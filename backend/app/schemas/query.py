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


class QueryResultResponse(BaseModel):
    """Preview data returned for a node or widget."""

    columns: list["ColumnInfo"]
    rows: list[dict]
    total_rows: int
    truncated: bool = False


class ColumnInfo(BaseModel):
    name: str
    dtype: str
