"""Preview service tests — verify caching, compilation, and tenant isolation."""

import json
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from app.services.preview_service import CACHE_KEY_PREFIX, PreviewService
from app.services.workflow_compiler import CompiledSegment

TENANT_A = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
TENANT_B = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

SAMPLE_NODES = [
    {
        "id": "src",
        "type": "data_source",
        "data": {
            "config": {
                "table": "fct_trades",
                "columns": [
                    {"name": "symbol", "dtype": "string"},
                    {"name": "price", "dtype": "float64"},
                ],
            }
        },
    },
    {
        "id": "out",
        "type": "table_output",
        "data": {"config": {}},
    },
]
SAMPLE_EDGES = [{"source": "src", "target": "out"}]


def _make_service(
    *,
    cache_get_return=None,
    compile_return=None,
    execute_return=None,
) -> tuple[PreviewService, AsyncMock, AsyncMock, AsyncMock]:
    """Create a PreviewService with mocked dependencies."""
    mock_compiler = MagicMock()
    mock_compiler._find_ancestors = MagicMock(return_value={"src"})
    if compile_return is not None:
        mock_compiler.compile_subgraph = MagicMock(return_value=compile_return)
    else:
        mock_compiler.compile_subgraph = MagicMock(
            return_value=[
                CompiledSegment(
                    sql="SELECT symbol, price FROM fct_trades",
                    dialect="clickhouse",
                    target="clickhouse",
                    source_node_ids=["src"],
                )
            ]
        )

    mock_router = AsyncMock()
    if execute_return is not None:
        mock_router.execute_all = AsyncMock(return_value=execute_return)
    else:
        result = MagicMock()
        result.columns = ["symbol", "price"]
        result.rows = [{"symbol": "AAPL", "price": 150.0}]
        result.total_rows = 1
        mock_router.execute_all = AsyncMock(return_value=[result])

    mock_redis = AsyncMock()
    if cache_get_return is not None:
        mock_redis.get = AsyncMock(return_value=json.dumps(cache_get_return))
    else:
        mock_redis.get = AsyncMock(return_value=None)
    mock_redis.set = AsyncMock()

    service = PreviewService(
        compiler=mock_compiler,
        query_router=mock_router,
        redis=mock_redis,
    )
    return service, mock_compiler, mock_router, mock_redis


class TestPreviewExecution:
    @pytest.mark.asyncio
    async def test_preview_compiles_subgraph_and_returns_result(self):
        """Preview compiles the subgraph and returns formatted result."""
        service, mock_compiler, mock_router, mock_redis = _make_service()

        result = await service.execute_preview(
            tenant_id=TENANT_A,
            target_node_id="out",
            nodes=SAMPLE_NODES,
            edges=SAMPLE_EDGES,
        )

        mock_compiler.compile_subgraph.assert_called_once()
        mock_router.execute_all.assert_called_once()
        assert result["cache_hit"] is False
        assert len(result["columns"]) > 0
        assert isinstance(result["rows"], list)
        assert "execution_ms" in result

    @pytest.mark.asyncio
    async def test_preview_empty_segments_returns_empty(self):
        """Preview with no compiled segments returns empty result."""
        service, _, _, _ = _make_service(compile_return=[])

        result = await service.execute_preview(
            tenant_id=TENANT_A,
            target_node_id="out",
            nodes=SAMPLE_NODES,
            edges=SAMPLE_EDGES,
        )

        assert result["columns"] == []
        assert result["rows"] == []
        assert result["cache_hit"] is False


class TestPreviewCaching:
    @pytest.mark.asyncio
    async def test_cache_hit_returns_cached_result(self):
        """When Redis has a cached result, skip compilation."""
        cached_data = {
            "columns": [{"name": "symbol", "dtype": "String"}],
            "rows": [{"symbol": "AAPL"}],
            "total_estimate": 1,
            "execution_ms": 2.0,
            "offset": 0,
            "limit": 100,
        }
        service, mock_compiler, mock_router, _ = _make_service(
            cache_get_return=cached_data
        )

        result = await service.execute_preview(
            tenant_id=TENANT_A,
            target_node_id="out",
            nodes=SAMPLE_NODES,
            edges=SAMPLE_EDGES,
        )

        assert result["cache_hit"] is True
        mock_compiler.compile_subgraph.assert_not_called()
        mock_router.execute_all.assert_not_called()

    @pytest.mark.asyncio
    async def test_cache_miss_executes_query(self):
        """When Redis has no cached result, compile and execute."""
        service, mock_compiler, mock_router, mock_redis = _make_service()

        result = await service.execute_preview(
            tenant_id=TENANT_A,
            target_node_id="out",
            nodes=SAMPLE_NODES,
            edges=SAMPLE_EDGES,
        )

        assert result["cache_hit"] is False
        mock_compiler.compile_subgraph.assert_called_once()
        mock_router.execute_all.assert_called_once()
        # Result should be cached
        mock_redis.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_key_includes_tenant_id(self):
        """Different tenants produce different cache keys."""
        service, _, _, _ = _make_service()

        key_a = service._compute_cache_key(TENANT_A, "out", SAMPLE_NODES, SAMPLE_EDGES)
        key_b = service._compute_cache_key(TENANT_B, "out", SAMPLE_NODES, SAMPLE_EDGES)

        assert key_a != key_b
        assert key_a.startswith(CACHE_KEY_PREFIX)
        assert key_b.startswith(CACHE_KEY_PREFIX)

    @pytest.mark.asyncio
    async def test_same_tenant_same_config_produces_same_key(self):
        """Same tenant + same graph config produces same cache key."""
        service, _, _, _ = _make_service()

        key1 = service._compute_cache_key(TENANT_A, "out", SAMPLE_NODES, SAMPLE_EDGES)
        key2 = service._compute_cache_key(TENANT_A, "out", SAMPLE_NODES, SAMPLE_EDGES)

        assert key1 == key2

    @pytest.mark.asyncio
    async def test_redis_failure_fails_open(self):
        """Redis error during cache read doesn't block preview."""
        service, _, _, mock_redis = _make_service()
        mock_redis.get = AsyncMock(side_effect=ConnectionError("Redis down"))

        result = await service.execute_preview(
            tenant_id=TENANT_A,
            target_node_id="out",
            nodes=SAMPLE_NODES,
            edges=SAMPLE_EDGES,
        )

        # Should still return a result despite cache error
        assert result["cache_hit"] is False
        assert "columns" in result
