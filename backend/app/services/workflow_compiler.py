"""Workflow Compiler — translates canvas DAG into merged SQL queries.

Steps:
1. Topological sort the node graph
2. Schema validate every connection
3. Merge adjacent compatible nodes into single queries
4. Determine target backing store per query segment
5. Return compiled query segments ready for the query router

All SQL is built via SQLGlot — never string concatenation.
"""

import time
from dataclasses import dataclass, field

import sqlglot
import structlog
from sqlglot import exp

from app.core.metrics import query_compilation_duration_seconds
from app.schemas.schema import ColumnSchema
from app.services.formula_parser import FormulaParser
from app.services.schema_engine import SchemaEngine

logger = structlog.stdlib.get_logger(__name__)


DEFAULT_HARD_CAP = 10_000

AGG_FUNC_MAP = {
    "SUM": exp.Sum,
    "AVG": exp.Avg,
    "COUNT": exp.Count,
    "MIN": exp.Min,
    "MAX": exp.Max,
}


@dataclass
class CompiledSegment:
    """A merged SQL query targeting a single backing store."""

    sql: str
    dialect: str  # "clickhouse" | "postgres" (for Materialize)
    target: str  # "clickhouse" | "materialize" | "redis"
    source_node_ids: list[str] = field(default_factory=list)
    params: dict = field(default_factory=dict)
    limit: int | None = None
    offset: int | None = None


class WorkflowCompiler:
    """Compiles a workflow DAG into executable, merged SQL query segments."""

    def __init__(self, schema_engine: SchemaEngine):
        self._schema_engine = schema_engine

    def compile(
        self,
        nodes: list[dict],
        edges: list[dict],
    ) -> list[CompiledSegment]:
        """Compile a full workflow DAG into query segments.

        Adjacent compatible nodes are merged into single queries.
        """
        start = time.perf_counter()

        # Step 1: Validate schemas through the DAG
        schema_map = self._schema_engine.validate_dag(nodes, edges)

        # Step 2: Topological sort
        sorted_ids = self._topological_sort(nodes, edges)

        # Step 3: Build expression trees and merge
        segments = self._build_and_merge(sorted_ids, nodes, edges, schema_map)

        # Step 4: Apply LIMIT clauses based on output node config
        segments = self._apply_limits(segments, nodes, edges)

        duration = time.perf_counter() - start
        query_compilation_duration_seconds.observe(duration)
        logger.info(
            "workflow_compiled",
            node_count=len(nodes),
            segment_count=len(segments),
            compilation_ms=round(duration * 1000, 2),
        )

        return segments

    def compile_subgraph(
        self,
        nodes: list[dict],
        edges: list[dict],
        target_node_id: str,
    ) -> list[CompiledSegment]:
        """Compile only the subgraph leading to a specific output node.

        Used when executing a single widget's query for dashboards/embeds.
        """
        # Find all ancestor nodes of the target
        ancestors = self._find_ancestors(target_node_id, edges)
        ancestors.add(target_node_id)

        sub_nodes = [n for n in nodes if n["id"] in ancestors]
        sub_edges = [
            e for e in edges if e["source"] in ancestors and e["target"] in ancestors
        ]

        return self.compile(sub_nodes, sub_edges)

    def _topological_sort(self, nodes: list[dict], edges: list[dict]) -> list[str]:
        """Kahn's algorithm for topological ordering."""
        in_degree: dict[str, int] = {n["id"]: 0 for n in nodes}
        adjacency: dict[str, list[str]] = {n["id"]: [] for n in nodes}

        for edge in edges:
            adjacency[edge["source"]].append(edge["target"])
            in_degree[edge["target"]] += 1

        queue = [nid for nid, deg in in_degree.items() if deg == 0]
        result: list[str] = []

        while queue:
            node_id = queue.pop(0)
            result.append(node_id)
            for neighbor in adjacency[node_id]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(result) != len(nodes):
            raise ValueError("Workflow DAG contains a cycle")

        return result

    def _build_and_merge(
        self,
        sorted_ids: list[str],
        nodes: list[dict],
        edges: list[dict],
        schema_map: dict[str, list[ColumnSchema]] | None = None,
    ) -> list[CompiledSegment]:
        """Build SQLGlot expression trees and merge adjacent compatible nodes.

        Merging rules:
        - Filter, Select, Sort, Rename, Formula, Unique, Sample
          on the same source -> single SELECT
        - Group By creates a new expression layer (wraps parent as subquery)
        - Join creates a new segment combining two upstream segments
        - Union creates a new segment combining two upstream segments
        """
        node_map = {n["id"]: n for n in nodes}

        # Build parent mapping: child_id -> list of parent_ids
        parents: dict[str, list[str]] = {}
        for edge in edges:
            parents.setdefault(edge["target"], []).append(edge["source"])

        # Map node_id -> its current SQLGlot expression tree
        expr_map: dict[str, exp.Expression] = {}
        # Map node_id -> list of all source node ids contributing to this expression
        source_ids_map: dict[str, list[str]] = {}
        # Track which node_id owns the "root" segment (for merging)
        # node_id -> root_node_id (the data_source that started this chain)
        root_map: dict[str, str] = {}
        # Track whether a node's expression has GROUP BY
        # (prevents further merging of certain ops)
        has_group_by: dict[str, bool] = {}
        # Map node_id -> (target, dialect) for backing store routing
        target_map: dict[str, tuple[str, str]] = {}

        mergeable_types = {
            "filter",
            "select",
            "sort",
            "rename",
            "formula",
            "unique",
            "sample",
            "limit",
            "window",
        }

        for node_id in sorted_ids:
            node = node_map[node_id]
            node_type = node.get("type", "")
            config = node.get("data", {}).get("config", {})

            if node_type in ("chart_output", "table_output", "kpi_output"):
                continue

            expression: exp.Expression

            if node_type == "data_source":
                table_name = config.get("table", "unknown")
                columns = config.get("columns", [])

                select_cols: list[exp.Expression]
                if columns:
                    col_names = [
                        c["name"] if isinstance(c, dict) else c for c in columns
                    ]
                    select_cols = [
                        exp.Column(this=exp.to_identifier(name)) for name in col_names
                    ]
                else:
                    select_cols = [exp.Star()]

                expression = (
                    exp.Select()
                    .select(*select_cols)
                    .from_(exp.Table(this=exp.to_identifier(table_name)))
                )
                expr_map[node_id] = expression
                source_ids_map[node_id] = [node_id]
                root_map[node_id] = node_id
                has_group_by[node_id] = False
                target_map[node_id] = self._detect_target(table_name)

            elif node_type in mergeable_types:
                parent_ids = parents.get(node_id, [])
                if not parent_ids:
                    continue
                parent_id = parent_ids[0]

                if parent_id not in expr_map:
                    continue

                expression = expr_map[parent_id]
                parent_source_ids = source_ids_map[parent_id]

                if node_type == "filter":
                    # Look up parent's output schema for typed literals
                    filter_input_schema = (
                        schema_map.get(parent_id) if schema_map else None
                    )
                    expression = self._apply_filter(
                        expression, config, filter_input_schema
                    )
                elif node_type == "select":
                    expression = self._apply_select(expression, config)
                elif node_type == "sort":
                    expression = self._apply_sort(expression, config)
                elif node_type == "rename":
                    expression = self._apply_rename(expression, config)
                elif node_type == "formula":
                    expression = self._apply_formula(expression, config)
                elif node_type == "unique":
                    expression = self._apply_unique(expression, config)
                elif node_type == "sample":
                    expression = self._apply_sample(expression, config)
                elif node_type == "limit":
                    expression = self._apply_limit(expression, config)
                elif node_type == "window":
                    expression = self._apply_window(expression, config)

                expr_map[node_id] = expression
                source_ids_map[node_id] = parent_source_ids + [node_id]
                root_map[node_id] = root_map.get(parent_id, parent_id)
                has_group_by[node_id] = has_group_by.get(parent_id, False)
                target_map[node_id] = target_map.get(
                    parent_id, ("clickhouse", "clickhouse")
                )

            elif node_type == "group_by":
                parent_ids = parents.get(node_id, [])
                if not parent_ids:
                    continue
                parent_id = parent_ids[0]
                if parent_id not in expr_map:
                    continue

                parent_expr = expr_map[parent_id]
                expression = self._apply_group_by(parent_expr, config)
                expr_map[node_id] = expression
                source_ids_map[node_id] = source_ids_map[parent_id] + [node_id]
                root_map[node_id] = node_id  # new segment root
                has_group_by[node_id] = True
                target_map[node_id] = target_map.get(
                    parent_ids[0], ("clickhouse", "clickhouse")
                )

            elif node_type == "pivot":
                parent_ids = parents.get(node_id, [])
                if not parent_ids:
                    continue
                parent_id = parent_ids[0]
                if parent_id not in expr_map:
                    continue

                parent_expr = expr_map[parent_id]
                expression = self._apply_pivot(parent_expr, config)
                expr_map[node_id] = expression
                source_ids_map[node_id] = source_ids_map[parent_id] + [node_id]
                root_map[node_id] = node_id  # new segment root
                has_group_by[node_id] = True
                target_map[node_id] = target_map.get(
                    parent_ids[0], ("clickhouse", "clickhouse")
                )

            elif node_type == "join":
                parent_ids = parents.get(node_id, [])
                if len(parent_ids) < 2:
                    continue
                left_id, right_id = parent_ids[0], parent_ids[1]
                if left_id not in expr_map or right_id not in expr_map:
                    continue

                left_expr = expr_map[left_id]
                right_expr = expr_map[right_id]
                expression = self._apply_join(left_expr, right_expr, config)
                expr_map[node_id] = expression
                source_ids_map[node_id] = (
                    source_ids_map[left_id] + source_ids_map[right_id] + [node_id]
                )
                root_map[node_id] = node_id  # new segment root
                has_group_by[node_id] = False
                target_map[node_id] = ("clickhouse", "clickhouse")

            elif node_type == "union":
                parent_ids = parents.get(node_id, [])
                if len(parent_ids) < 2:
                    continue
                left_id, right_id = parent_ids[0], parent_ids[1]
                if left_id not in expr_map or right_id not in expr_map:
                    continue

                left_expr = expr_map[left_id]
                right_expr = expr_map[right_id]
                expression = self._apply_union(left_expr, right_expr)
                expr_map[node_id] = expression
                source_ids_map[node_id] = (
                    source_ids_map[left_id] + source_ids_map[right_id] + [node_id]
                )
                root_map[node_id] = node_id  # new segment root
                has_group_by[node_id] = False
                target_map[node_id] = ("clickhouse", "clickhouse")

        # Collect final segments: find terminal expressions
        # (nodes with no downstream merge)
        # A node's expression is terminal if no other node merged into it
        merged_into: set[str] = set()
        for node_id in sorted_ids:
            parent_ids = parents.get(node_id, [])
            node_type = node_map[node_id].get("type", "")
            if node_type in mergeable_types and parent_ids:
                parent_id = parent_ids[0]
                if parent_id in expr_map:
                    merged_into.add(parent_id)
            elif node_type == "group_by" and parent_ids:
                # group_by consumes its parent expression
                parent_id = parent_ids[0]
                if parent_id in expr_map:
                    merged_into.add(parent_id)
            elif node_type == "pivot" and parent_ids:
                # pivot consumes its parent expression
                parent_id = parent_ids[0]
                if parent_id in expr_map:
                    merged_into.add(parent_id)
            elif node_type == "join" and len(parent_ids) >= 2:
                # join consumes both parent expressions
                for pid in parent_ids[:2]:
                    if pid in expr_map:
                        merged_into.add(pid)
            elif node_type == "union" and len(parent_ids) >= 2:
                # union consumes both parent expressions
                for pid in parent_ids[:2]:
                    if pid in expr_map:
                        merged_into.add(pid)

        segments: list[CompiledSegment] = []

        for node_id in sorted_ids:
            if node_id not in expr_map:
                continue
            if node_id in merged_into:
                continue

            target, dialect = target_map.get(node_id, ("clickhouse", "clickhouse"))

            if target == "redis":
                # Redis segments skip SQL — pass key pattern via params
                root_id = root_map.get(node_id, node_id)
                root_node = node_map.get(root_id)
                key_pattern = (
                    root_node.get("data", {}).get("config", {}).get("table", "")
                    if root_node
                    else ""
                )
                segments.append(
                    CompiledSegment(
                        sql="",
                        dialect="",
                        target="redis",
                        source_node_ids=source_ids_map.get(node_id, [node_id]),
                        params={
                            "lookup_type": "SCAN_HASH",
                            "pattern": key_pattern,
                        },
                    )
                )
            else:
                expression = expr_map[node_id]
                sql = expression.sql(dialect=dialect or "clickhouse")
                segments.append(
                    CompiledSegment(
                        sql=sql,
                        dialect=dialect or "clickhouse",
                        target=target,
                        source_node_ids=source_ids_map.get(node_id, [node_id]),
                    )
                )

        return segments

    @staticmethod
    def _normalize_datetime(value: str) -> str:
        """Normalize datetime strings for ClickHouse compatibility.

        HTML datetime-local inputs produce values like '2026-02-10T11:48'
        (missing seconds). ClickHouse DateTime64 requires full ISO format.
        """
        s = str(value).replace("T", " ")
        # Append :00 if seconds missing (e.g. '2026-02-10 11:48')
        parts = s.split(" ")
        if len(parts) == 2:
            time_parts = parts[1].split(":")
            if len(time_parts) == 2:
                s = f"{parts[0]} {parts[1]}:00"
        return s

    @staticmethod
    def _detect_target(table_name: str) -> tuple[str, str]:
        """Detect backing store target and SQL dialect from table name."""
        if table_name.startswith("latest:"):
            return ("redis", "")
        if table_name.startswith("live_"):
            return ("materialize", "postgres")
        return ("clickhouse", "clickhouse")

    @staticmethod
    def _make_literal(value: str, dtype: str) -> exp.Expression:
        """Build a typed SQLGlot literal based on column dtype."""
        if dtype in ("int64", "int32", "uint64", "uint32"):
            try:
                return exp.Literal.number(int(value))
            except (ValueError, TypeError):
                return exp.Literal.string(str(value))
        elif dtype in ("float64", "float32"):
            try:
                return exp.Literal.number(float(value))
            except (ValueError, TypeError):
                return exp.Literal.string(str(value))
        elif dtype in ("bool", "boolean"):
            return exp.Boolean(this=value in ("true", "True", "1", True))
        else:
            # string, object, datetime, and any unknown dtype → string literal
            return exp.Literal.string(str(value))

    @staticmethod
    def _apply_filter(
        expression: exp.Expression,
        config: dict,
        input_schema: list[ColumnSchema] | None = None,
    ) -> exp.Expression:
        """Merge a WHERE clause into the expression based on filter config."""
        column = config.get("column")
        operator = config.get("operator", "=")
        value = config.get("value")

        if not column or value is None:
            return expression

        col_expr = exp.Column(this=exp.to_identifier(column))

        # Look up column dtype from input schema
        dtype = "string"
        if input_schema:
            for col in input_schema:
                if col.name == column:
                    dtype = col.dtype
                    break

        # Normalize datetime values for ClickHouse compatibility
        if operator in ("before", "after", "between", ">", "<", ">=", "<="):
            if isinstance(value, str) and ("T" in value or "-" in value.split(" ")[0]):
                value = WorkflowCompiler._normalize_datetime(value)
            elif isinstance(value, (list, tuple)):
                value = [
                    WorkflowCompiler._normalize_datetime(v) if isinstance(v, str) else v
                    for v in value
                ]

        val_expr = WorkflowCompiler._make_literal(str(value), dtype)

        condition: exp.Expression
        if operator == "=":
            condition = exp.EQ(this=col_expr, expression=val_expr)
        elif operator == "!=":
            condition = exp.NEQ(this=col_expr, expression=val_expr)
        elif operator == ">":
            condition = exp.GT(this=col_expr, expression=val_expr)
        elif operator == "<":
            condition = exp.LT(this=col_expr, expression=val_expr)
        elif operator == ">=":
            condition = exp.GTE(this=col_expr, expression=val_expr)
        elif operator == "<=":
            condition = exp.LTE(this=col_expr, expression=val_expr)
        elif operator == "contains":
            condition = exp.Like(
                this=col_expr, expression=exp.Literal.string(f"%{value}%")
            )
        elif operator == "starts with":
            condition = exp.Like(
                this=col_expr, expression=exp.Literal.string(f"{value}%")
            )
        elif operator == "ends with":
            condition = exp.Like(
                this=col_expr, expression=exp.Literal.string(f"%{value}")
            )
        elif operator in ("before", "after"):
            if operator == "before":
                condition = exp.LT(this=col_expr, expression=val_expr)
            else:
                condition = exp.GT(this=col_expr, expression=val_expr)
        elif operator == "between":
            # value should be a list [low, high] or "low,high" string
            if isinstance(value, str):
                parts = [v.strip() for v in value.split(",")]
            elif isinstance(value, (list, tuple)):
                parts = [str(v) for v in value]
            else:
                return expression
            if len(parts) == 2:
                low_expr = WorkflowCompiler._make_literal(
                    WorkflowCompiler._normalize_datetime(parts[0]), dtype
                )
                high_expr = WorkflowCompiler._make_literal(
                    WorkflowCompiler._normalize_datetime(parts[1]), dtype
                )
                condition = exp.Between(
                    this=col_expr,
                    low=low_expr,
                    high=high_expr,
                )
            else:
                return expression
        else:
            raise ValueError(f"Unsupported filter operator: {operator!r}")

        return expression.where(condition)  # type: ignore[attr-defined, no-any-return]

    @staticmethod
    def _apply_select(expression: exp.Expression, config: dict) -> exp.Expression:
        """Replace the SELECT column list with only the specified columns."""
        columns = config.get("columns", [])
        if not columns:
            return expression

        # Build new select with only the requested columns
        new_select = expression.copy()
        new_select.args["expressions"] = [
            exp.Column(this=exp.to_identifier(name)) for name in columns
        ]
        return new_select

    @staticmethod
    def _apply_sort(expression: exp.Expression, config: dict) -> exp.Expression:
        """Merge ORDER BY into the expression."""
        sort_by = config.get("sort_by", [])
        if not sort_by:
            return expression

        order_exprs = []
        for rule in sort_by:
            col_name = rule.get("column")
            direction = rule.get("direction", "asc").lower()
            if not col_name:
                continue
            col_expr = exp.Column(this=exp.to_identifier(col_name))
            order_exprs.append(exp.Ordered(this=col_expr, desc=(direction == "desc")))

        if order_exprs:
            return expression.order_by(*order_exprs)  # type: ignore[attr-defined, no-any-return]
        return expression

    @staticmethod
    def _apply_rename(expression: exp.Expression, config: dict) -> exp.Expression:
        """Apply AS aliases for renamed columns."""
        rename_map = config.get("rename_map", {})
        if not rename_map:
            return expression

        new_select = expression.copy()
        new_exprs: list[exp.Expression] = []
        for expr in new_select.args.get("expressions", []):
            if isinstance(expr, exp.Column):
                col_name = expr.name
                if col_name in rename_map:
                    new_exprs.append(
                        exp.Alias(
                            this=expr, alias=exp.to_identifier(rename_map[col_name])
                        )
                    )
                else:
                    new_exprs.append(expr)
            elif isinstance(expr, exp.Star):
                new_exprs.append(expr)
            else:
                new_exprs.append(expr)
        new_select.args["expressions"] = new_exprs
        return new_select

    @staticmethod
    def _apply_group_by(parent_expr: exp.Expression, config: dict) -> exp.Expression:
        """Create a GROUP BY query wrapping the parent expression as a subquery.

        Config: {group_columns: [...], aggregations: [{column, function, alias}]}
        Also supports legacy single-agg: {group_columns, agg_column, agg_function}
        """
        group_columns = config.get("group_columns", [])
        if not group_columns:
            return parent_expr

        # Normalize aggregations
        aggregations = config.get("aggregations", [])
        if not aggregations:
            # Legacy single-agg format
            agg_col = config.get("agg_column")
            agg_func = config.get("agg_function", "SUM")
            if agg_col:
                aggregations = [
                    {
                        "column": agg_col,
                        "function": agg_func,
                        "alias": f"{agg_func.lower()}_{agg_col}",
                    }
                ]

        if not aggregations:
            return parent_expr

        # Wrap parent as subquery
        subquery = parent_expr.subquery(alias="_sub")  # type: ignore[attr-defined]

        # Build SELECT: group columns + aggregations
        select_exprs: list[exp.Expression] = []

        for col_name in group_columns:
            select_exprs.append(exp.Column(this=exp.to_identifier(col_name)))

        for agg in aggregations:
            agg_col = agg.get("column", "")
            agg_func = agg.get("function", "SUM").upper()
            alias = agg.get("alias", f"{agg_func.lower()}_{agg_col}")

            col_ref = exp.Column(this=exp.to_identifier(agg_col))

            agg_class = AGG_FUNC_MAP.get(agg_func)
            agg_expr: exp.Expression
            if agg_class:
                agg_expr = agg_class(this=col_ref)
            else:
                agg_expr = exp.Anonymous(this=agg_func, expressions=[col_ref])

            select_exprs.append(
                exp.Alias(this=agg_expr, alias=exp.to_identifier(alias))
            )

        # Build GROUP BY clause
        group_exprs = [exp.Column(this=exp.to_identifier(c)) for c in group_columns]

        query = (
            exp.Select().select(*select_exprs).from_(subquery).group_by(*group_exprs)
        )

        return query

    @staticmethod
    def _apply_pivot(parent_expr: exp.Expression, config: dict) -> exp.Expression:
        """Create a GROUP BY query for pivot, wrapping the parent as a subquery.

        Config: {row_columns: [...], pivot_column: str, value_column: str,
                 aggregation: "SUM"|"AVG"|"COUNT"|"MIN"|"MAX"}

        Produces: SELECT row_columns, pivot_column, agg(value_column) AS value_agg
                  FROM (_sub) GROUP BY row_columns, pivot_column

        Full dynamic column explosion (one output column per distinct pivot value)
        would require a two-pass approach; this produces the grouped intermediate
        representation that matches the schema engine contract.
        """
        row_columns = config.get("row_columns", [])
        pivot_column = config.get("pivot_column", "")
        value_column = config.get("value_column", "")
        aggregation = config.get("aggregation", "SUM").upper()

        if not row_columns or not value_column:
            return parent_expr

        # Wrap parent as subquery
        subquery = parent_expr.subquery(alias="_sub")  # type: ignore[attr-defined]

        # Build SELECT: row_columns + pivot_column + aggregation
        select_exprs: list[exp.Expression] = []
        group_exprs: list[exp.Expression] = []

        for col_name in row_columns:
            col = exp.Column(this=exp.to_identifier(col_name))
            select_exprs.append(col)
            group_exprs.append(exp.Column(this=exp.to_identifier(col_name)))

        if pivot_column:
            pivot_col = exp.Column(this=exp.to_identifier(pivot_column))
            select_exprs.append(pivot_col)
            group_exprs.append(exp.Column(this=exp.to_identifier(pivot_column)))

        # Aggregation on value_column
        alias_name = f"{value_column}_{aggregation.lower()}"
        col_ref = exp.Column(this=exp.to_identifier(value_column))

        agg_class = AGG_FUNC_MAP.get(aggregation)
        agg_expr: exp.Expression
        if agg_class:
            agg_expr = agg_class(this=col_ref)
        else:
            agg_expr = exp.Anonymous(this=aggregation, expressions=[col_ref])

        select_exprs.append(
            exp.Alias(this=agg_expr, alias=exp.to_identifier(alias_name))
        )

        query = (
            exp.Select().select(*select_exprs).from_(subquery).group_by(*group_exprs)
        )

        return query

    @staticmethod
    def _apply_join(
        left_expr: exp.Expression,
        right_expr: exp.Expression,
        config: dict,
    ) -> exp.Expression:
        """Combine two upstream expressions with a JOIN.

        Config: {join_type: "inner"|"left"|"right"|"full", left_key, right_key}
        """
        join_type = config.get("join_type", "inner").upper()
        left_key = config.get("left_key", "id")
        right_key = config.get("right_key", "id")

        left_sub = left_expr.subquery(alias="_left")  # type: ignore[attr-defined]
        right_sub = right_expr.subquery(alias="_right")  # type: ignore[attr-defined]

        # Build ON condition
        on_condition = exp.EQ(
            this=exp.Column(
                this=exp.to_identifier(left_key), table=exp.to_identifier("_left")
            ),
            expression=exp.Column(
                this=exp.to_identifier(right_key), table=exp.to_identifier("_right")
            ),
        )

        query = exp.Select().select(exp.Star()).from_(left_sub)

        # Use the join method with appropriate kind
        query = query.join(
            right_sub,
            on=on_condition,
            join_type=join_type if join_type != "INNER" else "",
        )

        return query

    @staticmethod
    def _apply_union(
        left_expr: exp.Expression,
        right_expr: exp.Expression,
    ) -> exp.Expression:
        """Combine two upstream expressions with UNION ALL."""
        return exp.Union(this=left_expr, expression=right_expr, distinct=False)

    @staticmethod
    def _apply_formula(expression: exp.Expression, config: dict) -> exp.Expression:
        """Merge a computed column into the parent SELECT list.

        Config: {expression: str, output_column: str, output_dtype: str}
        """
        formula_expr_str = config.get("expression", "")
        output_column = config.get("output_column", "calculated")

        if not formula_expr_str:
            return expression

        parser = FormulaParser()
        parsed = parser.compile_to_expression(formula_expr_str)

        new_select = expression.copy()
        existing_exprs = list(new_select.args.get("expressions", []))
        existing_exprs.append(
            exp.Alias(this=parsed, alias=exp.to_identifier(output_column))
        )
        new_select.args["expressions"] = existing_exprs
        return new_select

    @staticmethod
    def _apply_unique(expression: exp.Expression, config: dict) -> exp.Expression:
        """Add DISTINCT to the SELECT expression.

        Config: {columns: [...]} — if empty, DISTINCT on all columns.
        """
        new_select = expression.copy()
        new_select.args["distinct"] = exp.Distinct()
        return new_select

    @staticmethod
    def _apply_sample(expression: exp.Expression, config: dict) -> exp.Expression:
        """Add LIMIT to the SELECT expression.

        Config: {count: N}
        """
        count = config.get("count", 100)
        return expression.limit(count)  # type: ignore[attr-defined, no-any-return]

    @staticmethod
    def _apply_limit(expression: exp.Expression, config: dict) -> exp.Expression:
        """Add LIMIT and OFFSET to the SELECT expression.

        Config: {limit: N, offset: M}
        """
        limit = config.get("limit", 100)
        offset = config.get("offset", 0)
        result: exp.Expression = expression.limit(limit)  # type: ignore[attr-defined]
        if offset > 0:
            result = result.offset(offset)  # type: ignore[attr-defined]
        return result

    @staticmethod
    def _apply_window(expression: exp.Expression, config: dict) -> exp.Expression:
        """Add a window function column to the SELECT expression.

        Config: {
            function: "ROW_NUMBER" | "RANK" | "DENSE_RANK"
                | "LAG" | "LEAD" | "SUM" | "AVG" | etc.,
            source_column: "col_name" (for functions that need a column),
            partition_by: ["col1", "col2"],
            order_by: "col_name",
            order_direction: "ASC" | "DESC",
            output_column: "result_name"
        }
        """
        func_name = config.get("function", "ROW_NUMBER")
        source_column = config.get("source_column", "")
        partition_by = config.get("partition_by", [])
        order_by = config.get("order_by", "")
        order_dir = config.get("order_direction", "ASC")
        output_column = config.get("output_column", "window_result")

        # Build the window function expression
        func_requires_column = func_name in (
            "LAG",
            "LEAD",
            "SUM",
            "AVG",
            "MIN",
            "MAX",
            "FIRST_VALUE",
            "LAST_VALUE",
        )

        if func_requires_column and source_column:
            func_expr = exp.Anonymous(
                this=func_name,
                expressions=[exp.Column(this=exp.to_identifier(source_column))],
            )
        else:
            func_expr = exp.Anonymous(this=func_name, expressions=[])

        # Build OVER clause
        over_parts = []

        # PARTITION BY
        if partition_by:
            partition_cols = [
                exp.Column(this=exp.to_identifier(col)) for col in partition_by
            ]
            over_parts.append(
                exp.PartitionedByProperty(this=exp.Tuple(expressions=partition_cols))
            )

        # ORDER BY
        order_expr = None
        if order_by:
            order_col: exp.Expression = exp.Column(this=exp.to_identifier(order_by))
            if order_dir.upper() == "DESC":
                order_col = exp.Ordered(this=order_col, desc=True)
            else:
                order_col = exp.Ordered(this=order_col, desc=False)
            order_expr = exp.Order(expressions=[order_col])

        # Build the window expression
        window_spec = exp.Window(
            this=func_expr,
            partition_by=partition_by if partition_by else None,
            order=order_expr,
        )

        # Add as aliased column to SELECT
        alias_expr = exp.Alias(this=window_spec, alias=exp.to_identifier(output_column))

        # Clone expression and add the new column
        new_select = expression.copy()
        if hasattr(new_select, "expressions"):
            new_select.args["expressions"] = list(new_select.expressions) + [alias_expr]

        return new_select

    def _apply_limits(
        self,
        segments: list[CompiledSegment],
        nodes: list[dict],
        edges: list[dict],
    ) -> list[CompiledSegment]:
        """Inject LIMIT clauses into compiled segments via SQLGlot AST.

        - Output nodes (table_output) read max_rows from their config.
        - Non-output terminal segments get DEFAULT_HARD_CAP.
        """
        # Build mapping: source_node_id -> segment index
        node_to_segment: dict[str, int] = {}
        for idx, seg in enumerate(segments):
            for nid in seg.source_node_ids:
                node_to_segment[nid] = idx

        # Track which segments are upstream of an output node
        segments_with_limit: dict[int, int] = {}

        # Build child -> parents mapping for edge lookup
        children: dict[str, list[str]] = {}
        for edge in edges:
            children.setdefault(edge["source"], []).append(edge["target"])

        for node in nodes:
            node_type = node.get("type", "")
            if node_type not in ("table_output", "chart_output", "kpi_output"):
                continue

            max_rows = (
                node.get("data", {}).get("config", {}).get("max_rows", DEFAULT_HARD_CAP)
            )

            # Find upstream node(s) for this output node
            for edge in edges:
                if edge["target"] == node["id"]:
                    upstream_id = edge["source"]
                    if upstream_id in node_to_segment:
                        seg_idx = node_to_segment[upstream_id]
                        # Use the smallest limit if multiple outputs share a segment
                        if seg_idx not in segments_with_limit:
                            segments_with_limit[seg_idx] = max_rows
                        else:
                            segments_with_limit[seg_idx] = min(
                                segments_with_limit[seg_idx], max_rows
                            )

        # Apply DEFAULT_HARD_CAP to any segment not already limited
        for idx in range(len(segments)):
            if idx not in segments_with_limit:
                segments_with_limit[idx] = DEFAULT_HARD_CAP

        # Inject LIMIT into SQL AST via SQLGlot
        result = []
        for idx, seg in enumerate(segments):
            if seg.target == "redis":
                result.append(seg)
                continue
            limit_val = segments_with_limit.get(idx)
            if limit_val is not None:
                parsed = sqlglot.parse_one(seg.sql, read=seg.dialect)
                parsed = parsed.limit(limit_val, dialect=seg.dialect)  # type: ignore[attr-defined]
                new_sql = parsed.sql(dialect=seg.dialect)
                result.append(
                    CompiledSegment(
                        sql=new_sql,
                        dialect=seg.dialect,
                        target=seg.target,
                        source_node_ids=seg.source_node_ids,
                        params=seg.params,
                        limit=limit_val,
                        offset=seg.offset,
                    )
                )
            else:
                result.append(seg)

        return result

    def _find_ancestors(self, node_id: str, edges: list[dict]) -> set[str]:
        """Find all ancestor node IDs for a given node."""
        parents: dict[str, list[str]] = {}
        for edge in edges:
            parents.setdefault(edge["target"], []).append(edge["source"])

        ancestors: set[str] = set()
        stack = list(parents.get(node_id, []))

        while stack:
            current = stack.pop()
            if current not in ancestors:
                ancestors.add(current)
                stack.extend(parents.get(current, []))

        return ancestors
