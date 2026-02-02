"""Workflow CRUD endpoint tests."""

from httpx import AsyncClient


async def test_list_workflows_empty_returns_200(client: AsyncClient):
    response = await client.get("/api/v1/workflows")
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0


async def test_create_workflow_valid_returns_201(client: AsyncClient):
    response = await client.post(
        "/api/v1/workflows",
        json={"name": "Test Workflow", "description": "A test", "graph_json": {}},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Workflow"
    assert "id" in data


async def test_get_workflow_not_found_returns_404(client: AsyncClient):
    response = await client.get("/api/v1/workflows/00000000-0000-0000-0000-000000000001")
    assert response.status_code == 404
