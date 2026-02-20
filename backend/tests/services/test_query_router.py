"""Query router tests — verify correct dispatch to backing stores."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.query_router import QueryResult, QueryRouter
from app.services.workflow_compiler import CompiledSegment


class TestRouting:
    async def test_clickhouse_target_dispatches_to_clickhouse(self):
        """Analytical queries route to ClickHouse and return QueryResult."""
        mock_ch = MagicMock()
        mock_ch.execute = AsyncMock(
            return_value=[
                {"trade_id": "t1", "symbol": "AAPL", "price": 150.0},
                {"trade_id": "t2", "symbol": "GOOG", "price": 2800.0},
            ]
        )

        router = QueryRouter(clickhouse=mock_ch)
        segment = CompiledSegment(
            sql="SELECT trade_id, symbol, price FROM fct_trades LIMIT 10",
            dialect="clickhouse",
            target="clickhouse",
            source_node_ids=["node1"],
        )
        result = await router.execute(segment)

        assert isinstance(result, QueryResult)
        assert result.source == "clickhouse"
        assert result.total_rows == 2
        assert result.columns == ["trade_id", "symbol", "price"]
        assert len(result.rows) == 2
        mock_ch.execute.assert_awaited_once_with(segment.sql, segment.params)

    async def test_clickhouse_empty_result(self):
        """ClickHouse returning empty rows produces empty QueryResult."""
        mock_ch = MagicMock()
        mock_ch.execute = AsyncMock(return_value=[])

        router = QueryRouter(clickhouse=mock_ch)
        segment = CompiledSegment(
            sql="SELECT * FROM fct_trades WHERE 1=0",
            dialect="clickhouse",
            target="clickhouse",
            source_node_ids=["node1"],
        )
        result = await router.execute(segment)

        assert result.source == "clickhouse"
        assert result.total_rows == 0
        assert result.columns == []
        assert result.rows == []

    async def test_clickhouse_not_configured_raises(self):
        """ClickHouse target without client raises RuntimeError."""
        router = QueryRouter(clickhouse=None)
        segment = CompiledSegment(
            sql="SELECT 1",
            dialect="clickhouse",
            target="clickhouse",
            source_node_ids=["node1"],
        )
        with pytest.raises(RuntimeError, match="ClickHouse client not configured"):
            await router.execute(segment)

    async def test_materialize_target_dispatches_to_materialize(self):
        """Live data queries route to Materialize and return QueryResult."""
        mock_mz = MagicMock()
        mock_mz.execute = AsyncMock(return_value=[{"symbol": "AAPL", "position": 100}])
        router = QueryRouter(materialize=mock_mz)
        segment = CompiledSegment(
            sql="SELECT * FROM positions",
            dialect="postgres",
            target="materialize",
            source_node_ids=["node1"],
        )
        result = await router.execute(segment)
        assert result.source == "materialize"
        assert result.total_rows == 1

    async def test_materialize_not_configured_raises(self):
        """Materialize target without client raises RuntimeError."""
        router = QueryRouter()
        segment = CompiledSegment(
            sql="SELECT * FROM positions",
            dialect="postgres",
            target="materialize",
            source_node_ids=["node1"],
        )
        with pytest.raises(RuntimeError, match="Materialize client not configured"):
            await router.execute(segment)

    async def test_redis_target_dispatches_to_redis(self):
        """Point lookups route to Redis and return QueryResult."""
        mock_redis = MagicMock()
        mock_redis.get = AsyncMock(return_value='{"symbol": "AAPL", "price": 150.0}')
        router = QueryRouter(redis=mock_redis)
        segment = CompiledSegment(
            sql="",
            dialect="",
            target="redis",
            source_node_ids=["node1"],
            params={"key": "quote:AAPL"},
        )
        result = await router.execute(segment)
        assert result.source == "redis"
        assert result.total_rows == 1
        assert result.rows[0]["symbol"] == "AAPL"

    async def test_redis_not_configured_raises(self):
        """Redis target without client raises RuntimeError."""
        router = QueryRouter()
        segment = CompiledSegment(
            sql="",
            dialect="",
            target="redis",
            source_node_ids=["node1"],
            params={"key": "quote:AAPL"},
        )
        with pytest.raises(RuntimeError, match="Redis client not configured"):
            await router.execute(segment)

    async def test_unknown_target_raises(self):
        """Unknown target raises ValueError."""
        router = QueryRouter()
        segment = CompiledSegment(
            sql="SELECT 1",
            dialect="clickhouse",
            target="unknown_store",
            source_node_ids=["node1"],
        )
        with pytest.raises(ValueError, match="Unknown target"):
            await router.execute(segment)


class TestTimeouts:
    """Test query timeout enforcement for ClickHouse and Materialize."""

    @patch("app.services.query_router.settings")
    async def test_clickhouse_timeout_raises(self, mock_settings):
        """ClickHouse query exceeding timeout raises TimeoutError."""
        mock_settings.clickhouse_query_timeout = 1

        async def slow_query(*args, **kwargs):
            await asyncio.sleep(2)
            return [{"result": "never reached"}]

        mock_ch = MagicMock()
        mock_ch.execute = slow_query
        router = QueryRouter(clickhouse=mock_ch)
        segment = CompiledSegment(
            sql="SELECT * FROM large_table",
            dialect="clickhouse",
            target="clickhouse",
            source_node_ids=["node1"],
        )
        with pytest.raises(TimeoutError, match="ClickHouse query exceeded timeout"):
            await router.execute(segment)

    @patch("app.services.query_router.settings")
    async def test_clickhouse_fast_query_succeeds(self, mock_settings):
        """ClickHouse query completing within timeout succeeds."""
        mock_settings.clickhouse_query_timeout = 5

        async def fast_query(*args, **kwargs):
            await asyncio.sleep(0.1)
            return [{"symbol": "AAPL"}]

        mock_ch = MagicMock()
        mock_ch.execute = fast_query
        router = QueryRouter(clickhouse=mock_ch)
        segment = CompiledSegment(
            sql="SELECT * FROM quick_table",
            dialect="clickhouse",
            target="clickhouse",
            source_node_ids=["node1"],
        )
        result = await router.execute(segment)
        assert result.source == "clickhouse"
        assert result.total_rows == 1

    @patch("app.services.query_router.settings")
    async def test_materialize_timeout_raises(self, mock_settings):
        """Materialize query exceeding timeout raises TimeoutError."""
        mock_settings.materialize_query_timeout = 1

        async def slow_query(*args, **kwargs):
            await asyncio.sleep(2)
            return [{"result": "never reached"}]

        mock_mz = MagicMock()
        mock_mz.execute = slow_query
        router = QueryRouter(materialize=mock_mz)
        segment = CompiledSegment(
            sql="SELECT * FROM live_positions",
            dialect="postgres",
            target="materialize",
            source_node_ids=["node1"],
        )
        with pytest.raises(TimeoutError, match="Materialize query exceeded timeout"):
            await router.execute(segment)

    @patch("app.services.query_router.settings")
    async def test_materialize_fast_query_succeeds(self, mock_settings):
        """Materialize query completing within timeout succeeds."""
        mock_settings.materialize_query_timeout = 5

        async def fast_query(*args, **kwargs):
            await asyncio.sleep(0.1)
            return [{"symbol": "AAPL", "position": 100}]

        mock_mz = MagicMock()
        mock_mz.execute = fast_query
        router = QueryRouter(materialize=mock_mz)
        segment = CompiledSegment(
            sql="SELECT * FROM live_positions",
            dialect="postgres",
            target="materialize",
            source_node_ids=["node1"],
        )
        result = await router.execute(segment)
        assert result.source == "materialize"
        assert result.total_rows == 1


class TestRedisPipelining:
    """Test Redis SCAN_HASH with key limits and pipelining."""

    @patch("app.services.query_router.settings")
    async def test_redis_scan_hash_respects_key_limit(self, mock_settings):
        """SCAN_HASH stops at configured key limit."""
        mock_settings.redis_scan_limit = 50
        mock_settings.redis_pipeline_batch_size = 10

        # Simulate SCAN returning 100 keys total
        mock_redis = MagicMock()
        scan_results = [
            (1, [f"latest:vwap:SYM{i:03d}" for i in range(25)]),
            (2, [f"latest:vwap:SYM{i:03d}" for i in range(25, 50)]),
            (3, [f"latest:vwap:SYM{i:03d}" for i in range(50, 75)]),
            (0, [f"latest:vwap:SYM{i:03d}" for i in range(75, 100)]),
        ]
        mock_redis.scan = AsyncMock(side_effect=scan_results)

        # Mock pipeline
        mock_pipeline = MagicMock()
        mock_pipeline.execute = AsyncMock(return_value=[{"price": "150.0"}] * 10)
        mock_redis.pipeline.return_value = mock_pipeline

        router = QueryRouter(redis=mock_redis)
        segment = CompiledSegment(
            sql="",
            dialect="",
            target="redis",
            source_node_ids=["node1"],
            params={"lookup_type": "SCAN_HASH", "pattern": "latest:vwap:*"},
        )
        result = await router.execute(segment)

        # Should process only 50 keys, not all 100
        assert result.total_rows == 50
        # 50 keys / 10 per batch = 5 pipeline calls
        assert mock_pipeline.execute.await_count == 5

    @patch("app.services.query_router.settings")
    async def test_redis_scan_hash_uses_pipelining(self, mock_settings):
        """SCAN_HASH batches HGETALL calls via pipeline."""
        mock_settings.redis_scan_limit = 1000
        mock_settings.redis_pipeline_batch_size = 5

        mock_redis = MagicMock()
        # SCAN returns 15 keys total (3 batches of 5)
        mock_redis.scan = AsyncMock(
            return_value=(0, [f"latest:vwap:SYM{i}" for i in range(15)])
        )

        # Mock pipeline
        mock_pipeline = MagicMock()
        mock_pipeline.execute = AsyncMock(
            return_value=[{"price": f"{i}.0"} for i in range(5)]
        )
        mock_redis.pipeline.return_value = mock_pipeline

        router = QueryRouter(redis=mock_redis)
        segment = CompiledSegment(
            sql="",
            dialect="",
            target="redis",
            source_node_ids=["node1"],
            params={"lookup_type": "SCAN_HASH", "pattern": "latest:vwap:*"},
        )
        result = await router.execute(segment)

        # 15 keys / 5 per batch = 3 pipeline calls
        assert mock_pipeline.execute.await_count == 3
        assert result.total_rows == 15

    @patch("app.services.query_router.settings")
    async def test_redis_scan_hash_extracts_symbol_from_key(self, mock_settings):
        """SCAN_HASH correctly extracts symbol from key name."""
        mock_settings.redis_scan_limit = 1000
        mock_settings.redis_pipeline_batch_size = 10

        mock_redis = MagicMock()
        mock_redis.scan = AsyncMock(
            return_value=(0, ["latest:vwap:AAPL", "latest:vwap:GOOG"])
        )

        # Mock pipeline
        mock_pipeline = MagicMock()
        mock_pipeline.execute = AsyncMock(
            return_value=[
                {"price": "150.0", "volume": "1000"},
                {"price": "2800.0", "volume": "500"},
            ]
        )
        mock_redis.pipeline.return_value = mock_pipeline

        router = QueryRouter(redis=mock_redis)
        segment = CompiledSegment(
            sql="",
            dialect="",
            target="redis",
            source_node_ids=["node1"],
            params={"lookup_type": "SCAN_HASH", "pattern": "latest:vwap:*"},
        )
        result = await router.execute(segment)

        assert result.total_rows == 2
        # Check symbol extraction
        symbols = {row["symbol"] for row in result.rows}
        assert symbols == {"AAPL", "GOOG"}

    @patch("app.services.query_router.settings")
    async def test_redis_scan_hash_handles_empty_hashes(self, mock_settings):
        """SCAN_HASH skips keys with empty hash data."""
        mock_settings.redis_scan_limit = 1000
        mock_settings.redis_pipeline_batch_size = 10

        mock_redis = MagicMock()
        mock_redis.scan = AsyncMock(
            return_value=(0, ["latest:vwap:AAPL", "latest:vwap:EMPTY"])
        )

        # Mock pipeline — second hash is empty
        mock_pipeline = MagicMock()
        mock_pipeline.execute = AsyncMock(return_value=[{"price": "150.0"}, {}])
        mock_redis.pipeline.return_value = mock_pipeline

        router = QueryRouter(redis=mock_redis)
        segment = CompiledSegment(
            sql="",
            dialect="",
            target="redis",
            source_node_ids=["node1"],
            params={"lookup_type": "SCAN_HASH", "pattern": "latest:vwap:*"},
        )
        result = await router.execute(segment)

        # Only one non-empty hash
        assert result.total_rows == 1
        assert result.rows[0]["symbol"] == "AAPL"
