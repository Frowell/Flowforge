"""Pydantic schemas for dashboard and widget endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.schemas.query import ColumnInfo

# ── Dashboard ────────────────────────────────────────────────────────────


class DashboardCreate(BaseModel):
    name: str
    description: str | None = None


class DashboardUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class DashboardResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    description: str | None
    created_by: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DashboardListResponse(BaseModel):
    items: list[DashboardResponse]
    total: int
    page: int
    page_size: int


# ── Widget ───────────────────────────────────────────────────────────────


class WidgetCreate(BaseModel):
    """Pin a workflow output node to a dashboard."""

    dashboard_id: UUID
    source_workflow_id: UUID
    source_node_id: str
    title: str | None = None
    layout: dict = {"x": 0, "y": 0, "w": 6, "h": 4}
    config_overrides: dict = {}


class WidgetUpdate(BaseModel):
    title: str | None = None
    layout: dict | None = None
    config_overrides: dict | None = None


class WidgetResponse(BaseModel):
    id: UUID
    dashboard_id: UUID
    source_workflow_id: UUID
    source_node_id: str
    title: str | None
    layout: dict
    config_overrides: dict
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Dashboard Filter ─────────────────────────────────────────────────────


class DashboardFilterCreate(BaseModel):
    filter_type: str
    target_column: str
    config: dict = {}
    position: int = 0


class DashboardFilterResponse(BaseModel):
    id: UUID
    dashboard_id: UUID
    filter_type: str
    target_column: str
    config: dict
    position: int

    model_config = {"from_attributes": True}


# ── Widget Data ─────────────────────────────────────────────────────────


class WidgetDataResponse(BaseModel):
    columns: list[ColumnInfo]
    rows: list[dict]
    total_rows: int
    execution_ms: float
    cache_hit: bool
    offset: int
    limit: int
    chart_config: dict | None = None


# ── API Key ───────────────────────────────────────────────────────────


class APIKeyCreate(BaseModel):
    label: str | None = None
    scoped_widget_ids: list[UUID] | None = None
    rate_limit: int | None = None


class APIKeyResponse(BaseModel):
    id: UUID
    label: str | None
    scoped_widget_ids: list[UUID] | None
    rate_limit: int | None
    created_at: datetime
    revoked_at: datetime | None

    model_config = {"from_attributes": True}


class APIKeyCreateResponse(APIKeyResponse):
    """Returned only on creation — includes the raw key (shown once)."""

    key: str
