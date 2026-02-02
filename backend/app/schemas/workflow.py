"""Pydantic schemas for workflow endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class WorkflowCreate(BaseModel):
    name: str
    description: str | None = None
    graph_json: dict = {}


class WorkflowUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    graph_json: dict | None = None


class WorkflowResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    description: str | None
    graph_json: dict
    created_by: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WorkflowListResponse(BaseModel):
    items: list[WorkflowResponse]
    total: int
    page: int
    page_size: int


class WorkflowVersionResponse(BaseModel):
    id: UUID
    workflow_id: UUID
    version_number: int
    graph_json: dict
    created_by: UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class WorkflowVersionListResponse(BaseModel):
    items: list[WorkflowVersionResponse]
    total: int
