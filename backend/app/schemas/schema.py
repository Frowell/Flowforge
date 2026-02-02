"""Pydantic schemas for the schema registry / catalog endpoints."""

from pydantic import BaseModel


class ColumnSchema(BaseModel):
    name: str
    dtype: str
    nullable: bool = True
    description: str | None = None


class TableSchema(BaseModel):
    name: str
    database: str
    source: str  # "clickhouse" | "materialize" | "redis"
    columns: list[ColumnSchema]


class CatalogResponse(BaseModel):
    """Full schema catalog returned to the frontend."""

    tables: list[TableSchema]
