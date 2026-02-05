"""Health endpoint tests."""

from httpx import AsyncClient


async def test_health_check_returns_200(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


async def test_health_check_includes_service_name(client: AsyncClient):
    response = await client.get("/health")
    assert response.json()["service"] == "flowforge"


async def test_liveness_returns_200(client: AsyncClient):
    response = await client.get("/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "live"
