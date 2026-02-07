"""Tests for preview cache key computation and invalidation behavior."""

import pytest
from unittest.mock import MagicMock
from uuid import uuid4, UUID

from app.services.preview_service import PreviewService, CACHE_KEY_PREFIX, CACHE_TTL

# Fixtures for consistent test data
TENANT_A = uuid4()
TENANT_B = uuid4()


def make_preview_service():
    """Create a PreviewService with mocked dependencies."""
    compiler = MagicMock()
    # _find_ancestors returns the set of ancestor node IDs
    compiler._find_ancestors.return_value = {"src"}
    query_router = MagicMock()
    redis = MagicMock()
    return PreviewService(compiler=compiler, query_router=query_router, redis=redis)


NODES = [
    {
        "id": "src",
        "type": "data_source",
        "data": {"config": {"table": "trades"}},
    },
    {
        "id": "flt",
        "type": "filter",
        "data": {"config": {"column": "symbol", "operator": "=", "value": "AAPL"}},
    },
]
EDGES = [{"source": "src", "target": "flt"}]


class TestPreviewCacheKey:
    """Tests for _compute_cache_key behavior and invalidation semantics."""

    def test_config_change_produces_different_key(self):
        """Changing a node config value must produce a different cache key."""
        svc = make_preview_service()
        key1 = svc._compute_cache_key(TENANT_A, "flt", NODES, EDGES)

        modified_nodes = [
            {
                "id": "src",
                "type": "data_source",
                "data": {"config": {"table": "trades"}},
            },
            {
                "id": "flt",
                "type": "filter",
                "data": {
                    "config": {
                        "column": "symbol",
                        "operator": "=",
                        "value": "MSFT",
                    }
                },
            },
        ]
        svc._compiler._find_ancestors.return_value = {"src"}
        key2 = svc._compute_cache_key(TENANT_A, "flt", modified_nodes, EDGES)

        assert key1 != key2

    def test_position_change_produces_same_key(self):
        """UI-only fields (position, selected, dragging) must not affect the cache key."""
        svc = make_preview_service()
        key1 = svc._compute_cache_key(TENANT_A, "flt", NODES, EDGES)

        nodes_with_position = [
            {
                "id": "src",
                "type": "data_source",
                "data": {"config": {"table": "trades"}},
                "position": {"x": 100, "y": 200},
                "selected": True,
            },
            {
                "id": "flt",
                "type": "filter",
                "data": {
                    "config": {
                        "column": "symbol",
                        "operator": "=",
                        "value": "AAPL",
                    }
                },
                "position": {"x": 300, "y": 400},
                "dragging": True,
            },
        ]
        key2 = svc._compute_cache_key(TENANT_A, "flt", nodes_with_position, EDGES)

        assert key1 == key2

    def test_different_tenant_produces_different_key(self):
        """Different tenants must produce different cache keys for identical graphs."""
        svc = make_preview_service()
        key1 = svc._compute_cache_key(TENANT_A, "flt", NODES, EDGES)
        key2 = svc._compute_cache_key(TENANT_B, "flt", NODES, EDGES)

        assert key1 != key2

    def test_different_offset_produces_different_key(self):
        """Different offsets must produce different cache keys."""
        svc = make_preview_service()
        key1 = svc._compute_cache_key(TENANT_A, "flt", NODES, EDGES, offset=0, limit=100)
        key2 = svc._compute_cache_key(TENANT_A, "flt", NODES, EDGES, offset=100, limit=100)

        assert key1 != key2

    def test_different_limit_produces_different_key(self):
        """Different limits must produce different cache keys."""
        svc = make_preview_service()
        key1 = svc._compute_cache_key(TENANT_A, "flt", NODES, EDGES, offset=0, limit=50)
        key2 = svc._compute_cache_key(TENANT_A, "flt", NODES, EDGES, offset=0, limit=100)

        assert key1 != key2

    def test_cache_key_has_correct_prefix(self):
        """Cache keys must start with the standard prefix."""
        svc = make_preview_service()
        key = svc._compute_cache_key(TENANT_A, "flt", NODES, EDGES)

        assert key.startswith(CACHE_KEY_PREFIX)

    def test_cache_ttl_is_five_minutes(self):
        """Verify that CACHE_TTL is 300 seconds (5 minutes)."""
        assert CACHE_TTL == 300
