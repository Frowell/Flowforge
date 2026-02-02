"""Query router tests — verify correct dispatch to backing stores."""

import pytest

from app.services.query_router import QueryRouter
from app.services.workflow_compiler import CompiledSegment


class TestRouting:
    async def test_clickhouse_target_dispatches_to_clickhouse(self):
        """Analytical queries route to ClickHouse."""
        # TODO: Mock ClickHouseClient, verify it receives the query
        segment = CompiledSegment(
            sql="SELECT * FROM fct_trades",
            dialect="clickhouse",
            target="clickhouse",
            source_node_ids=["node1"],
        )
        # router = QueryRouter(clickhouse=mock_ch)
        # result = await router.execute(segment)
        # assert result.source == "clickhouse"

    async def test_materialize_target_dispatches_to_materialize(self):
        """Live data queries route to Materialize."""
        segment = CompiledSegment(
            sql="SELECT * FROM positions",
            dialect="postgres",
            target="materialize",
            source_node_ids=["node1"],
        )
        # TODO: Mock Materialize client

    async def test_redis_target_dispatches_to_redis(self):
        """Point lookups route to Redis."""
        segment = CompiledSegment(
            sql="",
            dialect="",
            target="redis",
            source_node_ids=["node1"],
            params={"key": "quote:AAPL"},
        )
        # TODO: Mock Redis client

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
