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
from app.services.schema_engine import SchemaEngine

logger = structlog.stdlib.get_logger(__name__)


DEFAULT_HARD_CAP = 10_000


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
        - Filter, Select, Sort, Rename on the same source -> single SELECT
        - Group By following the above -> extends the same query
        - Join creates a new segment combining two upstream segments
        """
        # TODO: Implement SQLGlot expression tree building per node type
        # TODO: Implement merge detection (same source lineage, compatible ops)
        # TODO: Determine dialect per segment based on source table freshness

        # Placeholder: return one segment per non-terminal node
        node_map = {n["id"]: n for n in nodes}
        segments: list[CompiledSegment] = []

        for node_id in sorted_ids:
            node = node_map[node_id]
            node_type = node.get("type", "")

            if node_type in ("chart_output", "table_output"):
                continue

            if node_type == "data_source":
                table = node.get("data", {}).get("config", {}).get("table", "unknown")
                sql = sqlglot.transpile(
                    f"SELECT * FROM {table}",
                    read="clickhouse",
                    write="clickhouse",
                )[0]
                segments.append(
                    CompiledSegment(
                        sql=sql,
                        dialect="clickhouse",
                        target="clickhouse",
                        source_node_ids=[node_id],
                    )
                )

        return segments

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
            if node_type not in ("table_output", "chart_output"):
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
