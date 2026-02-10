"""Widget endpoints — pin/unpin workflow outputs to dashboards.

Widgets inherit tenant scope from their parent Dashboard.
Cross-tenant references (dashboard in tenant A, workflow in tenant B) are rejected.
"""

import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_current_tenant_id,
    get_db,
    get_widget_data_service,
    require_role,
)
from app.models.dashboard import Dashboard, Widget
from app.models.workflow import Workflow
from app.schemas.dashboard import (
    WidgetCreate,
    WidgetDataResponse,
    WidgetResponse,
    WidgetUpdate,
)
from app.services.widget_data_service import WidgetDataService

router = APIRouter()


@router.post("", response_model=WidgetResponse, status_code=status.HTTP_201_CREATED)
async def pin_widget(
    body: WidgetCreate,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_role("admin", "analyst")),
):
    """Pin a workflow output node to a dashboard as a widget.

    Both the dashboard and the source workflow must belong to the caller's tenant.
    """
    # Verify dashboard belongs to tenant
    dash_result = await db.execute(
        select(Dashboard).where(
            Dashboard.id == body.dashboard_id,
            Dashboard.tenant_id == tenant_id,
        )
    )
    if not dash_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Dashboard not found"
        )

    # Verify source workflow belongs to same tenant
    wf_result = await db.execute(
        select(Workflow).where(
            Workflow.id == body.source_workflow_id,
            Workflow.tenant_id == tenant_id,
        )
    )
    if not wf_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found"
        )

    widget = Widget(
        dashboard_id=body.dashboard_id,
        source_workflow_id=body.source_workflow_id,
        source_node_id=body.source_node_id,
        title=body.title,
        layout=body.layout,
        config_overrides=body.config_overrides,
        auto_refresh_interval=body.auto_refresh_interval,
    )
    db.add(widget)
    await db.commit()
    await db.refresh(widget)
    return WidgetResponse.model_validate(widget)


@router.patch("/{widget_id}", response_model=WidgetResponse)
async def update_widget(
    widget_id: UUID,
    body: WidgetUpdate,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_role("admin", "analyst")),
):
    # Widget inherits tenant from its dashboard — join through dashboard to check tenant
    result = await db.execute(
        select(Widget)
        .join(Dashboard, Widget.dashboard_id == Dashboard.id)
        .where(
            Widget.id == widget_id,
            Dashboard.tenant_id == tenant_id,
        )
    )
    widget = result.scalar_one_or_none()
    if not widget:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Widget not found"
        )

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(widget, field, value)

    await db.commit()
    await db.refresh(widget)
    return WidgetResponse.model_validate(widget)


@router.get("/{widget_id}/data", response_model=WidgetDataResponse)
async def get_widget_data(
    widget_id: UUID,
    offset: int = Query(0, ge=0, description="Row offset for pagination"),
    limit: int = Query(1_000, ge=1, le=5_000, description="Max rows to return"),
    filters: str | None = Query(None, description="JSON-encoded filter parameters"),
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db),
    widget_data_service: WidgetDataService = Depends(get_widget_data_service),
):
    """Fetch data for a widget by compiling its source workflow."""
    # Load widget with tenant check through dashboard
    result = await db.execute(
        select(Widget)
        .join(Dashboard, Widget.dashboard_id == Dashboard.id)
        .where(
            Widget.id == widget_id,
            Dashboard.tenant_id == tenant_id,
        )
    )
    widget = result.scalar_one_or_none()
    if not widget:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Widget not found"
        )

    # Load source workflow with tenant check
    wf_result = await db.execute(
        select(Workflow).where(
            Workflow.id == widget.source_workflow_id,
            Workflow.tenant_id == tenant_id,
        )
    )
    workflow = wf_result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Source workflow not found"
        )

    # Parse optional JSON filter params
    filter_params: dict | None = None
    if filters:
        try:
            filter_params = json.loads(filters)
        except (json.JSONDecodeError, TypeError) as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid filters JSON",
            ) from exc

    data = await widget_data_service.fetch_widget_data(
        tenant_id=tenant_id,
        source_node_id=widget.source_node_id,
        graph_json=workflow.graph_json,
        config_overrides=widget.config_overrides,
        filter_params=filter_params,
        offset=offset,
        limit=limit,
    )
    return WidgetDataResponse(**data)


@router.delete("/{widget_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unpin_widget(
    widget_id: UUID,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_role("admin")),
):
    """Remove a widget from its dashboard."""
    result = await db.execute(
        select(Widget)
        .join(Dashboard, Widget.dashboard_id == Dashboard.id)
        .where(
            Widget.id == widget_id,
            Dashboard.tenant_id == tenant_id,
        )
    )
    widget = result.scalar_one_or_none()
    if not widget:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Widget not found"
        )
    await db.delete(widget)
    await db.commit()
