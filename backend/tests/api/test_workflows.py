"""Workflow CRUD endpoint tests."""

from uuid import UUID

from httpx import AsyncClient


async def test_list_workflows_empty_returns_200(client: AsyncClient, mock_auth):
    response = await client.get("/api/v1/workflows")
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0


async def test_create_workflow_valid_returns_201(client: AsyncClient, mock_auth, seed_user_a):
    response = await client.post(
        "/api/v1/workflows",
        json={"name": "Test Workflow", "description": "A test", "graph_json": {}},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Workflow"
    assert "id" in data


async def test_get_workflow_not_found_returns_404(client: AsyncClient, mock_auth):
    response = await client.get("/api/v1/workflows/00000000-0000-0000-0000-000000000001")
    assert response.status_code == 404


async def test_create_workflow_sets_tenant_from_auth(
    client: AsyncClient, mock_auth, seed_user_a, tenant_id: UUID
):
    """Create workflow sets tenant_id from auth context, not from request body."""
    response = await client.post(
        "/api/v1/workflows",
        json={"name": "Tenant Test", "description": "", "graph_json": {}},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["tenant_id"] == str(tenant_id)


async def test_list_workflows_returns_only_own_tenant(
    client: AsyncClient, db_session, mock_auth, seed_user_a, seed_user_b,
    tenant_id: UUID, user_id: UUID, tenant_id_b: UUID, user_id_b: UUID,
):
    """List workflows returns only the current tenant's workflows."""
    from app.models.workflow import Workflow

    # Create workflow for tenant A (current auth)
    wf_a = Workflow(
        name="Tenant A Workflow",
        tenant_id=tenant_id,
        created_by=user_id,
        graph_json={},
    )
    # Create workflow for tenant B (different tenant)
    wf_b = Workflow(
        name="Tenant B Workflow",
        tenant_id=tenant_id_b,
        created_by=user_id_b,
        graph_json={},
    )
    db_session.add(wf_a)
    db_session.add(wf_b)
    await db_session.commit()

    response = await client.get("/api/v1/workflows")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["name"] == "Tenant A Workflow"


async def test_get_workflow_other_tenant_returns_404(
    client: AsyncClient, db_session, mock_auth, seed_user_b,
    tenant_id_b: UUID, user_id_b: UUID,
):
    """Accessing a workflow belonging to another tenant returns 404 (not 403)."""
    from app.models.workflow import Workflow

    # Create workflow for tenant B
    wf = Workflow(
        name="Other Tenant Workflow",
        tenant_id=tenant_id_b,
        created_by=user_id_b,
        graph_json={},
    )
    db_session.add(wf)
    await db_session.commit()
    await db_session.refresh(wf)

    # Try to access as tenant A (mock_auth uses tenant_id_a)
    response = await client.get(f"/api/v1/workflows/{wf.id}")
    assert response.status_code == 404
