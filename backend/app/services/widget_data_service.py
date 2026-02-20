"""Widget Data Service — fetches widget data with content-addressed caching.

Same caching pattern as PreviewService but tailored for widgets:
- Loads graph from DB (not from request body)
- Applies config_overrides from the widget
- Variable TTL per backing store (Materialize=30s, ClickHouse=5min)
- Content-addressed keys automatically deduplicate across widgets sharing upstream nodes
"""

import hashlib
import json
import logging
import time
from uuid import UUID

import sqlglot
from redis.asyncio import Redis

from app.core.config import settings
from app.core.metrics import cache_operation_duration_seconds, cache_operations_total
from app.services.query_router import QueryRouter
from app.services.workflow_compiler import CompiledSegment, WorkflowCompiler

logger = logging.getLogger(__name__)

CACHE_KEY_PREFIX = "flowforge:widget:"

# ClickHouse resource limits — higher than preview (widgets serve dashboards)
WIDGET_MAX_EXECUTION_TIME = 30  # seconds (preview uses 3)
WIDGET_MAX_MEMORY = 500_000_000  # 500 MB (preview uses 100 MB)
WIDGET_MAX_ROWS_TO_READ = 50_000_000  # 50M rows (preview uses 10M)


class WidgetDataService:
    """Fetches widget data with content-addressed Redis caching."""

    def __init__(
        self,
        compiler: WorkflowCompiler,
        query_router: QueryRouter,
        redis: Redis,
    ):
        self._compiler = compiler
        self._query_router = query_router
        self._redis = redis

    async def fetch_widget_data(
        self,
        tenant_id: UUID,
        source_node_id: str,
        graph_json: dict,
        config_overrides: dict | None = None,
        filter_params: dict | None = None,
        offset: int = 0,
        limit: int = 1_000,
    ) -> dict:
        """Fetch data for a widget's source node with caching.

        1. Extract nodes/edges from graph_json
        2. Apply config_overrides to the target node's data.config
        3. Compute content-addressed cache key
        4. Check Redis → return on hit
        5. On miss: compile subgraph → execute → cache → return
        """
        config_overrides = config_overrides or {}
        filter_params = filter_params or {}

        nodes = graph_json.get("nodes", [])
        edges = graph_json.get("edges", [])

        # Deep-copy nodes so we don't mutate the original, then apply overrides
        import copy

        nodes = copy.deepcopy(nodes)

        # Extract chart_config from the target node before overrides
        chart_config = None
        node_type = None
        for node in nodes:
            if node["id"] == source_node_id:
                node_type = node.get("type", "")
                raw_config = node.get("data", {}).get("config")
                chart_config = dict(raw_config) if raw_config is not None else {}
                break

        # Set default chart_type based on node type if not specified
        if chart_config is not None and "chart_type" not in chart_config:
            if node_type == "table_output":
                chart_config["chart_type"] = "table"
            elif node_type == "kpi_output":
                chart_config["chart_type"] = "kpi"
            elif node_type == "chart_output":
                chart_config["chart_type"] = chart_config.get("chart_type", "bar")

        if config_overrides:
            for node in nodes:
                if node["id"] == source_node_id:
                    data = node.setdefault("data", {})
                    config = data.setdefault("config", {})
                    config.update(config_overrides)
                    # Update chart_config with overrides applied
                    chart_config = dict(config)
                    break

        cache_key = self._compute_cache_key(
            tenant_id,
            source_node_id,
            nodes,
            edges,
            config_overrides,
            filter_params,
            offset,
            limit,
        )

        # Cache check
        cached = await self._cache_get(cache_key)
        if cached is not None:
            cached["cache_hit"] = True
            return cached

        # Compile and execute
        start = time.monotonic()
        segments = self._compiler.compile_subgraph(nodes, edges, source_node_id)

        if not segments:
            return {
                "columns": [],
                "rows": [],
                "total_rows": 0,
                "execution_ms": 0.0,
                "cache_hit": False,
                "offset": offset,
                "limit": limit,
                "chart_config": chart_config,
            }

        # Apply offset/limit to the final segment via SQLGlot (no f-string SQL)
        final = segments[-1]
        dialect = final.dialect or "clickhouse"
        inner = sqlglot.parse_one(final.sql, dialect=dialect)
        assert isinstance(inner, sqlglot.exp.Select)
        wrapped = (
            sqlglot.select("*")
            .from_(inner.subquery("widget_q"))
            .limit(int(limit))
            .offset(int(offset))
        )
        constrained_sql = wrapped.sql(dialect=dialect)

        # ClickHouse SETTINGS — module-level int constants, safe to append
        if final.target == "clickhouse":
            constrained_sql += (
                f" SETTINGS max_execution_time={int(WIDGET_MAX_EXECUTION_TIME)}"
                f", max_memory_usage={int(WIDGET_MAX_MEMORY)}"
                f", max_rows_to_read={int(WIDGET_MAX_ROWS_TO_READ)}"
            )

        constrained_segments = segments[:-1] + [
            CompiledSegment(
                sql=constrained_sql,
                dialect=final.dialect,
                target=final.target,
                source_node_ids=final.source_node_ids,
                params=final.params,
                limit=limit,
                offset=offset,
            )
        ]

        results = await self._query_router.execute_all(constrained_segments)
        elapsed_ms = (time.monotonic() - start) * 1000

        last_result = results[-1]
        columns = [{"name": col, "dtype": "String"} for col in last_result.columns]
        response = {
            "columns": columns,
            "rows": last_result.rows[:limit],
            "total_rows": last_result.total_rows,
            "execution_ms": round(elapsed_ms, 2),
            "cache_hit": False,
            "offset": offset,
            "limit": limit,
            "chart_config": chart_config,
        }

        # Determine TTL from final segment's target
        ttl = self._ttl_for_target(final.target)
        await self._cache_set(cache_key, response, ttl)

        return response

    def _compute_cache_key(
        self,
        tenant_id: UUID,
        target_node_id: str,
        nodes: list[dict],
        edges: list[dict],
        config_overrides: dict,
        filter_params: dict,
        offset: int,
        limit: int,
    ) -> str:
        """Content-addressed cache key including config overrides and filters."""
        ancestors = self._compiler._find_ancestors(target_node_id, edges)
        ancestors.add(target_node_id)

        stable_nodes = sorted(
            [
                {"id": n["id"], "type": n.get("type"), "data": n.get("data")}
                for n in nodes
                if n["id"] in ancestors
            ],
            key=lambda n: n["id"],
        )
        stable_edges = sorted(
            [
                {"source": e["source"], "target": e["target"]}
                for e in edges
                if e["source"] in ancestors and e["target"] in ancestors
            ],
            key=lambda e: (e["source"], e["target"]),
        )

        payload = json.dumps(
            {
                "tenant_id": str(tenant_id),
                "target": target_node_id,
                "nodes": stable_nodes,
                "edges": stable_edges,
                "config_overrides": config_overrides,
                "filter_params": filter_params,
                "offset": offset,
                "limit": limit,
            },
            sort_keys=True,
        )
        digest = hashlib.sha256(payload.encode()).hexdigest()[:16]
        return f"{CACHE_KEY_PREFIX}{digest}"

    def _ttl_for_target(self, target: str) -> int:
        """Return cache TTL based on the backing store."""
        if target == "materialize":
            return settings.preview.widget_cache_ttl_materialize
        return settings.preview.widget_cache_ttl_clickhouse

    async def _cache_get(self, key: str) -> dict | None:
        """Read from Redis cache. Returns None on miss or error (fail-open)."""
        try:
            start = time.monotonic()
            raw = await self._redis.get(key)
            elapsed = time.monotonic() - start
            cache_operation_duration_seconds.labels(
                cache_type="widget", operation="get"
            ).observe(elapsed)
            if raw is not None:
                cache_operations_total.labels(
                    cache_type="widget", operation="get", status="hit"
                ).inc()
                return json.loads(raw)
            cache_operations_total.labels(
                cache_type="widget", operation="get", status="miss"
            ).inc()
        except Exception:
            cache_operations_total.labels(
                cache_type="widget", operation="get", status="error"
            ).inc()
            logger.warning("Widget cache read failed for key %s", key, exc_info=True)
        return None

    async def _cache_set(self, key: str, value: dict, ttl: int) -> None:
        """Write to Redis cache with TTL. Errors logged, not raised."""
        try:
            start = time.monotonic()
            await self._redis.set(key, json.dumps(value), ex=ttl)
            elapsed = time.monotonic() - start
            cache_operation_duration_seconds.labels(
                cache_type="widget", operation="set"
            ).observe(elapsed)
            cache_operations_total.labels(
                cache_type="widget", operation="set", status="hit"
            ).inc()
        except Exception:
            cache_operations_total.labels(
                cache_type="widget", operation="set", status="error"
            ).inc()
            logger.warning("Widget cache write failed for key %s", key, exc_info=True)
