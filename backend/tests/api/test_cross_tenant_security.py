"""Cross-tenant security integration tests.

Verifies that route-level IDOR protection works for dashboards, widgets,
executions, audit logs, and templates. Pattern: create resource as tenant A,
switch to tenant B auth, verify 404 on get/update/delete.
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_redis, get_user_claims, get_websocket_manager
from app.main import app
from app.models.dashboard import Dashboard
from app.models.workflow import Workflow

TENANT_A = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
TENANT_B = "cccccccc-cccc-cccc-cccc-cccccccccccc"


def _claims_for(tenant_id: str, user_id: str, roles: list[str] | None = None):
    """Build a Keycloak-style claims dict."""
    if roles is None:
        roles = ["admin"]

    async def _claims():
        return {
            "sub": user_id,
            "tenant_id": tenant_id,
            "realm_access": {"roles": roles},
            "resource_access": {},
        }

    return _claims


# ── Dashboard Tenant Isolation ──────────────────────────────────────────


class TestDashboardTenantIsolation:
    @pytest.fixture(autouse=True)
    def _setup_claims(self, tenant_id, user_id):
        app.dependency_overrides[get_user_claims] = _claims_for(
            str(tenant_id), str(user_id)
        )
        yield
        app.dependency_overrides.pop(get_user_claims, None)

    async def test_list_dashboards_filters_by_tenant(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        mock_auth,
        seed_user_a,
        seed_user_b,
        tenant_id,
        user_id,
        tenant_id_b,
        user_id_b,
    ):
        db_session.add(
            Dashboard(
                name="Dash A",
                tenant_id=tenant_id,
                created_by=user_id,
            )
        )
        db_session.add(
            Dashboard(
                name="Dash B",
                tenant_id=tenant_id_b,
                created_by=user_id_b,
            )
        )
        await db_session.commit()

        resp = await client.get("/api/v1/dashboards")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["name"] == "Dash A"

    async def test_get_dashboard_different_tenant_returns_404(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        mock_auth,
        seed_user_b,
        tenant_id_b,
        user_id_b,
    ):
        dash = Dashboard(
            name="Other Dash",
            tenant_id=tenant_id_b,
            created_by=user_id_b,
        )
        db_session.add(dash)
        await db_session.commit()
        await db_session.refresh(dash)

        resp = await client.get(f"/api/v1/dashboards/{dash.id}")
        assert resp.status_code == 404

    async def test_create_dashboard_sets_tenant_from_auth(
        self,
        client: AsyncClient,
        mock_auth,
        seed_user_a,
        tenant_id,
    ):
        resp = await client.post(
            "/api/v1/dashboards",
            json={"name": "My Dash", "description": "Test"},
        )
        assert resp.status_code == 201
        assert resp.json()["tenant_id"] == str(tenant_id)

    async def test_update_dashboard_different_tenant_returns_404(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        mock_auth,
        seed_user_b,
        tenant_id_b,
        user_id_b,
    ):
        dash = Dashboard(
            name="Other Dash",
            tenant_id=tenant_id_b,
            created_by=user_id_b,
        )
        db_session.add(dash)
        await db_session.commit()
        await db_session.refresh(dash)

        resp = await client.patch(
            f"/api/v1/dashboards/{dash.id}",
            json={"name": "Hijacked"},
        )
        assert resp.status_code == 404

    async def test_delete_dashboard_different_tenant_returns_404(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        mock_auth,
        seed_user_b,
        tenant_id_b,
        user_id_b,
    ):
        dash = Dashboard(
            name="Other Dash",
            tenant_id=tenant_id_b,
            created_by=user_id_b,
        )
        db_session.add(dash)
        await db_session.commit()
        await db_session.refresh(dash)

        resp = await client.delete(f"/api/v1/dashboards/{dash.id}")
        assert resp.status_code == 404


# ── Widget Cross-Tenant Reference ───────────────────────────────────────


class TestWidgetCrossTenantReference:
    @pytest.fixture(autouse=True)
    def _setup_claims(self, tenant_id, user_id):
        app.dependency_overrides[get_user_claims] = _claims_for(
            str(tenant_id), str(user_id)
        )
        yield
        app.dependency_overrides.pop(get_user_claims, None)

    async def test_create_widget_cross_tenant_workflow_returns_404(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        mock_auth,
        seed_user_a,
        seed_user_b,
        tenant_id,
        user_id,
        tenant_id_b,
        user_id_b,
    ):
        """Widget referencing a workflow from a different tenant must fail."""
        # Dashboard owned by tenant A
        dash = Dashboard(
            name="A's Dash",
            tenant_id=tenant_id,
            created_by=user_id,
        )
        # Workflow owned by tenant B
        wf = Workflow(
            name="B's Workflow",
            tenant_id=tenant_id_b,
            created_by=user_id_b,
            graph_json={},
        )
        db_session.add(dash)
        db_session.add(wf)
        await db_session.commit()
        await db_session.refresh(dash)
        await db_session.refresh(wf)

        resp = await client.post(
            "/api/v1/widgets",
            json={
                "dashboard_id": str(dash.id),
                "source_workflow_id": str(wf.id),
                "source_node_id": "node-1",
            },
        )
        assert resp.status_code == 404


# ── Execution Tenant Isolation ──────────────────────────────────────────


class TestExecutionTenantIsolation:
    @pytest.fixture
    def mock_redis_store(self):
        store: dict[str, str] = {}
        redis = AsyncMock()

        async def fake_get(key: str):
            return store.get(key)

        async def fake_set(key: str, value: str, ex: int | None = None):
            store[key] = value

        redis.get = AsyncMock(side_effect=fake_get)
        redis.set = AsyncMock(side_effect=fake_set)
        redis._store = store
        return redis

    @pytest.fixture(autouse=True)
    def _override_deps(self, mock_redis_store):
        mock_ws = MagicMock()
        mock_ws.publish_execution_status = AsyncMock()
        app.dependency_overrides[get_redis] = lambda: mock_redis_store
        app.dependency_overrides[get_websocket_manager] = lambda: mock_ws
        yield
        app.dependency_overrides.pop(get_redis, None)
        app.dependency_overrides.pop(get_websocket_manager, None)

    async def test_get_execution_different_tenant_returns_404(
        self,
        client: AsyncClient,
        mock_auth,
        mock_redis_store,
    ):
        """Execution stored under tenant B is invisible to tenant A."""
        exec_id = "11111111-1111-1111-1111-111111111111"
        key_b = f"flowforge:{TENANT_B}:execution:{exec_id}"
        mock_redis_store._store[key_b] = json.dumps(
            {
                "id": exec_id,
                "workflow_id": "00000000-0000-0000-0000-000000000099",
                "tenant_id": TENANT_B,
                "status": "completed",
                "node_statuses": {},
                "started_at": "2026-01-01T00:00:00+00:00",
                "completed_at": "2026-01-01T00:01:00+00:00",
            }
        )

        resp = await client.get(f"/api/v1/executions/{exec_id}")
        assert resp.status_code == 404


# ── Audit Log Tenant Isolation ──────────────────────────────────────────


class TestAuditLogTenantIsolation:
    async def test_list_audit_logs_filters_by_tenant(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        mock_auth,
        seed_user_a,
        seed_user_b,
        tenant_id,
        user_id,
        tenant_id_b,
        user_id_b,
    ):
        """Audit logs for tenant B should not appear in tenant A's listing."""
        from app.models.audit_log import AuditAction, AuditLog, AuditResourceType

        # Set up admin claims for tenant A
        app.dependency_overrides[get_user_claims] = _claims_for(
            str(tenant_id), str(user_id), ["admin"]
        )

        try:
            # Create audit entries for both tenants
            db_session.add(
                AuditLog(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    action=AuditAction.CREATED,
                    resource_type=AuditResourceType.WORKFLOW,
                    resource_id=user_id,
                )
            )
            db_session.add(
                AuditLog(
                    tenant_id=tenant_id_b,
                    user_id=user_id_b,
                    action=AuditAction.CREATED,
                    resource_type=AuditResourceType.DASHBOARD,
                    resource_id=user_id_b,
                )
            )
            await db_session.commit()

            resp = await client.get("/api/v1/audit-logs")
            assert resp.status_code == 200
            data = resp.json()
            # Should only see tenant A's entry
            assert data["total"] == 1
            assert data["items"][0]["tenant_id"] == str(tenant_id)
        finally:
            app.dependency_overrides.pop(get_user_claims, None)


# ── Template Tenant Isolation ───────────────────────────────────────────


class TestTemplateTenantIsolation:
    async def test_instantiate_template_creates_in_own_tenant(
        self,
        client: AsyncClient,
        mock_auth,
        seed_user_a,
        tenant_id,
        user_id,
    ):
        """Instantiated template workflow must belong to the caller's tenant."""
        app.dependency_overrides[get_user_claims] = _claims_for(
            str(tenant_id), str(user_id)
        )

        try:
            # Get available templates first
            list_resp = await client.get("/api/v1/templates")
            assert list_resp.status_code == 200
            templates = list_resp.json()["items"]
            if not templates:
                pytest.skip("No templates registered — cannot test instantiation")

            template_id = templates[0]["id"]
            resp = await client.post(
                f"/api/v1/templates/{template_id}/instantiate",
                json={"name": "My Instance"},
            )
            assert resp.status_code == 201
            data = resp.json()
            assert data["tenant_id"] == str(tenant_id)
        finally:
            app.dependency_overrides.pop(get_user_claims, None)
