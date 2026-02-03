"""Audit logging service.

Provides fire-and-forget audit record creation and paginated queries.
"""

import structlog
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditAction, AuditLog, AuditResourceType

logger = structlog.stdlib.get_logger(__name__)


class AuditService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def log(
        self,
        tenant_id: UUID,
        user_id: UUID,
        action: AuditAction,
        resource_type: AuditResourceType,
        resource_id: UUID,
        metadata: dict | None = None,
    ) -> None:
        """Create an audit log record. Fire-and-forget — errors are logged, not raised."""
        try:
            entry = AuditLog(
                tenant_id=tenant_id,
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                metadata_=metadata,
            )
            self.db.add(entry)
            await self.db.flush()
        except Exception:
            logger.exception(
                "audit_log_failed",
                action=action.value,
                resource_type=resource_type.value,
                resource_id=str(resource_id),
            )

    async def list_events(
        self,
        tenant_id: UUID,
        resource_type: AuditResourceType | None = None,
        resource_id: UUID | None = None,
        action: AuditAction | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        """Query audit events for a tenant with optional filters."""
        conditions = [AuditLog.tenant_id == tenant_id]

        if resource_type is not None:
            conditions.append(AuditLog.resource_type == resource_type)
        if resource_id is not None:
            conditions.append(AuditLog.resource_id == resource_id)
        if action is not None:
            conditions.append(AuditLog.action == action)

        total_q = await self.db.execute(
            select(func.count(AuditLog.id)).where(*conditions)
        )
        total = total_q.scalar_one()

        q = (
            select(AuditLog)
            .where(*conditions)
            .order_by(AuditLog.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.db.execute(q)
        events = result.scalars().all()

        return {
            "items": events,
            "total": total,
            "offset": offset,
            "limit": limit,
        }
