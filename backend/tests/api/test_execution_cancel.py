"""Execution cancellation endpoint tests."""

import json
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from httpx import AsyncClient

from app.api.deps import get_redis, get_websocket_manager
from app.main import app


@pytest.fixture
def mock_redis():
    """In-memory Redis mock that supports get/set."""
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


@pytest.fixture
def mock_ws():
    ws = MagicMock()
    ws.publish_execution_status = AsyncMock()
    return ws


@pytest.fixture
def override_redis(mock_redis):
    app.dependency_overrides[get_redis] = lambda: mock_redis
    yield mock_redis
    app.dependency_overrides.pop(get_redis, None)


@pytest.fixture
def override_ws(mock_ws):
    app.dependency_overrides[get_websocket_manager] = lambda: mock_ws
    yield mock_ws
    app.dependency_overrides.pop(get_websocket_manager, None)


def _make_execution_record(
    execution_id: str, tenant_id: str, status: str = "running"
) -> dict:
    return {
        "id": execution_id,
        "workflow_id": "00000000-0000-0000-0000-000000000099",
        "tenant_id": tenant_id,
        "status": status,
        "node_statuses": {},
        "started_at": "2026-01-01T00:00:00+00:00",
        "completed_at": None,
    }


EXEC_ID = "11111111-1111-1111-1111-111111111111"
TENANT_A = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
TENANT_B = "cccccccc-cccc-cccc-cccc-cccccccccccc"


async def test_cancel_running_execution_returns_202(
    client: AsyncClient, mock_auth, override_redis, override_ws
):
    redis = override_redis
    key = f"flowforge:{TENANT_A}:execution:{EXEC_ID}"
    redis._store[key] = json.dumps(_make_execution_record(EXEC_ID, TENANT_A, "running"))

    response = await client.post(f"/api/v1/executions/{EXEC_ID}/cancel")
    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "cancelled"
    assert data["id"] == EXEC_ID

    # Verify Redis was updated
    stored = json.loads(redis._store[key])
    assert stored["status"] == "cancelled"
    assert stored["completed_at"] is not None


async def test_cancel_pending_execution_returns_202(
    client: AsyncClient, mock_auth, override_redis, override_ws
):
    redis = override_redis
    key = f"flowforge:{TENANT_A}:execution:{EXEC_ID}"
    redis._store[key] = json.dumps(_make_execution_record(EXEC_ID, TENANT_A, "pending"))

    response = await client.post(f"/api/v1/executions/{EXEC_ID}/cancel")
    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "cancelled"


async def test_cancel_publishes_websocket_status(
    client: AsyncClient, mock_auth, override_redis, override_ws
):
    redis = override_redis
    ws = override_ws
    key = f"flowforge:{TENANT_A}:execution:{EXEC_ID}"
    redis._store[key] = json.dumps(_make_execution_record(EXEC_ID, TENANT_A, "running"))

    await client.post(f"/api/v1/executions/{EXEC_ID}/cancel")

    ws.publish_execution_status.assert_awaited_once_with(
        tenant_id=UUID(TENANT_A),
        execution_id=UUID(EXEC_ID),
        node_id="__workflow__",
        status="cancelled",
    )


async def test_cancel_completed_execution_returns_409(
    client: AsyncClient, mock_auth, override_redis, override_ws
):
    redis = override_redis
    key = f"flowforge:{TENANT_A}:execution:{EXEC_ID}"
    redis._store[key] = json.dumps(
        _make_execution_record(EXEC_ID, TENANT_A, "completed")
    )

    response = await client.post(f"/api/v1/executions/{EXEC_ID}/cancel")
    assert response.status_code == 409


async def test_cancel_failed_execution_returns_409(
    client: AsyncClient, mock_auth, override_redis, override_ws
):
    redis = override_redis
    key = f"flowforge:{TENANT_A}:execution:{EXEC_ID}"
    redis._store[key] = json.dumps(
        _make_execution_record(EXEC_ID, TENANT_A, "failed")
    )

    response = await client.post(f"/api/v1/executions/{EXEC_ID}/cancel")
    assert response.status_code == 409


async def test_cancel_nonexistent_execution_returns_404(
    client: AsyncClient, mock_auth, override_redis, override_ws
):
    response = await client.post(
        "/api/v1/executions/00000000-0000-0000-0000-000000000000/cancel"
    )
    assert response.status_code == 404


async def test_cancel_cross_tenant_execution_returns_404(
    client: AsyncClient, mock_auth, override_redis, override_ws
):
    """Execution stored under tenant B should not be visible to tenant A."""
    redis = override_redis
    # Store under tenant B's key
    key_b = f"flowforge:{TENANT_B}:execution:{EXEC_ID}"
    redis._store[key_b] = json.dumps(
        _make_execution_record(EXEC_ID, TENANT_B, "running")
    )

    # mock_auth is for tenant A — should get 404
    response = await client.post(f"/api/v1/executions/{EXEC_ID}/cancel")
    assert response.status_code == 404
