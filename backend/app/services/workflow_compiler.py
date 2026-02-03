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

import structlog
import sqlglot
from sqlglot import exp

from app.core.metrics import query_compilation_duration_seconds
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
        self._schema_engine.validate_dag(nodes, edges)

        # Step 2: Topological sort
        sorted_ids = self._topological_sort(nodes, edges)

        # Step 3: Build expression trees and merge
        segments = self._build_and_merge(sorted_ids, nodes, edges)

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
        sub_edges = [e for e in edges if e["source"] in ancestors and e["target"] in ancestors]

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
    ) -> list[CompiledSegment]:
        """Build SQLGlot expression trees and merge adjacent compatible nodes.

        Merging rules:
        - Filter, Select, Sort, Rename, Formula, Unique, Sample on the same source -> single SELECT
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
        # Track whether a node's expression has GROUP BY (prevents further merging of certain ops)
        has_group_by: dict[str, bool] = {}

        mergeable_types = {"filter", "select", "sort", "rename", "formula", "unique", "sample", "limit", "window"}

        for node_id in sorted_ids:
            node = node_map[node_id]
            node_type = node.get("type", "")
            config = node.get("data", {}).get("config", {})

            if node_type in ("chart_output", "table_output", "kpi_output"):
                continue

            if node_type == "data_source":
                table_name = config.get("table", "unknown")
                columns = config.get("columns", [])

                if columns:
                    col_names = [
                        c["name"] if isinstance(c, dict) else c
                        for c in columns
                    ]
                    select_cols = [exp.Column(this=exp.to_identifier(name)) for name in col_names]
                else:
                    select_cols = [exp.Star()]

                expression = exp.Select().select(*select_cols).from_(
                    exp.Table(this=exp.to_identifier(table_name))
                )
                expr_map[node_id] = expression
                source_ids_map[node_id] = [node_id]
                root_map[node_id] = node_id
                has_group_by[node_id] = False

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
                    expression = self._apply_filter(expression, config)
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

        # Collect final segments: find terminal expressions (nodes with no downstream merge)
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

            expression = expr_map[node_id]
            sql = expression.sql(dialect="clickhouse")

            segments.append(
                CompiledSegment(
                    sql=sql,
                    dialect="clickhouse",
                    target="clickhouse",
                    source_node_ids=source_ids_map.get(node_id, [node_id]),
                )
            )

        return segments

    @staticmethod
    def _apply_filter(expression: exp.Expression, config: dict) -> exp.Expression:
        """Merge a WHERE clause into the expression based on filter config."""
        column = config.get("column")
        operator = config.get("operator", "=")
        value = config.get("value")

        if not column or value is None:
            return expression

        col_expr = exp.Column(this=exp.to_identifier(column))

        val_expr = exp.Literal.string(str(value))

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
            condition = exp.Like(this=col_expr, expression=exp.Literal.string(f"%{value}%"))
        elif operator == "starts with":
            condition = exp.Like(this=col_expr, expression=exp.Literal.string(f"{value}%"))
        elif operator == "ends with":
            condition = exp.Like(this=col_expr, expression=exp.Literal.string(f"%{value}"))
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
                condition = exp.Between(
                    this=col_expr,
                    low=exp.Literal.string(parts[0]),
                    high=exp.Literal.string(parts[1]),
                )
            else:
                return expression
        else:
            condition = exp.EQ(this=col_expr, expression=val_expr)

        return expression.where(condition)

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
            order_exprs.append(
                exp.Ordered(this=col_expr, desc=(direction == "desc"))
            )

        if order_exprs:
            return expression.order_by(*order_exprs)
        return expression

    @staticmethod
    def _apply_rename(expression: exp.Expression, config: dict) -> exp.Expression:
        """Apply AS aliases for renamed columns."""
        rename_map = config.get("rename_map", {})
        if not rename_map:
            return expression

        new_select = expression.copy()
        new_exprs = []
        for expr in new_select.args.get("expressions", []):
            if isinstance(expr, exp.Column):
                col_name = expr.name
                if col_name in rename_map:
                    new_exprs.append(
                        exp.Alias(this=expr, alias=exp.to_identifier(rename_map[col_name]))
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
                aggregations = [{"column": agg_col, "function": agg_func, "alias": f"{agg_func.lower()}_{agg_col}"}]

        if not aggregations:
            return parent_expr

        # Wrap parent as subquery
        subquery = parent_expr.subquery(alias="_sub")

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
            exp.Select()
            .select(*select_exprs)
            .from_(subquery)
            .group_by(*group_exprs)
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

        left_sub = left_expr.subquery(alias="_left")
        right_sub = right_expr.subquery(alias="_right")

        # Build ON condition
        on_condition = exp.EQ(
            this=exp.Column(this=exp.to_identifier(left_key), table=exp.to_identifier("_left")),
            expression=exp.Column(this=exp.to_identifier(right_key), table=exp.to_identifier("_right")),
        )

        # Map join type string to SQLGlot join kind
        join_kind_map = {
            "INNER": "JOIN",
            "LEFT": "LEFT JOIN",
            "RIGHT": "RIGHT JOIN",
            "FULL": "FULL JOIN",
        }
        join_kind = join_kind_map.get(join_type, "JOIN")

        query = (
            exp.Select()
            .select(exp.Star())
            .from_(left_sub)
        )

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
        return expression.limit(count)

    @staticmethod
    def _apply_limit(expression: exp.Expression, config: dict) -> exp.Expression:
        """Add LIMIT and OFFSET to the SELECT expression.

        Config: {limit: N, offset: M}
        """
        limit = config.get("limit", 100)
        offset = config.get("offset", 0)
        result = expression.limit(limit)
        if offset > 0:
            result = result.offset(offset)
        return result

    @staticmethod
    def _apply_window(expression: exp.Expression, config: dict) -> exp.Expression:
        """Add a window function column to the SELECT expression.

        Config: {
            function: "ROW_NUMBER" | "RANK" | "DENSE_RANK" | "LAG" | "LEAD" | "SUM" | "AVG" | etc.,
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
        func_requires_column = func_name in ("LAG", "LEAD", "SUM", "AVG", "MIN", "MAX", "FIRST_VALUE", "LAST_VALUE")

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
            partition_cols = [exp.Column(this=exp.to_identifier(col)) for col in partition_by]
            over_parts.append(exp.PartitionedByProperty(this=exp.Tuple(expressions=partition_cols)))

        # ORDER BY
        order_expr = None
        if order_by:
            order_col = exp.Column(this=exp.to_identifier(order_by))
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
        node_map = {n["id"]: n for n in nodes}

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
            limit_val = segments_with_limit.get(idx)
            if limit_val is not None:
                parsed = sqlglot.parse_one(seg.sql, read=seg.dialect)
                parsed = parsed.limit(limit_val, dialect=seg.dialect)
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
