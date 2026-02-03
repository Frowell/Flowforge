"""Pydantic schemas for audit log endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class AuditLogResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    user_id: UUID
    action: str
    resource_type: str
    resource_id: UUID
    metadata: dict | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    items: list[AuditLogResponse]
    total: int
    offset: int
    limit: int
