"""Role-based access control tests.

Verifies that require_role() guards enforce correct permissions.
Uses dependency overrides to simulate different roles.
"""

from uuid import UUID

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


# --- Workflow access ---

async def test_viewer_cannot_create_workflow(
    client: AsyncClient, mock_auth, mock_viewer_claims
):
    """Viewer role should be rejected when creating a workflow."""
    response = await client.post(
        "/api/v1/workflows",
        json={"name": "Test", "graph_json": {}},
    )
    assert response.status_code == 403


async def test_viewer_can_list_workflows(
    client: AsyncClient, mock_auth, mock_viewer_claims
):
    """Viewer role can list workflows (read-only)."""
    response = await client.get("/api/v1/workflows")
    assert response.status_code == 200


async def test_analyst_can_create_workflow(
    client: AsyncClient, mock_auth, mock_analyst_claims, seed_user_a
):
    """Analyst role should be able to create workflows."""
    response = await client.post(
        "/api/v1/workflows",
        json={"name": "Analyst Workflow", "graph_json": {}},
    )
    assert response.status_code == 201


# --- Execution access ---

async def test_viewer_cannot_execute_workflow(
    client: AsyncClient, mock_auth, mock_viewer_claims
):
    """Viewer role should be rejected when executing a workflow."""
    response = await client.post(
        "/api/v1/executions",
        json={"workflow_id": "00000000-0000-0000-0000-000000000001"},
    )
    assert response.status_code == 403


# --- API key access ---

async def test_admin_can_manage_api_keys(
    client: AsyncClient, mock_auth, mock_admin_claims
):
    """Admin role can list API keys."""
    response = await client.get("/api/v1/api-keys")
    assert response.status_code == 200


async def test_viewer_cannot_manage_api_keys(
    client: AsyncClient, mock_auth, mock_viewer_claims
):
    """Viewer role should be rejected for API key operations."""
    response = await client.get("/api/v1/api-keys")
    assert response.status_code == 403


async def test_analyst_cannot_manage_api_keys(
    client: AsyncClient, mock_auth, mock_analyst_claims
):
    """Analyst role should be rejected for API key operations (admin only)."""
    response = await client.get("/api/v1/api-keys")
    assert response.status_code == 403


# --- Audit log access ---

async def test_viewer_cannot_access_audit_logs(
    client: AsyncClient, mock_auth, mock_viewer_claims
):
    """Viewer role should be rejected from audit logs."""
    response = await client.get("/api/v1/audit-logs")
    assert response.status_code == 403


async def test_admin_can_access_audit_logs(
    client: AsyncClient, mock_auth, mock_admin_claims
):
    """Admin role can access audit logs."""
    response = await client.get("/api/v1/audit-logs")
    assert response.status_code == 200
