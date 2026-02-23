"""Schema Registry — discovers and caches table/column metadata.

Reads from:
- ClickHouse system.columns
- Materialize mz_catalog
- Redis key patterns

Caches in Redis. Strictly read-only — never creates tables or views.
"""

import logging

from redis.asyncio import Redis

from app.core.clickhouse import ClickHouseClient
from app.core.config import settings
from app.core.metrics import cache_operations_total
from app.schemas.schema import CatalogResponse, ColumnSchema, TableSchema

logger = logging.getLogger(__name__)

CACHE_KEY = "flowforge:schema:catalog"


def _map_clickhouse_type(ch_type: str) -> str:
    """Map a ClickHouse type string to a simplified dtype."""
    t = ch_type.replace("Nullable(", "").rstrip(")")
    if t.startswith("DateTime") or t.startswith("Date"):
        return "datetime"
    if t.startswith("String") or t.startswith("FixedString") or t.startswith("UUID"):
        return "string"
    if t.startswith("Enum"):
        return "string"
    if t.startswith("UInt") or t.startswith("Int"):
        return "int64"
    if t.startswith("Float"):
        return "float64"
    if t.startswith("Decimal"):
        return "float64"
    if t.startswith("Bool"):
        return "bool"
    return "string"


def _map_pg_type(pg_type: str) -> str:
    """Map a PostgreSQL/Materialize type string to a simplified dtype."""
    t = pg_type.lower().strip()
    if t in ("text", "varchar", "character varying", "char", "uuid", "name"):
        return "string"
    if t in (
        "integer",
        "bigint",
        "smallint",
        "int4",
        "int8",
        "int2",
        "serial",
        "bigserial",
    ):
        return "int64"
    if t in ("real", "double precision", "float4", "float8", "numeric", "decimal"):
        return "float64"
    if t in (
        "timestamp",
        "timestamptz",
        "timestamp with time zone",
        "timestamp without time zone",
        "date",
    ):
        return "datetime"
    if t in ("boolean", "bool"):
        return "bool"
    return "string"


class SchemaRegistry:
    def __init__(
        self,
        redis: Redis,
        clickhouse: ClickHouseClient | None = None,
        materialize=None,
        cache_ttl: int = 300,
    ):
        self._redis = redis
        self._clickhouse = clickhouse
        self._materialize = materialize
        self._cache_ttl = cache_ttl

    async def get_catalog(self, force_refresh: bool = False) -> CatalogResponse:
        """Return the full schema catalog, from cache if available."""
        if not force_refresh:
            cached = await self._redis.get(CACHE_KEY)
            if cached:
                cache_operations_total.labels(
                    cache_type="schema", operation="get", status="hit"
                ).inc()
                return CatalogResponse.model_validate_json(cached)
            cache_operations_total.labels(
                cache_type="schema", operation="get", status="miss"
            ).inc()

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

        # Materialize discovery
        if self._materialize:
            try:
                mz_tables = await self._discover_materialize()
                tables.extend(mz_tables)
            except Exception:
                logger.exception("Failed to discover Materialize schemas")

        # Redis key pattern discovery (static, always available)
        tables.extend(self._discover_redis_patterns())

        # Dev-mode fallback: if no tables discovered, use mock catalog
        if not tables:
            logger.warning(
                "Using mock catalog — no tables discovered from backing stores"
            )
            tables = self._mock_catalog()

        return CatalogResponse(tables=tables)

    @staticmethod
    def _mock_catalog() -> list[TableSchema]:
        """Return sample financial tables for development without ClickHouse."""
        return [
            TableSchema(
                name="fct_trades",
                database="default",
                source="clickhouse",
                columns=[
                    ColumnSchema(name="trade_id", dtype="string", nullable=False),
                    ColumnSchema(name="symbol", dtype="string", nullable=False),
                    ColumnSchema(name="side", dtype="string", nullable=False),
                    ColumnSchema(name="quantity", dtype="int64", nullable=False),
                    ColumnSchema(name="price", dtype="float64", nullable=False),
                    ColumnSchema(name="notional", dtype="float64", nullable=False),
                    ColumnSchema(name="trade_time", dtype="datetime", nullable=False),
                    ColumnSchema(name="trader_id", dtype="string", nullable=False),
                ],
            ),
            TableSchema(
                name="fct_quotes",
                database="default",
                source="clickhouse",
                columns=[
                    ColumnSchema(name="symbol", dtype="string", nullable=False),
                    ColumnSchema(name="bid_price", dtype="float64", nullable=False),
                    ColumnSchema(name="ask_price", dtype="float64", nullable=False),
                    ColumnSchema(name="bid_size", dtype="int64", nullable=False),
                    ColumnSchema(name="ask_size", dtype="int64", nullable=False),
                    ColumnSchema(name="quote_time", dtype="datetime", nullable=False),
                ],
            ),
            TableSchema(
                name="dim_positions",
                database="default",
                source="clickhouse",
                columns=[
                    ColumnSchema(name="account_id", dtype="string", nullable=False),
                    ColumnSchema(name="symbol", dtype="string", nullable=False),
                    ColumnSchema(name="quantity", dtype="int64", nullable=False),
                    ColumnSchema(name="avg_price", dtype="float64", nullable=False),
                    ColumnSchema(name="market_value", dtype="float64", nullable=False),
                    ColumnSchema(
                        name="unrealized_pnl", dtype="float64", nullable=False
                    ),
                    ColumnSchema(name="updated_at", dtype="datetime", nullable=False),
                ],
            ),
            TableSchema(
                name="dim_instruments",
                database="default",
                source="clickhouse",
                columns=[
                    ColumnSchema(name="symbol", dtype="string", nullable=False),
                    ColumnSchema(name="name", dtype="string", nullable=False),
                    ColumnSchema(name="sector", dtype="string", nullable=False),
                    ColumnSchema(name="exchange", dtype="string", nullable=False),
                    ColumnSchema(name="currency", dtype="string", nullable=False),
                    ColumnSchema(name="lot_size", dtype="int64", nullable=False),
                ],
            ),
        ]

    async def _discover_clickhouse(self) -> list[TableSchema]:
        """Read table schemas from ClickHouse system.columns."""
        assert self._clickhouse is not None

        databases = settings.clickhouse.clickhouse_databases
        all_tables: list[TableSchema] = []

        for database in databases:
            query = (
                "SELECT table, name, type "
                "FROM system.columns "
                "WHERE database = {database:String} "
                "AND table NOT LIKE '%_mv' "
                "ORDER BY table, position"
            )
            rows = await self._clickhouse.execute(query, {"database": database})

            # Group by table
            grouped: dict[str, list[ColumnSchema]] = {}
            for row in rows:
                table_name = row["table"]
                if table_name not in grouped:
                    grouped[table_name] = []
                grouped[table_name].append(
                    ColumnSchema(
                        name=row["name"],
                        dtype=_map_clickhouse_type(row["type"]),
                        nullable="Nullable" in row["type"],
                    )
                )

            for table_name, columns in grouped.items():
                all_tables.append(
                    TableSchema(
                        name=table_name,
                        database=database,
                        source="clickhouse",
                        columns=columns,
                    )
                )

        return all_tables

    async def _discover_materialize(self) -> list[TableSchema]:
        """Read table schemas from Materialize mz_catalog."""
        assert self._materialize is not None

        query = (
            "SELECT s.name AS schema_name, o.name AS object_name, "
            "c.name AS column_name, c.type_oid::regtype::text AS data_type "
            "FROM mz_columns c "
            "JOIN mz_objects o ON c.id = o.id "
            "JOIN mz_schemas s ON o.schema_id = s.id "
            "WHERE s.name NOT IN "
            "('mz_internal', 'mz_catalog', 'pg_catalog', 'information_schema')"
        )
        rows = await self._materialize.execute(query)

        # Group by (schema_name, object_name)
        grouped: dict[str, list[ColumnSchema]] = {}
        for row in rows:
            key = f"{row['schema_name']}.{row['object_name']}"
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(
                ColumnSchema(
                    name=row["column_name"],
                    dtype=_map_pg_type(row["data_type"]),
                    nullable=True,
                )
            )

        return [
            TableSchema(
                name=name,
                database="materialize",
                source="materialize",
                columns=columns,
            )
            for name, columns in grouped.items()
        ]

    @staticmethod
    def _discover_redis_patterns() -> list[TableSchema]:
        """Return static Redis key pattern schemas."""
        return [
            TableSchema(
                name="latest:vwap:*",
                database="redis",
                source="redis",
                columns=[
                    ColumnSchema(name="symbol", dtype="string", nullable=False),
                    ColumnSchema(name="vwap", dtype="float64", nullable=False),
                    ColumnSchema(name="volume", dtype="int64", nullable=False),
                    ColumnSchema(name="timestamp", dtype="datetime", nullable=False),
                ],
            ),
            TableSchema(
                name="latest:position:*",
                database="redis",
                source="redis",
                columns=[
                    ColumnSchema(name="symbol", dtype="string", nullable=False),
                    ColumnSchema(name="quantity", dtype="int64", nullable=False),
                    ColumnSchema(name="avg_price", dtype="float64", nullable=False),
                    ColumnSchema(name="market_value", dtype="float64", nullable=False),
                    ColumnSchema(name="timestamp", dtype="datetime", nullable=False),
                ],
            ),
        ]
