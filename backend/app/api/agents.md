# API Routes — Agent Rules

> Parent rules: [`/workspace/backend/agents.md`](../../agents.md)

## Thin Controllers

Route handlers validate input → call a service method → return a Pydantic response. Business logic lives in `app/services/`, never in route handlers.

```python
# Correct pattern
@router.post("/workflows", response_model=WorkflowResponse)
async def create_workflow(
    body: WorkflowCreate,
    service: WorkflowService = Depends(get_workflow_service),
) -> WorkflowResponse:
    return await service.create(body)
```

## REST Conventions

- All endpoints prefixed with `/api/v1/`.
- CRUD operations at `/api/v1/<resource>` (plural nouns).
- Actions use verb sub-paths: `/api/v1/workflows/{id}/execute`, `/api/v1/workflows/{id}/pin`.

## Endpoint Catalog

| Route file | Endpoints |
|---|---|
| `workflows.py` | CRUD for workflows (create, read, update, delete, list) |
| `executions.py` | Run workflow, get execution status, cancel |
| `dashboards.py` | CRUD for dashboards + widget layout management |
| `widgets.py` | Pin/unpin widgets, config overrides |
| `embed.py` | API key validation + widget data for embed mode |
| `schema.py` | Catalog: available tables, columns, types from serving layer |
| `ws.py` | WebSocket: live results, execution status streaming |
| `health.py` | Health check: `/health`, `/health/live`, `/health/ready` (no auth) |
| `metrics.py` | Prometheus scrape endpoint `GET /metrics` (no auth, internal-only) |

## Authentication & Tenant Context

| Context | Auth method | Tenant resolution |
|---|---|---|
| Canvas / Dashboards | Keycloak SSO (Bearer token validated against JWKS) | `tenant_id` claim from JWT |
| Embed | API key (`sk_live_...`) validated server-side | `tenant_id` column on `api_keys` table |
| Health check | None | N/A |

### Mandatory Dependencies for Authenticated Routes

Every authenticated route MUST inject these dependencies:

```python
@router.get("/{workflow_id}")
async def get_workflow(
    workflow_id: UUID,
    tenant_id: UUID = Depends(get_current_tenant_id),  # REQUIRED — data isolation
    user_id: UUID = Depends(get_current_user_id),       # REQUIRED — audit + ownership
    db: AsyncSession = Depends(get_db),
):
    ...
```

- `get_current_tenant_id` — extracts tenant from JWT; used in all WHERE clauses
- `get_current_user_id` — extracts user from JWT; used for `created_by` and access checks

### Tenant Filtering Rules

1. **All list endpoints** filter by `tenant_id` in the query.
2. **All single-item endpoints** (get, update, delete) filter by BOTH `id` AND `tenant_id` — prevents IDOR.
3. **All create endpoints** set `tenant_id` from auth context, never from request body.
4. **Cross-resource references** (e.g., widget referencing a workflow) must verify both resources share the same tenant.
5. **Return 404 (not 403)** when a resource exists but belongs to a different tenant — prevents enumeration.

## Paginated Responses

Use a generic paginated response pattern:

```python
class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
```

All list endpoints return paginated responses.

## Preview Endpoint

`POST /api/v1/preview` — Returns first 100 rows of a node's output.

- Request: `{ graph: {...}, target_node_id: "node-3" }`
- Response: `{ columns, rows, row_count, execution_ms, cache_hit, truncated }`
- Uses content-addressed Redis cache (tenant-scoped cache keys)
- Query constraints: `LIMIT 100`, `max_execution_time = 3s`, `max_memory_usage = 100MB`

## Dev Mode Auth Bypass

When `APP_ENV == "development"` and `X-Dev-Tenant` header is present:
- JWT validation is skipped
- Tenant context is set from the header value
- A dev user is returned: `sub="dev-user"`, `email="dev@flowforge.local"`, `roles=["admin"]`
- MUST be disabled in production

## WebSocket Endpoints

- `ws://localhost:8000/ws/dashboard/{dashboard_id}` — Live data push for dashboard widgets
- Backend subscribes to Redis pub/sub channel: `flowforge:{tenant_id}:execution:{execution_id}`
- Pushes execution status updates (pending → running → complete/error) and live data from Materialize
