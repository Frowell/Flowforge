"""Execution history persistence tests.

Verifies write-through to PostgreSQL and paginated history listing.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_redis
from app.main import app
from app.models.execution import Execution
from app.models.workflow import Workflow


@pytest.fixture(autouse=True)
def mock_redis():
    """Mock Redis to return None (cache miss) so tests fall through to PG."""
    mock = AsyncMock()
    mock.get = AsyncMock(return_value=None)
    app.dependency_overrides[get_redis] = lambda: mock
    yield mock
    app.dependency_overrides.pop(get_redis, None)


async def _create_workflow(
    db_session: AsyncSession, tenant_id: UUID, user_id: UUID
) -> Workflow:
    """Helper to create a workflow for tests."""
    wf = Workflow(
        name="Test Workflow",
        tenant_id=tenant_id,
        created_by=user_id,
        graph_json={"nodes": [], "edges": []},
    )
    db_session.add(wf)
    await db_session.commit()
    await db_session.refresh(wf)
    return wf


async def _create_execution(
    db_session: AsyncSession,
    workflow_id: UUID,
    tenant_id: UUID,
    user_id: UUID,
    status: str = "completed",
) -> Execution:
    """Helper to create an execution record directly in PostgreSQL."""
    execution = Execution(
        workflow_id=workflow_id,
        tenant_id=tenant_id,
        started_by=user_id,
        status=status,
        node_statuses={},
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC) if status in ("completed", "failed") else None,
        error_message="something went wrong" if status == "failed" else None,
    )
    db_session.add(execution)
    await db_session.commit()
    await db_session.refresh(execution)
    return execution


async def test_list_executions_returns_paginated(
    client: AsyncClient,
    db_session: AsyncSession,
    mock_auth,
    seed_user_a,
    tenant_id: UUID,
    user_id: UUID,
):
    """GET /executions/history/{workflow_id} returns paginated results."""
    wf = await _create_workflow(db_session, tenant_id, user_id)

    # Create 3 executions
    for _ in range(3):
        await _create_execution(db_session, wf.id, tenant_id, user_id)

    response = await client.get(
        f"/api/v1/executions/history/{wf.id}",
        params={"page": 1, "page_size": 2},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert len(data["items"]) == 2
    assert data["page"] == 1
    assert data["page_size"] == 2


async def test_list_executions_page_two(
    client: AsyncClient,
    db_session: AsyncSession,
    mock_auth,
    seed_user_a,
    tenant_id: UUID,
    user_id: UUID,
):
    """Second page returns remaining items."""
    wf = await _create_workflow(db_session, tenant_id, user_id)
    for _ in range(3):
        await _create_execution(db_session, wf.id, tenant_id, user_id)

    response = await client.get(
        f"/api/v1/executions/history/{wf.id}",
        params={"page": 2, "page_size": 2},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert len(data["items"]) == 1


async def test_list_executions_filters_by_tenant(
    client: AsyncClient,
    db_session: AsyncSession,
    mock_auth,
    seed_user_a,
    seed_user_b,
    tenant_id: UUID,
    user_id: UUID,
    tenant_id_b: UUID,
    user_id_b: UUID,
):
    """Execution history only shows executions for the current tenant's workflow."""
    # Create workflow for tenant A
    wf_a = await _create_workflow(db_session, tenant_id, user_id)
    await _create_execution(db_session, wf_a.id, tenant_id, user_id)

    # Create workflow for tenant B with its own execution
    wf_b = Workflow(
        name="Tenant B WF",
        tenant_id=tenant_id_b,
        created_by=user_id_b,
        graph_json={"nodes": [], "edges": []},
    )
    db_session.add(wf_b)
    await db_session.commit()
    await db_session.refresh(wf_b)
    await _create_execution(db_session, wf_b.id, tenant_id_b, user_id_b)

    # Tenant A should see only their workflow's executions
    response = await client.get(f"/api/v1/executions/history/{wf_a.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1

    # Tenant A should get 404 for tenant B's workflow
    response_b = await client.get(f"/api/v1/executions/history/{wf_b.id}")
    assert response_b.status_code == 404


async def test_get_execution_falls_back_to_postgres(
    client: AsyncClient,
    db_session: AsyncSession,
    mock_auth,
    seed_user_a,
    tenant_id: UUID,
    user_id: UUID,
):
    """GET /executions/{id} returns data from PostgreSQL when not in Redis."""
    wf = await _create_workflow(db_session, tenant_id, user_id)
    execution = await _create_execution(
        db_session, wf.id, tenant_id, user_id, status="completed"
    )

    # No Redis setup — should fall back to PostgreSQL
    response = await client.get(f"/api/v1/executions/{execution.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(execution.id)
    assert data["status"] == "completed"
    assert data["workflow_id"] == str(wf.id)


async def test_get_execution_different_tenant_returns_404(
    client: AsyncClient,
    db_session: AsyncSession,
    mock_auth,
    seed_user_a,
    seed_user_b,
    tenant_id: UUID,
    user_id: UUID,
    tenant_id_b: UUID,
    user_id_b: UUID,
):
    """GET /executions/{id} for another tenant's execution returns 404."""
    wf_b = Workflow(
        name="Tenant B WF",
        tenant_id=tenant_id_b,
        created_by=user_id_b,
        graph_json={"nodes": [], "edges": []},
    )
    db_session.add(wf_b)
    await db_session.commit()
    await db_session.refresh(wf_b)

    execution_b = await _create_execution(db_session, wf_b.id, tenant_id_b, user_id_b)

    # Tenant A tries to access tenant B's execution
    response = await client.get(f"/api/v1/executions/{execution_b.id}")
    assert response.status_code == 404


async def test_list_execution_history_workflow_not_found(
    client: AsyncClient,
    mock_auth,
    seed_user_a,
):
    """GET /executions/history/{workflow_id} returns 404 for non-existent workflow."""
    response = await client.get(
        "/api/v1/executions/history/00000000-0000-0000-0000-000000000099"
    )
    assert response.status_code == 404
