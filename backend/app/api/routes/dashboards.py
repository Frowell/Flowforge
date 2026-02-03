"""Dashboard CRUD endpoints.

All queries are scoped by tenant_id from the JWT.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_tenant_id, get_current_user_id, get_db, require_role
from app.models.audit_log import AuditAction, AuditResourceType
from app.models.dashboard import Dashboard, Widget
from app.services.audit_service import AuditService
from app.schemas.dashboard import (
    DashboardCreate,
    DashboardListResponse,
    DashboardResponse,
    DashboardUpdate,
    WidgetResponse,
)

router = APIRouter()


@router.get("", response_model=DashboardListResponse)
async def list_dashboards(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    total_q = await db.execute(
        select(func.count(Dashboard.id)).where(Dashboard.tenant_id == tenant_id)
    )
    total = total_q.scalar_one()

    q = (
        select(Dashboard)
        .where(Dashboard.tenant_id == tenant_id)
        .order_by(Dashboard.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(q)
    dashboards = result.scalars().all()

    return DashboardListResponse(
        items=[DashboardResponse.model_validate(d) for d in dashboards],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{dashboard_id}", response_model=DashboardResponse)
async def get_dashboard(
    dashboard_id: UUID,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Dashboard).where(
            Dashboard.id == dashboard_id,
            Dashboard.tenant_id == tenant_id,
        )
    )
    dashboard = result.scalar_one_or_none()
    if not dashboard:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dashboard not found")
    return DashboardResponse.model_validate(dashboard)


@router.post("", response_model=DashboardResponse, status_code=status.HTTP_201_CREATED)
async def create_dashboard(
    body: DashboardCreate,
    tenant_id: UUID = Depends(get_current_tenant_id),
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_role("admin", "analyst")),
):
    dashboard = Dashboard(
        name=body.name,
        description=body.description,
        tenant_id=tenant_id,
        created_by=user_id,
    )
    db.add(dashboard)
    await db.flush()

    audit = AuditService(db)
    await audit.log(
        tenant_id=tenant_id,
        user_id=user_id,
        action=AuditAction.CREATED,
        resource_type=AuditResourceType.DASHBOARD,
        resource_id=dashboard.id,
        metadata={"name": body.name},
    )

    await db.commit()
    await db.refresh(dashboard)
    return DashboardResponse.model_validate(dashboard)


@router.patch("/{dashboard_id}", response_model=DashboardResponse)
async def update_dashboard(
    dashboard_id: UUID,
    body: DashboardUpdate,
    tenant_id: UUID = Depends(get_current_tenant_id),
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_role("admin", "analyst")),
):
    result = await db.execute(
        select(Dashboard).where(
            Dashboard.id == dashboard_id,
            Dashboard.tenant_id == tenant_id,
        )
    )
    dashboard = result.scalar_one_or_none()
    if not dashboard:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dashboard not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(dashboard, field, value)

    audit = AuditService(db)
    await audit.log(
        tenant_id=tenant_id,
        user_id=user_id,
        action=AuditAction.UPDATED,
        resource_type=AuditResourceType.DASHBOARD,
        resource_id=dashboard.id,
        metadata={"fields": list(update_data.keys())},
    )

    await db.commit()
    await db.refresh(dashboard)
    return DashboardResponse.model_validate(dashboard)


@router.delete("/{dashboard_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dashboard(
    dashboard_id: UUID,
    tenant_id: UUID = Depends(get_current_tenant_id),
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_role("admin", "analyst")),
):
    result = await db.execute(
        select(Dashboard).where(
            Dashboard.id == dashboard_id,
            Dashboard.tenant_id == tenant_id,
        )
    )
    dashboard = result.scalar_one_or_none()
    if not dashboard:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dashboard not found")

    audit = AuditService(db)
    await audit.log(
        tenant_id=tenant_id,
        user_id=user_id,
        action=AuditAction.DELETED,
        resource_type=AuditResourceType.DASHBOARD,
        resource_id=dashboard.id,
        metadata={"name": dashboard.name},
    )

    await db.delete(dashboard)
    await db.commit()


@router.get("/{dashboard_id}/widgets", response_model=list[WidgetResponse])
async def list_dashboard_widgets(
    dashboard_id: UUID,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    """List all widgets belonging to a dashboard."""
    # Verify dashboard belongs to tenant
    dash_result = await db.execute(
        select(Dashboard).where(
            Dashboard.id == dashboard_id,
            Dashboard.tenant_id == tenant_id,
        )
    )
    if not dash_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dashboard not found")

    result = await db.execute(
        select(Widget).where(Widget.dashboard_id == dashboard_id)
    )
    widgets = result.scalars().all()
    return [WidgetResponse.model_validate(w) for w in widgets]
