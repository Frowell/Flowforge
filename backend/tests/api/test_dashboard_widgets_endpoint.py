"""Tests for dashboard widget list endpoint and widget data features."""

import json
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dashboard import Dashboard, Widget
from app.models.workflow import Workflow

# ── Helpers ──────────────────────────────────────────────────────────────


async def _create_dashboard(
    db: AsyncSession, tenant_id: UUID, user_id: UUID, name: str = "Test Dashboard"
) -> Dashboard:
    dashboard = Dashboard(name=name, tenant_id=tenant_id, created_by=user_id)
    db.add(dashboard)
    await db.commit()
    await db.refresh(dashboard)
    return dashboard


async def _create_workflow(
    db: AsyncSession, tenant_id: UUID, user_id: UUID, name: str = "Test Workflow"
) -> Workflow:
    workflow = Workflow(
        name=name,
        tenant_id=tenant_id,
        created_by=user_id,
        graph_json={
            "nodes": [
                {
                    "id": "node_1",
                    "type": "chart_output",
                    "data": {
                        "config": {
                            "chart_type": "bar",
                            "x_axis": "category",
                            "y_axis": "value",
                        }
                    },
                }
            ],
            "edges": [],
        },
    )
    db.add(workflow)
    await db.commit()
    await db.refresh(workflow)
    return workflow


async def _create_widget(
    db: AsyncSession,
    dashboard_id: UUID,
    workflow_id: UUID,
    source_node_id: str = "node_1",
    title: str | None = None,
) -> Widget:
    widget = Widget(
        dashboard_id=dashboard_id,
        source_workflow_id=workflow_id,
        source_node_id=source_node_id,
        title=title,
        layout={"x": 0, "y": 0, "w": 6, "h": 4},
        config_overrides={},
    )
    db.add(widget)
    await db.commit()
    await db.refresh(widget)
    return widget


# ── GET /dashboards/{id}/widgets ──────────────────────────────────────


@pytest.mark.asyncio
async def test_list_dashboard_widgets_returns_widgets(
    client: AsyncClient,
    db_session: AsyncSession,
    mock_auth,
    seed_user_a,
    tenant_id: UUID,
    user_id: UUID,
):
    """GET /dashboards/{id}/widgets returns all widgets for that dashboard."""
    dashboard = await _create_dashboard(db_session, tenant_id, user_id)
    workflow = await _create_workflow(db_session, tenant_id, user_id)
    w1 = await _create_widget(db_session, dashboard.id, workflow.id, title="Widget A")
    w2 = await _create_widget(db_session, dashboard.id, workflow.id, title="Widget B")

    response = await client.get(f"/api/v1/dashboards/{dashboard.id}/widgets")
    assert response.status_code == 200

    data = response.json()
    assert len(data) == 2
    widget_ids = {w["id"] for w in data}
    assert str(w1.id) in widget_ids
    assert str(w2.id) in widget_ids


@pytest.mark.asyncio
async def test_list_dashboard_widgets_empty(
    client: AsyncClient,
    db_session: AsyncSession,
    mock_auth,
    seed_user_a,
    tenant_id: UUID,
    user_id: UUID,
):
    """GET /dashboards/{id}/widgets returns empty list when no widgets exist."""
    dashboard = await _create_dashboard(db_session, tenant_id, user_id)

    response = await client.get(f"/api/v1/dashboards/{dashboard.id}/widgets")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_list_dashboard_widgets_different_tenant_404(
    client: AsyncClient,
    db_session: AsyncSession,
    mock_auth,
    seed_user_a,
    seed_user_b,
    tenant_id_b: UUID,
    user_id_b: UUID,
):
    """GET /dashboards/{id}/widgets returns 404 for other tenant."""
    # Create dashboard in tenant B
    dashboard_b = await _create_dashboard(
        db_session, tenant_id_b, user_id_b, "Tenant B Dashboard"
    )

    # Auth is set to tenant A via mock_auth — accessing tenant B dashboard should 404
    response = await client.get(f"/api/v1/dashboards/{dashboard_b.id}/widgets")
    assert response.status_code == 404


# ── Widget data includes chart_config ─────────────────────────────────


@pytest.mark.asyncio
async def test_widget_data_includes_chart_config(
    client: AsyncClient,
    db_session: AsyncSession,
    mock_auth,
    seed_user_a,
    tenant_id: UUID,
    user_id: UUID,
):
    """GET /widgets/{id}/data response includes chart_config from the source node."""
    dashboard = await _create_dashboard(db_session, tenant_id, user_id)
    workflow = await _create_workflow(db_session, tenant_id, user_id)
    widget = await _create_widget(db_session, dashboard.id, workflow.id)

    mock_result = {
        "columns": [{"name": "category", "dtype": "String"}],
        "rows": [{"category": "A"}],
        "total_rows": 1,
        "execution_ms": 5.0,
        "cache_hit": False,
        "offset": 0,
        "limit": 10000,
        "chart_config": {"chart_type": "bar", "x_axis": "category", "y_axis": "value"},
    }

    with patch(
        "app.api.deps.get_widget_data_service",
        return_value=lambda: AsyncMock(
            fetch_widget_data=AsyncMock(return_value=mock_result)
        ),
    ):
        # Override the dependency directly for this test
        from app.api.deps import get_widget_data_service
        from app.main import app as test_app

        mock_service = AsyncMock()
        mock_service.fetch_widget_data = AsyncMock(return_value=mock_result)
        test_app.dependency_overrides[get_widget_data_service] = lambda: mock_service

        try:
            response = await client.get(f"/api/v1/widgets/{widget.id}/data")
            assert response.status_code == 200
            data = response.json()
            assert "chart_config" in data
            assert data["chart_config"]["chart_type"] == "bar"
        finally:
            test_app.dependency_overrides.pop(get_widget_data_service, None)


# ── Widget data accepts filters param ──────────────────────────────────


@pytest.mark.asyncio
async def test_widget_data_accepts_filters_param(
    client: AsyncClient,
    db_session: AsyncSession,
    mock_auth,
    seed_user_a,
    tenant_id: UUID,
    user_id: UUID,
):
    """GET /widgets/{id}/data accepts a filters query parameter."""
    dashboard = await _create_dashboard(db_session, tenant_id, user_id)
    workflow = await _create_workflow(db_session, tenant_id, user_id)
    widget = await _create_widget(db_session, dashboard.id, workflow.id)

    mock_result = {
        "columns": [],
        "rows": [],
        "total_rows": 0,
        "execution_ms": 0.0,
        "cache_hit": False,
        "offset": 0,
        "limit": 10000,
        "chart_config": None,
    }

    from app.api.deps import get_widget_data_service
    from app.main import app as test_app

    mock_service = AsyncMock()
    mock_service.fetch_widget_data = AsyncMock(return_value=mock_result)
    test_app.dependency_overrides[get_widget_data_service] = lambda: mock_service

    try:
        filters = json.dumps(
            [
                {
                    "column": "date",
                    "type": "date_range",
                    "value": {"from": "2024-01-01", "to": "2024-12-31"},
                }
            ]
        )
        response = await client.get(
            f"/api/v1/widgets/{widget.id}/data",
            params={"filters": filters},
        )
        assert response.status_code == 200

        # Verify service was called with filter_params
        call_kwargs = mock_service.fetch_widget_data.call_args[1]
        assert call_kwargs["filter_params"] is not None
    finally:
        test_app.dependency_overrides.pop(get_widget_data_service, None)


@pytest.mark.asyncio
async def test_widget_data_invalid_filters_returns_400(
    client: AsyncClient,
    db_session: AsyncSession,
    mock_auth,
    seed_user_a,
    tenant_id: UUID,
    user_id: UUID,
):
    """GET /widgets/{id}/data returns 400 for malformed filters JSON."""
    dashboard = await _create_dashboard(db_session, tenant_id, user_id)
    workflow = await _create_workflow(db_session, tenant_id, user_id)
    widget = await _create_widget(db_session, dashboard.id, workflow.id)

    response = await client.get(
        f"/api/v1/widgets/{widget.id}/data",
        params={"filters": "not-valid-json"},
    )
    assert response.status_code == 400
    assert "Invalid filters JSON" in response.json()["detail"]
