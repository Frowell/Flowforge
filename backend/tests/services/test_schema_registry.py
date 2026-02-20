"""Tests for SchemaRegistry — discovery from ClickHouse, Materialize, and Redis."""

from unittest.mock import AsyncMock, patch

import pytest

from app.schemas.schema import CatalogResponse
from app.services.schema_registry import (
    SchemaRegistry,
    _map_clickhouse_type,
    _map_pg_type,
)


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.setex = AsyncMock()
    return redis


@pytest.fixture
def mock_clickhouse():
    """Mock ClickHouse client that returns system.columns rows."""
    ch = AsyncMock()
    return ch


@pytest.fixture
def mock_materialize():
    """Mock Materialize client that returns mz_columns rows."""
    mz = AsyncMock()
    return mz


# --- ClickHouse type mapping ---


class TestMapClickHouseType:
    def test_string_types(self):
        assert _map_clickhouse_type("String") == "string"
        assert _map_clickhouse_type("FixedString(32)") == "string"
        assert _map_clickhouse_type("UUID") == "string"
        assert _map_clickhouse_type("Enum8('a'=1,'b'=2)") == "string"
        assert _map_clickhouse_type("Enum16('x'=1)") == "string"

    def test_integer_types(self):
        assert _map_clickhouse_type("Int8") == "int64"
        assert _map_clickhouse_type("Int16") == "int64"
        assert _map_clickhouse_type("Int32") == "int64"
        assert _map_clickhouse_type("Int64") == "int64"
        assert _map_clickhouse_type("UInt8") == "int64"
        assert _map_clickhouse_type("UInt16") == "int64"
        assert _map_clickhouse_type("UInt32") == "int64"
        assert _map_clickhouse_type("UInt64") == "int64"

    def test_float_types(self):
        assert _map_clickhouse_type("Float32") == "float64"
        assert _map_clickhouse_type("Float64") == "float64"
        assert _map_clickhouse_type("Decimal(18,4)") == "float64"
        assert _map_clickhouse_type("Decimal32(4)") == "float64"
        assert _map_clickhouse_type("Decimal64(8)") == "float64"
        assert _map_clickhouse_type("Decimal128(18)") == "float64"

    def test_datetime_types(self):
        assert _map_clickhouse_type("DateTime") == "datetime"
        assert _map_clickhouse_type("DateTime64(3)") == "datetime"
        assert _map_clickhouse_type("Date") == "datetime"
        assert _map_clickhouse_type("Date32") == "datetime"

    def test_bool_type(self):
        assert _map_clickhouse_type("Bool") == "bool"

    def test_nullable_wrapping(self):
        assert _map_clickhouse_type("Nullable(String)") == "string"
        assert _map_clickhouse_type("Nullable(Int64)") == "int64"
        assert _map_clickhouse_type("Nullable(Float64)") == "float64"
        assert _map_clickhouse_type("Nullable(DateTime)") == "datetime"
        assert _map_clickhouse_type("Nullable(Bool)") == "bool"

    def test_unknown_type_defaults_to_string(self):
        assert _map_clickhouse_type("Array(String)") == "string"
        assert _map_clickhouse_type("Map(String, Int64)") == "string"


# --- PG type mapping ---


class TestMapPgType:
    def test_string_types(self):
        assert _map_pg_type("text") == "string"
        assert _map_pg_type("varchar") == "string"
        assert _map_pg_type("character varying") == "string"
        assert _map_pg_type("uuid") == "string"

    def test_integer_types(self):
        assert _map_pg_type("integer") == "int64"
        assert _map_pg_type("bigint") == "int64"
        assert _map_pg_type("smallint") == "int64"
        assert _map_pg_type("int4") == "int64"
        assert _map_pg_type("int8") == "int64"

    def test_float_types(self):
        assert _map_pg_type("real") == "float64"
        assert _map_pg_type("double precision") == "float64"
        assert _map_pg_type("numeric") == "float64"

    def test_datetime_types(self):
        assert _map_pg_type("timestamp") == "datetime"
        assert _map_pg_type("timestamptz") == "datetime"
        assert _map_pg_type("timestamp with time zone") == "datetime"
        assert _map_pg_type("date") == "datetime"

    def test_boolean_types(self):
        assert _map_pg_type("boolean") == "bool"
        assert _map_pg_type("bool") == "bool"

    def test_unknown_type_defaults_to_string(self):
        assert _map_pg_type("jsonb") == "string"
        assert _map_pg_type("bytea") == "string"


# --- ClickHouse discovery ---


class TestDiscoverClickHouse:
    async def test_discover_multi_database(self, mock_redis, mock_clickhouse):
        """Tables from all configured databases appear in the catalog."""
        # Mock system.columns responses per database
        db_data = {
            "flowforge": [
                {"table": "raw_trades", "name": "trade_id", "type": "String"},
                {"table": "raw_trades", "name": "price", "type": "Float64"},
            ],
            "metrics": [
                {"table": "vwap_5min", "name": "symbol", "type": "String"},
                {"table": "vwap_5min", "name": "vwap", "type": "Float64"},
            ],
            "marts": [
                {"table": "fct_trades", "name": "trade_id", "type": "String"},
                {"table": "dim_instruments", "name": "symbol", "type": "String"},
            ],
        }

        async def ch_execute(query, params=None):
            db = params["database"] if params else "default"
            return db_data.get(db, [])

        mock_clickhouse.execute = AsyncMock(side_effect=ch_execute)

        registry = SchemaRegistry(
            redis=mock_redis, clickhouse=mock_clickhouse, cache_ttl=300
        )

        with patch("app.services.schema_registry.settings") as mock_settings:
            mock_settings.clickhouse.clickhouse_databases = [
                "flowforge",
                "metrics",
                "marts",
            ]
            tables = await registry._discover_clickhouse()

        assert len(tables) == 4
        table_names = {(t.database, t.name) for t in tables}
        assert ("flowforge", "raw_trades") in table_names
        assert ("metrics", "vwap_5min") in table_names
        assert ("marts", "fct_trades") in table_names
        assert ("marts", "dim_instruments") in table_names

        # All should be source=clickhouse
        for t in tables:
            assert t.source == "clickhouse"

    async def test_discover_clickhouse_column_types(self, mock_redis, mock_clickhouse):
        """ClickHouse column types are mapped correctly."""
        mock_clickhouse.execute = AsyncMock(
            return_value=[
                {"table": "test_table", "name": "id", "type": "UInt64"},
                {"table": "test_table", "name": "name", "type": "Nullable(String)"},
                {"table": "test_table", "name": "price", "type": "Float64"},
                {"table": "test_table", "name": "created_at", "type": "DateTime64(3)"},
                {"table": "test_table", "name": "is_active", "type": "Bool"},
            ]
        )

        registry = SchemaRegistry(
            redis=mock_redis, clickhouse=mock_clickhouse, cache_ttl=300
        )

        with patch("app.services.schema_registry.settings") as mock_settings:
            mock_settings.clickhouse.clickhouse_databases = ["test_db"]
            tables = await registry._discover_clickhouse()

        assert len(tables) == 1
        cols = {c.name: c for c in tables[0].columns}
        assert cols["id"].dtype == "int64"
        assert cols["id"].nullable is False
        assert cols["name"].dtype == "string"
        assert cols["name"].nullable is True
        assert cols["price"].dtype == "float64"
        assert cols["created_at"].dtype == "datetime"
        assert cols["is_active"].dtype == "bool"

    async def test_discover_clickhouse_empty_database(
        self, mock_redis, mock_clickhouse
    ):
        """Empty databases return no tables."""
        mock_clickhouse.execute = AsyncMock(return_value=[])

        registry = SchemaRegistry(
            redis=mock_redis, clickhouse=mock_clickhouse, cache_ttl=300
        )

        with patch("app.services.schema_registry.settings") as mock_settings:
            mock_settings.clickhouse.clickhouse_databases = ["empty_db"]
            tables = await registry._discover_clickhouse()

        assert tables == []


# --- Materialize discovery ---


class TestDiscoverMaterialize:
    async def test_discover_materialize_views(self, mock_redis, mock_materialize):
        """Materialize views appear with source=materialize."""
        mock_materialize.execute = AsyncMock(
            return_value=[
                {
                    "schema_name": "public",
                    "object_name": "live_positions",
                    "column_name": "symbol",
                    "data_type": "text",
                },
                {
                    "schema_name": "public",
                    "object_name": "live_positions",
                    "column_name": "quantity",
                    "data_type": "bigint",
                },
                {
                    "schema_name": "public",
                    "object_name": "live_positions",
                    "column_name": "market_value",
                    "data_type": "double precision",
                },
                {
                    "schema_name": "public",
                    "object_name": "live_quotes",
                    "column_name": "symbol",
                    "data_type": "text",
                },
                {
                    "schema_name": "public",
                    "object_name": "live_quotes",
                    "column_name": "bid_price",
                    "data_type": "numeric",
                },
                {
                    "schema_name": "public",
                    "object_name": "live_quotes",
                    "column_name": "updated_at",
                    "data_type": "timestamp with time zone",
                },
            ]
        )

        registry = SchemaRegistry(
            redis=mock_redis, materialize=mock_materialize, cache_ttl=300
        )
        tables = await registry._discover_materialize()

        assert len(tables) == 2
        names = {t.name for t in tables}
        assert "public.live_positions" in names
        assert "public.live_quotes" in names

        for t in tables:
            assert t.source == "materialize"
            assert t.database == "materialize"

        # Verify column types
        pos = next(t for t in tables if t.name == "public.live_positions")
        cols = {c.name: c for c in pos.columns}
        assert cols["symbol"].dtype == "string"
        assert cols["quantity"].dtype == "int64"
        assert cols["market_value"].dtype == "float64"

        quotes = next(t for t in tables if t.name == "public.live_quotes")
        cols = {c.name: c for c in quotes.columns}
        assert cols["bid_price"].dtype == "float64"
        assert cols["updated_at"].dtype == "datetime"

    async def test_discover_materialize_empty(self, mock_redis, mock_materialize):
        """Empty Materialize returns no tables."""
        mock_materialize.execute = AsyncMock(return_value=[])

        registry = SchemaRegistry(
            redis=mock_redis, materialize=mock_materialize, cache_ttl=300
        )
        tables = await registry._discover_materialize()

        assert tables == []


# --- Redis discovery ---


class TestDiscoverRedisPatterns:
    def test_redis_patterns_included(self):
        """Static Redis key patterns are returned."""
        tables = SchemaRegistry._discover_redis_patterns()

        assert len(tables) == 2
        names = {t.name for t in tables}
        assert "latest:vwap:*" in names
        assert "latest:position:*" in names

        for t in tables:
            assert t.source == "redis"
            assert t.database == "redis"

    def test_redis_vwap_columns(self):
        """VWAP pattern has correct column schema."""
        tables = SchemaRegistry._discover_redis_patterns()
        vwap = next(t for t in tables if t.name == "latest:vwap:*")

        col_names = [c.name for c in vwap.columns]
        assert col_names == ["symbol", "vwap", "volume", "timestamp"]

        cols = {c.name: c for c in vwap.columns}
        assert cols["symbol"].dtype == "string"
        assert cols["vwap"].dtype == "float64"
        assert cols["volume"].dtype == "int64"
        assert cols["timestamp"].dtype == "datetime"

    def test_redis_position_columns(self):
        """Position pattern has correct column schema."""
        tables = SchemaRegistry._discover_redis_patterns()
        pos = next(t for t in tables if t.name == "latest:position:*")

        col_names = [c.name for c in pos.columns]
        expected = ["symbol", "quantity", "avg_price", "market_value", "timestamp"]
        assert col_names == expected

        cols = {c.name: c for c in pos.columns}
        assert cols["quantity"].dtype == "int64"
        assert cols["avg_price"].dtype == "float64"
        assert cols["market_value"].dtype == "float64"


# --- Cache behavior ---


class TestCacheBehavior:
    async def test_cache_hit_returns_cached(self, mock_redis):
        """When Redis has cached catalog, discovery is skipped."""
        cached = CatalogResponse(tables=[])
        mock_redis.get = AsyncMock(return_value=cached.model_dump_json())

        registry = SchemaRegistry(redis=mock_redis, cache_ttl=300)
        result = await registry.get_catalog()

        assert result.tables == []
        mock_redis.setex.assert_not_called()

    async def test_cache_miss_triggers_discovery(self, mock_redis):
        """When Redis cache is empty, discovery runs and result is cached."""
        mock_redis.get = AsyncMock(return_value=None)

        registry = SchemaRegistry(redis=mock_redis, cache_ttl=300)
        result = await registry.get_catalog()

        # Should have called setex to cache the result
        mock_redis.setex.assert_called_once()
        # With no CH or MZ clients, only Redis patterns are discovered,
        # but they are non-empty so mock fallback is NOT used
        assert len(result.tables) == 2  # Redis patterns
        assert all(t.source == "redis" for t in result.tables)

    async def test_force_refresh_bypasses_cache(self, mock_redis):
        """force_refresh=True skips cache even if present."""
        cached = CatalogResponse(tables=[])
        mock_redis.get = AsyncMock(return_value=cached.model_dump_json())

        registry = SchemaRegistry(redis=mock_redis, cache_ttl=300)
        result = await registry.get_catalog(force_refresh=True)

        # Should NOT have called get (or at least should have written new cache)
        mock_redis.setex.assert_called_once()
        # Redis patterns should be in result
        assert len(result.tables) == 2


# --- Fallback behavior ---


class TestFallbackBehavior:
    async def test_fallback_to_mock_when_all_fail(self, mock_redis):
        """When CH, MZ both fail and Redis patterns are somehow empty, mock is used."""
        mock_clickhouse = AsyncMock()
        mock_clickhouse.execute = AsyncMock(side_effect=Exception("CH down"))

        mock_materialize = AsyncMock()
        mock_materialize.execute = AsyncMock(side_effect=Exception("MZ down"))

        registry = SchemaRegistry(
            redis=mock_redis,
            clickhouse=mock_clickhouse,
            materialize=mock_materialize,
            cache_ttl=300,
        )

        # Patch _discover_redis_patterns to return empty to trigger mock fallback
        with patch.object(SchemaRegistry, "_discover_redis_patterns", return_value=[]):
            result = await registry._discover()

        assert len(result.tables) == 4  # Mock catalog has 4 tables
        assert result.tables[0].name == "fct_trades"

    async def test_ch_failure_does_not_block_mz(self, mock_redis, mock_materialize):
        """ClickHouse failure doesn't prevent Materialize discovery."""
        mock_clickhouse = AsyncMock()
        mock_clickhouse.execute = AsyncMock(side_effect=Exception("CH down"))

        mock_materialize.execute = AsyncMock(
            return_value=[
                {
                    "schema_name": "public",
                    "object_name": "live_pnl",
                    "column_name": "account",
                    "data_type": "text",
                },
            ]
        )

        registry = SchemaRegistry(
            redis=mock_redis,
            clickhouse=mock_clickhouse,
            materialize=mock_materialize,
            cache_ttl=300,
        )
        result = await registry._discover()

        # Should have MZ table + Redis patterns
        sources = {t.source for t in result.tables}
        assert "materialize" in sources
        assert "redis" in sources

    async def test_mz_failure_does_not_block_ch(self, mock_redis, mock_clickhouse):
        """Materialize failure doesn't prevent ClickHouse discovery."""
        mock_clickhouse.execute = AsyncMock(
            return_value=[
                {"table": "raw_trades", "name": "id", "type": "UInt64"},
            ]
        )

        mock_materialize = AsyncMock()
        mock_materialize.execute = AsyncMock(side_effect=Exception("MZ down"))

        registry = SchemaRegistry(
            redis=mock_redis,
            clickhouse=mock_clickhouse,
            materialize=mock_materialize,
            cache_ttl=300,
        )

        with patch("app.services.schema_registry.settings") as mock_settings:
            mock_settings.clickhouse.clickhouse_databases = ["flowforge"]
            result = await registry._discover()

        sources = {t.source for t in result.tables}
        assert "clickhouse" in sources
        assert "redis" in sources
