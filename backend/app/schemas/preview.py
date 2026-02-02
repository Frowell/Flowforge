"""Pydantic schemas for data preview requests and responses."""

from uuid import UUID

from pydantic import BaseModel

from app.schemas.query import ColumnInfo


class GraphPayload(BaseModel):
    """Serialized canvas DAG."""

    nodes: list[dict]
    edges: list[dict]


class PreviewRequest(BaseModel):
    """Request to preview a node's output data."""

    workflow_id: UUID
    target_node_id: str
    graph: GraphPayload
    offset: int = 0
    limit: int = 100


class PreviewResponse(BaseModel):
    """Preview data returned for a node."""

    columns: list[ColumnInfo]
    rows: list[dict]
    total_estimate: int
    execution_ms: float
    cache_hit: bool
    offset: int
    limit: int
