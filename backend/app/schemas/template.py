"""Pydantic schemas for template endpoints."""

from pydantic import BaseModel


class TemplateResponse(BaseModel):
    id: str
    name: str
    description: str
    category: str
    tags: list[str]
    graph_json: dict
    thumbnail: str | None = None


class TemplateListResponse(BaseModel):
    items: list[TemplateResponse]


class TemplateInstantiateRequest(BaseModel):
    name: str | None = None
