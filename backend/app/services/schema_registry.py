"""Schema Registry — discovers and caches table/column metadata.

Reads from:
- ClickHouse system.columns
- Materialize mz_catalog
- Redis key patterns

Caches in Redis. Strictly read-only — never creates tables or views.
"""

import json
import logging

from redis.asyncio import Redis

from app.core.clickhouse import ClickHouseClient
from app.core.metrics import cache_operations_total
from app.schemas.schema import CatalogResponse, ColumnSchema, TableSchema

logger = logging.getLogger(__name__)

CACHE_KEY = "flowforge:schema:catalog"


class SchemaRegistry:
    def __init__(
        self,
        redis: Redis,
        clickhouse: ClickHouseClient | None = None,
        cache_ttl: int = 300,
    ):
        self._redis = redis
        self._clickhouse = clickhouse
        self._cache_ttl = cache_ttl

    async def get_catalog(self, force_refresh: bool = False) -> CatalogResponse:
        """Return the full schema catalog, from cache if available."""
        if not force_refresh:
            cached = await self._redis.get(CACHE_KEY)
            if cached:
                cache_operations_total.labels(cache_type="schema", operation="get", status="hit").inc()
                return CatalogResponse.model_validate_json(cached)
            cache_operations_total.labels(cache_type="schema", operation="get", status="miss").inc()

        catalog = await self._discover()
        await self._redis.setex(
            CACHE_KEY,
            self._cache_ttl,
            catalog.model_dump_json(),
        )
        return catalog

    async def refresh(self) -> CatalogResponse:
        """Force a cache refresh."""
        return await self.get_catalog(force_refresh=True)

    async def _discover(self) -> CatalogResponse:
        """Query backing stores for schema metadata."""
        tables: list[TableSchema] = []

        # ClickHouse discovery
        if self._clickhouse:
            try:
                ch_tables = await self._discover_clickhouse()
                tables.extend(ch_tables)
            except Exception:
                logger.exception("Failed to discover ClickHouse schemas")

        # TODO: Materialize discovery via mz_catalog
        # TODO: Redis key pattern discovery

        return CatalogResponse(tables=tables)

    async def _discover_clickhouse(self) -> list[TableSchema]:
        """Read table schemas from ClickHouse system.columns."""
        assert self._clickhouse is not None

        # TODO: Query system.columns, group by table, build TableSchema objects
        # query = """
        #     SELECT table, name, type, comment
        #     FROM system.columns
        #     WHERE database = {database:String}
        #     ORDER BY table, position
        # """
        return []
