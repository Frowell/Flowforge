"""Widget Data Service — fetches widget data with content-addressed caching.

Same caching pattern as PreviewService but tailored for widgets:
- Loads graph from DB (not from request body)
- Applies config_overrides from the widget
- Variable TTL per backing store (Materialize=30s, ClickHouse=5min)
- Content-addressed keys automatically deduplicate across widgets sharing upstream nodes
"""

import logging
import time
from uuid import UUID

from redis.asyncio import Redis

from app.core.config import settings
from app.services.base_query_service import BaseQueryService
from app.services.query_router import QueryRouter
from app.services.workflow_compiler import WorkflowCompiler

logger = logging.getLogger(__name__)

CACHE_KEY_PREFIX = "flowforge:widget:"

# ClickHouse resource limits — higher than preview (widgets serve dashboards)
WIDGET_MAX_EXECUTION_TIME = 30  # seconds (preview uses 3)
WIDGET_MAX_MEMORY = 500_000_000  # 500 MB (preview uses 100 MB)
WIDGET_MAX_ROWS_TO_READ = 50_000_000  # 50M rows (preview uses 10M)


class WidgetDataService(BaseQueryService):
    """Fetches widget data with content-addressed Redis caching."""

    def __init__(
        self,
        compiler: WorkflowCompiler,
        query_router: QueryRouter,
        redis: Redis,
    ):
        super().__init__(redis=redis, cache_key_prefix=CACHE_KEY_PREFIX)
        self._compiler = compiler
        self._query_router = query_router

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
        cached = await self._cache_get(cache_key, cache_type="widget")
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
        constrained_segments = segments[:-1] + [
            self._wrap_with_limit_offset(
                final,
                limit=limit,
                offset=offset,
                subquery_alias="widget_q",
                clickhouse_settings={
                    "max_execution_time": WIDGET_MAX_EXECUTION_TIME,
                    "max_memory_usage": WIDGET_MAX_MEMORY,
                    "max_rows_to_read": WIDGET_MAX_ROWS_TO_READ,
                },
            )
        ]

        results = await self._query_router.execute_all(constrained_segments)
        elapsed_ms = (time.monotonic() - start) * 1000

        last_result = results[-1]
        # M8 fix: Use actual column types instead of hardcoded "String"
        columns = self._build_columns_with_types(last_result.columns)
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
        await self._cache_set(cache_key, response, ttl, cache_type="widget")

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

        payload = {
            "tenant_id": str(tenant_id),
            "target": target_node_id,
            "nodes": stable_nodes,
            "edges": stable_edges,
            "config_overrides": config_overrides,
            "filter_params": filter_params,
            "offset": offset,
            "limit": limit,
        }
        return self._compute_cache_key_hash(payload)

    def _ttl_for_target(self, target: str) -> int:
        """Return cache TTL based on the backing store."""
        if target == "materialize":
            return settings.preview.widget_cache_ttl_materialize
        return settings.preview.widget_cache_ttl_clickhouse
