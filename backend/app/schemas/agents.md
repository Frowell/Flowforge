# Pydantic Schemas — Agent Rules

> Parent rules: [`/workspace/backend/agents.md`](../../agents.md)

## Purpose

This directory contains Pydantic v2 request/response models for all API endpoints. Schemas define the contract between the frontend and backend — they validate incoming data and serialize outgoing responses.

## File Catalog

| File | Schemas |
|------|---------|
| `workflow.py` | WorkflowCreate, WorkflowUpdate, WorkflowResponse, WorkflowListResponse, WorkflowVersionResponse, WorkflowExportResponse, WorkflowImportRequest |
| `dashboard.py` | DashboardCreate, DashboardUpdate, DashboardResponse, DashboardListResponse, WidgetCreate, WidgetUpdate, WidgetResponse, DashboardFilterCreate, DashboardFilterResponse |
| `preview.py` | PreviewRequest, PreviewResponse |
| `query.py` | QueryRequest, QueryResponse |
| `schema.py` | TableSchema, ColumnSchema, SchemaCatalogResponse |
| `audit.py` | AuditLogResponse, AuditLogListResponse |
| `template.py` | TemplateResponse, TemplateListResponse |

## Naming Convention

| Suffix | HTTP Method | Purpose |
|--------|-------------|---------|
| `*Create` | `POST` | Request body for resource creation |
| `*Update` | `PATCH` | Request body for partial update (all fields optional) |
| `*Response` | All | Single-item response |
| `*ListResponse` | `GET` (list) | Paginated list response |

Follow this convention strictly. Do not invent new suffixes.

## Patterns

### Model Config

All response schemas that map from SQLAlchemy models must include:

```python
model_config = {"from_attributes": True}
```

This enables `WorkflowResponse.model_validate(workflow_orm_instance)`.

### Paginated Responses

All list endpoints return paginated responses with consistent structure:

```python
class WorkflowListResponse(BaseModel):
    items: list[WorkflowResponse]
    total: int
    page: int
    page_size: int
```

### Optional Fields in Updates

Update schemas make all fields optional so callers only send changed fields:

```python
class WorkflowUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    graph_json: dict | None = None
```

Route handlers use `body.model_dump(exclude_unset=True)` to apply only the fields that were actually sent.

### UUID Fields

- Use `UUID` type (from `uuid` stdlib) for all ID fields.
- Response schemas expose `tenant_id`, `created_by`, and timestamps.
- Create schemas do NOT accept `tenant_id` or `created_by` — those are set from auth context in route handlers.

### graph_json

Workflow and version schemas use `dict` for `graph_json` (the serialized React Flow state). This is stored as JSONB in PostgreSQL. Do not attempt to define a Pydantic model for the internal graph structure — it is opaque to the backend (the frontend owns the schema).

## Rules

- **Schemas are data contracts, not business logic.** Validation beyond type checking (e.g., "does this workflow ID exist?") belongs in route handlers or services.
- **Never import from `models/`** — schemas and ORM models are separate layers. Use `model_config = {"from_attributes": True}` for ORM → schema conversion.
- **Never import from `services/` or `api/`** — schemas are a leaf dependency.
- **Keep schemas thin** — no methods, no computed properties, no database access. Pure data containers.
- **Match frontend TypeScript types** — the TypeScript types in `frontend/src/shared/query-engine/types.ts` should mirror these schemas. When adding a field here, add it there too.
