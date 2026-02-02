"""Multi-tenancy tests — verify tenant isolation across models and auth."""

import uuid

import pytest
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from starlette.requests import Request

from app.core.auth import get_current_tenant_id, get_current_user_id
from app.core.database import TenantMixin
from app.models.user import User
from app.models.workflow import Workflow
from app.models.dashboard import Dashboard, APIKey, Widget, DashboardFilter


# ── TenantMixin Tests ────────────────────────────────────────────────────


class TestTenantMixin:
    """Verify TenantMixin is applied correctly to tenant-scoped models."""

    def test_user_has_tenant_id_column(self):
        assert hasattr(User, "tenant_id")

    def test_workflow_has_tenant_id_column(self):
        assert hasattr(Workflow, "tenant_id")

    def test_dashboard_has_tenant_id_column(self):
        assert hasattr(Dashboard, "tenant_id")

    def test_api_key_has_tenant_id_column(self):
        assert hasattr(APIKey, "tenant_id")

    def test_widget_does_not_have_tenant_id_column(self):
        """Widget inherits tenant from its parent Dashboard — no own column."""
        # Widget should NOT have TenantMixin in its MRO
        assert not issubclass(Widget, TenantMixin)

    def test_dashboard_filter_does_not_have_tenant_id_column(self):
        """DashboardFilter inherits tenant from its parent Dashboard."""
        assert not issubclass(DashboardFilter, TenantMixin)

    def test_tenant_mixin_column_is_not_nullable(self):
        """The tenant_id column must be NOT NULL."""
        col = Workflow.__table__.columns["tenant_id"]
        assert col.nullable is False

    def test_tenant_mixin_column_is_indexed(self):
        """The tenant_id column must be indexed for query performance."""
        col = Workflow.__table__.columns["tenant_id"]
        assert col.index is True


# ── Auth Dependency Tests ────────────────────────────────────────────────


def _make_request(headers: dict | None = None) -> Request:
    """Create a minimal Starlette request with given headers."""
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [
            (k.lower().encode(), v.encode())
            for k, v in (headers or {}).items()
        ],
    }
    return Request(scope)


class TestGetCurrentTenantId:
    """Verify get_current_tenant_id extracts tenant from JWT."""

    @pytest.mark.asyncio
    async def test_missing_auth_header_returns_401(self):
        request = _make_request()
        with patch("app.core.auth.settings") as mock_settings:
            mock_settings.app_env = "production"
            with pytest.raises(HTTPException) as exc_info:
                await get_current_tenant_id(request)
            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_bearer_prefix_returns_401(self):
        request = _make_request({"Authorization": "Basic abc123"})
        with patch("app.core.auth.settings") as mock_settings:
            mock_settings.app_env = "production"
            with pytest.raises(HTTPException) as exc_info:
                await get_current_tenant_id(request)
            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_missing_tenant_id_claim_returns_403(self):
        """A valid token without tenant_id claim should be rejected."""
        with patch("app.core.auth._decode_token", new_callable=AsyncMock) as mock_decode:
            mock_decode.return_value = {"sub": str(uuid.uuid4()), "email": "a@b.com"}
            request = _make_request({"Authorization": "Bearer valid-token"})
            with pytest.raises(HTTPException) as exc_info:
                await get_current_tenant_id(request)
            assert exc_info.value.status_code == 403
            assert "tenant_id" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_valid_tenant_id_claim_returns_uuid(self):
        tenant_uuid = uuid.uuid4()
        with patch("app.core.auth._decode_token", new_callable=AsyncMock) as mock_decode:
            mock_decode.return_value = {
                "sub": str(uuid.uuid4()),
                "tenant_id": str(tenant_uuid),
            }
            request = _make_request({"Authorization": "Bearer valid-token"})
            result = await get_current_tenant_id(request)
            assert result == tenant_uuid


class TestGetCurrentUserId:
    """Verify get_current_user_id extracts user from JWT."""

    @pytest.mark.asyncio
    async def test_missing_auth_header_returns_401(self):
        request = _make_request()
        with patch("app.core.auth.settings") as mock_settings:
            mock_settings.app_env = "production"
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user_id(request)
            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_missing_sub_claim_returns_401(self):
        with patch("app.core.auth._decode_token", new_callable=AsyncMock) as mock_decode:
            mock_decode.return_value = {"email": "a@b.com"}
            request = _make_request({"Authorization": "Bearer valid-token"})
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user_id(request)
            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_valid_sub_claim_returns_uuid(self):
        user_uuid = uuid.uuid4()
        with patch("app.core.auth._decode_token", new_callable=AsyncMock) as mock_decode:
            mock_decode.return_value = {"sub": str(user_uuid)}
            request = _make_request({"Authorization": "Bearer valid-token"})
            result = await get_current_user_id(request)
            assert result == user_uuid


# ── Preview Cache Key Isolation ──────────────────────────────────────────


class TestPreviewCacheKeyIsolation:
    """Verify preview cache keys include tenant_id."""

    def test_different_tenants_produce_different_cache_keys(self):
        from app.services.preview_service import PreviewService
        from unittest.mock import MagicMock

        compiler = MagicMock()
        compiler._find_ancestors.return_value = set()
        service = PreviewService(compiler=compiler, query_router=MagicMock(), redis=MagicMock())

        tenant_a = uuid.uuid4()
        tenant_b = uuid.uuid4()
        nodes = [{"id": "n1", "type": "data_source", "data": {"config": {}}}]
        edges = []

        key_a = service._compute_cache_key(tenant_a, "n1", nodes, edges)
        key_b = service._compute_cache_key(tenant_b, "n1", nodes, edges)

        assert key_a != key_b

    def test_same_tenant_same_config_produces_same_cache_key(self):
        from app.services.preview_service import PreviewService
        from unittest.mock import MagicMock

        compiler = MagicMock()
        compiler._find_ancestors.return_value = set()
        service = PreviewService(compiler=compiler, query_router=MagicMock(), redis=MagicMock())

        tenant = uuid.uuid4()
        nodes = [{"id": "n1", "type": "data_source", "data": {"config": {}}}]
        edges = []

        key_1 = service._compute_cache_key(tenant, "n1", nodes, edges)
        key_2 = service._compute_cache_key(tenant, "n1", nodes, edges)

        assert key_1 == key_2
