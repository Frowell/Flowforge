"""Audit log model.

Records all significant actions for compliance and debugging.
Indexed by (tenant_id, created_at) for efficient tenant-scoped queries.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Index, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TenantMixin, UUIDPrimaryKeyMixin


class AuditAction(str, enum.Enum):
    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"
    EXECUTED = "executed"
    REVOKED = "revoked"


class AuditResourceType(str, enum.Enum):
    WORKFLOW = "workflow"
    DASHBOARD = "dashboard"
    WIDGET = "widget"
    API_KEY = "api_key"


class AuditLog(Base, UUIDPrimaryKeyMixin, TenantMixin):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_logs_tenant_created", "tenant_id", "created_at"),)

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    action: Mapped[AuditAction] = mapped_column(
        Enum(AuditAction, name="audit_action"), nullable=False
    )
    resource_type: Mapped[AuditResourceType] = mapped_column(
        Enum(AuditResourceType, name="audit_resource_type"), nullable=False
    )
    resource_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    metadata_: Mapped[dict | None] = mapped_column(
        "metadata", JSONB, default=None, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
