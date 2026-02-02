"""Query router tests — verify correct dispatch to backing stores."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.query_router import QueryRouter, QueryResult
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
        """Live data queries route to Materialize (not yet implemented)."""
        router = QueryRouter()
        segment = CompiledSegment(
            sql="SELECT * FROM positions",
            dialect="postgres",
            target="materialize",
            source_node_ids=["node1"],
        )
        with pytest.raises(NotImplementedError):
            await router.execute(segment)

    async def test_redis_target_dispatches_to_redis(self):
        """Point lookups route to Redis (not yet implemented)."""
        mock_redis = MagicMock()
        router = QueryRouter(redis=mock_redis)
        segment = CompiledSegment(
            sql="",
            dialect="",
            target="redis",
            source_node_ids=["node1"],
            params={"key": "quote:AAPL"},
        )
        with pytest.raises(NotImplementedError):
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
