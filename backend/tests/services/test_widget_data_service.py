"""Tests for WidgetDataService — content-addressed caching for widget data.

Run: pytest backend/tests/services/test_widget_data_service.py -v --noconftest
"""

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

# Ensure backend is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.query_router import QueryResult
from app.services.widget_data_service import WidgetDataService
from app.services.workflow_compiler import CompiledSegment, WorkflowCompiler

# ── Fixtures ──────────────────────────────────────────────────────────────


def _make_graph(target: str = "clickhouse"):
    """Minimal graph with one data_source node."""
    return {
        "nodes": [
            {
                "id": "node_1",
                "type": "data_source",
                "data": {"config": {"table": "trades"}},
            }
        ],
        "edges": [],
    }


def _make_service(
    redis_get_return=None,
    compile_segments=None,
    execute_results=None,
    redis_fail=False,
):
    """Build a WidgetDataService with mocked dependencies."""
    compiler = MagicMock(spec=WorkflowCompiler)
    compiler._find_ancestors = MagicMock(return_value=set())

    if compile_segments is None:
        compile_segments = [
            CompiledSegment(
                sql="SELECT * FROM trades",
                dialect="clickhouse",
                target="clickhouse",
                source_node_ids=["node_1"],
            )
        ]
    compiler.compile_subgraph = MagicMock(return_value=compile_segments)

    query_router = AsyncMock()
    if execute_results is None:
        execute_results = [
            QueryResult(
                columns=["id", "price"],
                rows=[{"id": 1, "price": 100.0}],
                total_rows=1,
                source="clickhouse",
            )
        ]
    query_router.execute_all = AsyncMock(return_value=execute_results)

    redis = AsyncMock()
    if redis_fail:
        redis.get = AsyncMock(side_effect=ConnectionError("Redis down"))
        redis.set = AsyncMock(side_effect=ConnectionError("Redis down"))
    else:
        if redis_get_return is not None:
            redis.get = AsyncMock(return_value=json.dumps(redis_get_return))
        else:
            redis.get = AsyncMock(return_value=None)

    return WidgetDataService(compiler=compiler, query_router=query_router, redis=redis)


# ── Tests ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cache_hit_returns_cached_data():
    """Cache hit returns cached data without compiling or executing."""
    cached_data = {
        "columns": [{"name": "id", "dtype": "String"}],
        "rows": [{"id": 1}],
        "total_rows": 1,
        "execution_ms": 5.0,
        "cache_hit": False,
        "offset": 0,
        "limit": 10000,
    }
    svc = _make_service(redis_get_return=cached_data)

    result = await svc.fetch_widget_data(
        tenant_id=uuid4(),
        source_node_id="node_1",
        graph_json=_make_graph(),
    )

    assert result["cache_hit"] is True
    assert result["rows"] == [{"id": 1}]
    # Compiler and query router should NOT have been called
    svc._compiler.compile_subgraph.assert_not_called()
    svc._query_router.execute_all.assert_not_called()


@pytest.mark.asyncio
async def test_cache_miss_compiles_and_executes():
    """Cache miss compiles subgraph and executes queries."""
    svc = _make_service()

    result = await svc.fetch_widget_data(
        tenant_id=uuid4(),
        source_node_id="node_1",
        graph_json=_make_graph(),
    )

    assert result["cache_hit"] is False
    assert result["total_rows"] == 1
    assert len(result["columns"]) == 2
    svc._compiler.compile_subgraph.assert_called_once()
    svc._query_router.execute_all.assert_called_once()


@pytest.mark.asyncio
async def test_different_config_overrides_produce_different_cache_keys():
    """Different config_overrides should produce different cache keys."""
    svc = _make_service()
    tenant_id = uuid4()
    graph = _make_graph()
    nodes = graph["nodes"]
    edges = graph["edges"]

    import copy

    nodes_a = copy.deepcopy(nodes)
    nodes_b = copy.deepcopy(nodes)

    key_a = svc._compute_cache_key(
        tenant_id,
        "node_1",
        nodes_a,
        edges,
        {"filter": "A"},
        {},
        0,
        10000,
    )
    key_b = svc._compute_cache_key(
        tenant_id,
        "node_1",
        nodes_b,
        edges,
        {"filter": "B"},
        {},
        0,
        10000,
    )

    assert key_a != key_b


@pytest.mark.asyncio
async def test_same_inputs_produce_same_cache_key():
    """Identical inputs should produce the same cache key (dedup)."""
    svc = _make_service()
    tenant_id = uuid4()
    graph = _make_graph()
    nodes = graph["nodes"]
    edges = graph["edges"]

    key_1 = svc._compute_cache_key(
        tenant_id,
        "node_1",
        nodes,
        edges,
        {"x": 1},
        {},
        0,
        100,
    )
    key_2 = svc._compute_cache_key(
        tenant_id,
        "node_1",
        nodes,
        edges,
        {"x": 1},
        {},
        0,
        100,
    )

    assert key_1 == key_2


@pytest.mark.asyncio
async def test_ttl_varies_by_segment_target():
    """Materialize segments get shorter TTL than ClickHouse."""
    svc = _make_service()

    assert svc._ttl_for_target("materialize") == 30
    assert svc._ttl_for_target("clickhouse") == 300


@pytest.mark.asyncio
async def test_redis_failure_fails_open():
    """Redis errors should not prevent data from being returned."""
    svc = _make_service(redis_fail=True)

    result = await svc.fetch_widget_data(
        tenant_id=uuid4(),
        source_node_id="node_1",
        graph_json=_make_graph(),
    )

    # Should still return data despite Redis being down
    assert result["cache_hit"] is False
    assert result["total_rows"] == 1
