"""Preview Service — executes constrained preview queries with caching.

Layer 2: Content-addressed Redis cache (keyed on node config, not position).
Layer 3: Query constraints (LIMIT, max_execution_time, max_memory_usage).
"""

import logging
import time
from uuid import UUID

from redis.asyncio import Redis

from app.services.base_query_service import BaseQueryService
from app.services.query_router import QueryRouter
from app.services.workflow_compiler import WorkflowCompiler

logger = logging.getLogger(__name__)

# Preview constraints
PREVIEW_LIMIT = 100
PREVIEW_HARD_CAP = 10_000
CACHE_TTL = 300  # 5 minutes
PREVIEW_MAX_EXECUTION_TIME = 3
PREVIEW_MAX_MEMORY = 100_000_000
PREVIEW_MAX_ROWS_TO_READ = 10_000_000

CACHE_KEY_PREFIX = "flowforge:preview:"


class PreviewService(BaseQueryService):
    """Executes preview queries with caching and resource constraints."""

    def __init__(
        self,
        compiler: WorkflowCompiler,
        query_router: QueryRouter,
        redis: Redis,
    ):
        super().__init__(redis=redis, cache_key_prefix=CACHE_KEY_PREFIX)
        self._compiler = compiler
        self._query_router = query_router

    async def execute_preview(
        self,
        tenant_id: UUID,
        target_node_id: str,
        nodes: list[dict],
        edges: list[dict],
        offset: int = 0,
        limit: int = PREVIEW_LIMIT,
    ) -> dict:
        """Execute a constrained preview query for a target node.

        1. Compute content-addressed cache key (includes tenant_id + offset/limit)
        2. Check Redis cache -> return on hit
        3. Compile subgraph on cache miss
        4. Wrap SQL with LIMIT + OFFSET + SETTINGS constraints
        5. Execute via query router
        6. Cache result and return
        """
        limit = min(limit, PREVIEW_HARD_CAP)

        cache_key = self._compute_cache_key(
            tenant_id, target_node_id, nodes, edges, offset, limit
        )

        # Layer 2: Cache check
        cached = await self._cache_get(cache_key, cache_type="preview")
        if cached is not None:
            cached["cache_hit"] = True
            return cached

        # Compile the subgraph leading to the target node
        start = time.monotonic()
        segments = self._compiler.compile_subgraph(nodes, edges, target_node_id)

        if not segments:
            return {
                "columns": [],
                "rows": [],
                "total_estimate": 0,
                "execution_ms": 0.0,
                "cache_hit": False,
                "offset": offset,
                "limit": limit,
            }

        # Layer 3: Wrap the final segment with constraints
        constrained_segments = segments[:-1] + [
            self._wrap_with_limit_offset(
                segments[-1],
                limit=limit,
                offset=offset,
                subquery_alias="preview",
                clickhouse_settings={
                    "max_execution_time": PREVIEW_MAX_EXECUTION_TIME,
                    "max_memory_usage": PREVIEW_MAX_MEMORY,
                    "max_rows_to_read": PREVIEW_MAX_ROWS_TO_READ,
                },
            )
        ]

        results = await self._query_router.execute_all(constrained_segments)
        elapsed_ms = (time.monotonic() - start) * 1000

        # Use the last result (the target node's output)
        last_result = results[-1]
        # M8 fix: Use actual column types instead of hardcoded "String"
        columns = self._build_columns_with_types(last_result.columns)
        response = {
            "columns": columns,
            "rows": last_result.rows[:limit],
            "total_estimate": last_result.total_rows,
            "execution_ms": round(elapsed_ms, 2),
            "cache_hit": False,
            "offset": offset,
            "limit": limit,
        }

        # Cache the result (without cache_hit flag)
        await self._cache_set(cache_key, response, CACHE_TTL, cache_type="preview")

        return response

    def _compute_cache_key(
        self,
        tenant_id: UUID,
        target_node_id: str,
        nodes: list[dict],
        edges: list[dict],
        offset: int = 0,
        limit: int = PREVIEW_LIMIT,
    ) -> str:
        """Compute a content-addressed cache key.

        Strips UI-only fields (position, selected, dragging) to avoid
        cache busts on node drag or selection changes.
        Includes tenant_id, offset, and limit so different tenants/pages
        are cached separately.
        """
        ancestors = self._compiler._find_ancestors(target_node_id, edges)
        ancestors.add(target_node_id)

        # Extract only config-relevant fields from ancestor nodes
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
            "offset": offset,
            "limit": limit,
        }
        return self._compute_cache_key_hash(payload)
