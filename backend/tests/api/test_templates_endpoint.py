"""Template registry endpoint tests."""

from uuid import UUID

from httpx import AsyncClient


async def test_list_templates_returns_all(client: AsyncClient, mock_auth):
    """GET /api/v1/templates returns all 5 templates."""
    response = await client.get("/api/v1/templates")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 5


async def test_get_template_by_id(client: AsyncClient, mock_auth):
    """GET /api/v1/templates/{id} returns single template with graph_json."""
    response = await client.get("/api/v1/templates/trade-blotter")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "trade-blotter"
    assert data["name"] == "Trade Blotter"
    assert "nodes" in data["graph_json"]
    assert "edges" in data["graph_json"]


async def test_get_nonexistent_template_returns_404(client: AsyncClient, mock_auth):
    """GET /api/v1/templates/{id} returns 404 for unknown ID."""
    response = await client.get("/api/v1/templates/does-not-exist")
    assert response.status_code == 404


async def test_instantiate_template_creates_workflow(
    client: AsyncClient, mock_auth, seed_user_a
):
    """POST /templates/{id}/instantiate creates workflow with fresh IDs."""
    response = await client.post(
        "/api/v1/templates/trade-blotter/instantiate",
        json={"name": "My Blotter"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "My Blotter"
    assert "id" in data
    assert data["graph_json"] is not None
    # Verify nodes have fresh IDs (not the template's original IDs)
    nodes = data["graph_json"]["nodes"]
    original_ids = {"ds1", "ft1", "st1", "tbl1"}
    actual_ids = {n["id"] for n in nodes}
    assert actual_ids.isdisjoint(original_ids), "Node IDs should be regenerated"


async def test_instantiate_template_tenant_scoped(
    client: AsyncClient, mock_auth, seed_user_a, tenant_id: UUID
):
    """POST instantiate sets tenant_id from auth context."""
    response = await client.post(
        "/api/v1/templates/trade-blotter/instantiate",
        json={},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["tenant_id"] == str(tenant_id)


async def test_instantiate_template_default_name(
    client: AsyncClient, mock_auth, seed_user_a
):
    """POST instantiate uses template name when no override provided."""
    response = await client.post(
        "/api/v1/templates/pnl-dashboard/instantiate",
        json={},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "P&L Dashboard"


async def test_instantiate_nonexistent_template_returns_404(
    client: AsyncClient, mock_auth, seed_user_a
):
    """POST instantiate with unknown template ID returns 404."""
    response = await client.post(
        "/api/v1/templates/nonexistent/instantiate",
        json={},
    )
    assert response.status_code == 404
