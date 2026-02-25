"""Pydantic schemas for query execution and results."""

from uuid import UUID

from pydantic import BaseModel


class ExecutionRequest(BaseModel):
    """Request to execute a workflow."""

    workflow_id: UUID


class ExecutionStatusResponse(BaseModel):
    id: UUID
    workflow_id: UUID
    status: str  # pending | running | completed | failed | cancelled
    started_at: str | None = None
    completed_at: str | None = None
    node_statuses: dict[str, "NodeStatusResponse"] = {}


class NodeStatusResponse(BaseModel):
    status: str  # pending | running | completed | failed | skipped | cancelled
    started_at: str | None = None
    completed_at: str | None = None
    rows_processed: int | None = None
    error: str | None = None


class ExecutionHistoryItem(BaseModel):
    id: UUID
    workflow_id: UUID
    status: str
    started_by: UUID
    node_statuses: dict = {}
    started_at: str | None = None
    completed_at: str | None = None
    error_message: str | None = None
    created_at: str | None = None

    model_config = {"from_attributes": True}


class ExecutionListResponse(BaseModel):
    items: list[ExecutionHistoryItem]
    total: int
    page: int
    page_size: int


class QueryResultResponse(BaseModel):
    """Preview data returned for a node or widget."""

    columns: list["ColumnInfo"]
    rows: list[dict]
    total_rows: int
    truncated: bool = False


class ColumnInfo(BaseModel):
    name: str
    dtype: str
