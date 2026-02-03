"""Audit log endpoints.

Read-only access to audit trail. Admin role required.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_tenant_id, get_db, require_role
from app.models.audit_log import AuditAction, AuditResourceType
from app.schemas.audit import AuditLogListResponse, AuditLogResponse
from app.services.audit_service import AuditService

router = APIRouter()


@router.get("", response_model=AuditLogListResponse)
async def list_audit_logs(
    resource_type: str | None = Query(None),
    resource_id: UUID | None = Query(None),
    action: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_role("admin")),
):
    """List audit events for the current tenant. Admin only."""
    service = AuditService(db)

    rt = AuditResourceType(resource_type) if resource_type else None
    act = AuditAction(action) if action else None

    result = await service.list_events(
        tenant_id=tenant_id,
        resource_type=rt,
        resource_id=resource_id,
        action=act,
        limit=limit,
        offset=offset,
    )

    return AuditLogListResponse(
        items=[_to_response(e) for e in result["items"]],
        total=result["total"],
        offset=result["offset"],
        limit=result["limit"],
    )


def _to_response(entry) -> AuditLogResponse:
    return AuditLogResponse(
        id=entry.id,
        tenant_id=entry.tenant_id,
        user_id=entry.user_id,
        action=entry.action.value,
        resource_type=entry.resource_type.value,
        resource_id=entry.resource_id,
        metadata=entry.metadata_,
        created_at=entry.created_at,
    )
