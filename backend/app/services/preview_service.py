"""Preview Service — executes constrained preview queries with caching.

Layer 2: Content-addressed Redis cache (keyed on node config, not position).
Layer 3: Query constraints (LIMIT, max_execution_time, max_memory_usage).
"""

import hashlib
import json
import logging
import time
from uuid import UUID

from redis.asyncio import Redis

from app.core.metrics import cache_operations_total
from app.services.query_router import QueryRouter
from app.services.workflow_compiler import CompiledSegment, WorkflowCompiler

logger = logging.getLogger(__name__)

# Preview constraints
PREVIEW_LIMIT = 100
PREVIEW_HARD_CAP = 10_000
CACHE_TTL = 300  # 5 minutes
PREVIEW_MAX_EXECUTION_TIME = 3
PREVIEW_MAX_MEMORY = 100_000_000
PREVIEW_MAX_ROWS_TO_READ = 10_000_000

CACHE_KEY_PREFIX = "flowforge:preview:"


class PreviewService:
    """Executes preview queries with caching and resource constraints."""

    def __init__(
        self,
        compiler: WorkflowCompiler,
        query_router: QueryRouter,
        redis: Redis,
    ):
        self._compiler = compiler
        self._query_router = query_router
        self._redis = redis

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
        cached = await self._cache_get(cache_key)
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
            self._wrap_with_constraints(segments[-1], limit=limit, offset=offset)
        ]

        results = await self._query_router.execute_all(constrained_segments)
        elapsed_ms = (time.monotonic() - start) * 1000

        # Use the last result (the target node's output)
        last_result = results[-1]
        columns = [{"name": col, "dtype": "String"} for col in last_result.columns]
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
        await self._cache_set(cache_key, response)

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

        payload = json.dumps(
            {
                "tenant_id": str(tenant_id),
                "target": target_node_id,
                "nodes": stable_nodes,
                "edges": stable_edges,
                "offset": offset,
                "limit": limit,
            },
            sort_keys=True,
        )
        digest = hashlib.sha256(payload.encode()).hexdigest()[:16]
        return f"{CACHE_KEY_PREFIX}{digest}"

    def _wrap_with_constraints(
        self,
        segment: CompiledSegment,
        limit: int = PREVIEW_LIMIT,
        offset: int = 0,
    ) -> CompiledSegment:
        """Wrap a segment's SQL with LIMIT, OFFSET, and SETTINGS."""
        constrained_sql = (
            f"SELECT * FROM ({segment.sql}) AS preview "
            f"LIMIT {limit} OFFSET {offset} "
            f"SETTINGS max_execution_time={PREVIEW_MAX_EXECUTION_TIME}, "
            f"max_memory_usage={PREVIEW_MAX_MEMORY}, "
            f"max_rows_to_read={PREVIEW_MAX_ROWS_TO_READ}"
        )
        return CompiledSegment(
            sql=constrained_sql,
            dialect=segment.dialect,
            target=segment.target,
            source_node_ids=segment.source_node_ids,
            params=segment.params,
            limit=limit,
            offset=offset,
        )

    async def _cache_get(self, key: str) -> dict | None:
        """Read from Redis cache. Returns None on miss or error."""
        try:
            raw = await self._redis.get(key)
            if raw is not None:
                cache_operations_total.labels(
                    cache_type="preview", operation="get", status="hit"
                ).inc()
                return json.loads(raw)
            cache_operations_total.labels(
                cache_type="preview", operation="get", status="miss"
            ).inc()
        except Exception:
            cache_operations_total.labels(
                cache_type="preview", operation="get", status="error"
            ).inc()
            logger.warning("Preview cache read failed for key %s", key, exc_info=True)
        return None

    async def _cache_set(self, key: str, value: dict) -> None:
        """Write to Redis cache with TTL. Errors are logged, never raised."""
        try:
            await self._redis.set(key, json.dumps(value), ex=CACHE_TTL)
            cache_operations_total.labels(
                cache_type="preview", operation="set", status="hit"
            ).inc()
        except Exception:
            cache_operations_total.labels(
                cache_type="preview", operation="set", status="error"
            ).inc()
            logger.warning("Preview cache write failed for key %s", key, exc_info=True)
