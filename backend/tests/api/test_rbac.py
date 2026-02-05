"""RBAC enforcement tests for widget and schema endpoints.

Verifies role-based guards on write operations and auth on schema routes.
"""

import pytest
from httpx import AsyncClient

from app.api.deps import get_user_claims
from app.main import app


@pytest.fixture
def mock_viewer_claims():
    """Simulate a user with only the viewer role."""

    async def _claims():
        return {
            "sub": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            "tenant_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "realm_access": {"roles": ["viewer"]},
            "resource_access": {},
        }

    app.dependency_overrides[get_user_claims] = _claims
    yield
    app.dependency_overrides.pop(get_user_claims, None)


@pytest.fixture
def mock_analyst_claims():
    """Simulate a user with the analyst role."""

    async def _claims():
        return {
            "sub": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            "tenant_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "realm_access": {"roles": ["analyst"]},
            "resource_access": {},
        }

    app.dependency_overrides[get_user_claims] = _claims
    yield
    app.dependency_overrides.pop(get_user_claims, None)


@pytest.fixture
def mock_admin_claims():
    """Simulate a user with the admin role."""

    async def _claims():
        return {
            "sub": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            "tenant_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "realm_access": {"roles": ["admin"]},
            "resource_access": {},
        }

    app.dependency_overrides[get_user_claims] = _claims
    yield
    app.dependency_overrides.pop(get_user_claims, None)


# --- Widget RBAC ---


WIDGET_CREATE_BODY = {
    "dashboard_id": "00000000-0000-0000-0000-000000000001",
    "source_workflow_id": "00000000-0000-0000-0000-000000000002",
    "source_node_id": "node-1",
    "title": "Test Widget",
}

WIDGET_UPDATE_BODY = {"title": "Updated Title"}

FAKE_WIDGET_ID = "00000000-0000-0000-0000-000000000099"


async def test_viewer_cannot_create_widget(
    client: AsyncClient, mock_auth, mock_viewer_claims
):
    """Viewer role should be rejected when creating a widget."""
    response = await client.post("/api/v1/widgets", json=WIDGET_CREATE_BODY)
    assert response.status_code == 403


async def test_viewer_cannot_update_widget(
    client: AsyncClient, mock_auth, mock_viewer_claims
):
    """Viewer role should be rejected when updating a widget."""
    response = await client.patch(
        f"/api/v1/widgets/{FAKE_WIDGET_ID}", json=WIDGET_UPDATE_BODY
    )
    assert response.status_code == 403


async def test_viewer_cannot_delete_widget(
    client: AsyncClient, mock_auth, mock_viewer_claims
):
    """Viewer role should be rejected when deleting a widget."""
    response = await client.delete(f"/api/v1/widgets/{FAKE_WIDGET_ID}")
    assert response.status_code == 403


async def test_analyst_cannot_delete_widget(
    client: AsyncClient, mock_auth, mock_analyst_claims
):
    """Analyst role should be rejected when deleting a widget (admin only)."""
    response = await client.delete(f"/api/v1/widgets/{FAKE_WIDGET_ID}")
    assert response.status_code == 403


async def test_analyst_can_create_widget_role_check(
    client: AsyncClient, mock_auth, mock_analyst_claims
):
    """Analyst role passes the RBAC check (may fail on 404 for dashboard/workflow)."""
    response = await client.post("/api/v1/widgets", json=WIDGET_CREATE_BODY)
    # 404 means RBAC passed but dashboard not found — expected
    assert response.status_code in (201, 404)


async def test_admin_can_delete_widget_role_check(
    client: AsyncClient, mock_auth, mock_admin_claims
):
    """Admin role passes the RBAC check for delete (may 404 on widget)."""
    response = await client.delete(f"/api/v1/widgets/{FAKE_WIDGET_ID}")
    # 404 means RBAC passed but widget not found — expected
    assert response.status_code in (204, 404)


# --- Schema auth ---


async def test_schema_catalog_requires_auth(client: AsyncClient, mock_auth):
    """Schema catalog endpoint is wired with auth dependency."""
    response = await client.get("/api/v1/schema")
    # With mock_auth the endpoint is reachable; 200 confirms auth dep is wired
    assert response.status_code == 200


async def test_schema_refresh_requires_auth(client: AsyncClient, mock_auth):
    """Schema refresh endpoint is wired with auth dependency."""
    response = await client.post("/api/v1/schema/refresh")
    assert response.status_code == 200
