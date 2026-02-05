# Backend — Agent Rules

> Parent rules: [`/workspace/agents.md`](../agents.md) | Architecture: [`/workspace/planning.md`](../planning.md)

## Directory Structure

```
backend/
├── app/
│   ├── api/
│   │   ├── deps.py              # Dependency injection (DB sessions, services, auth)
│   │   └── routes/              # Thin route handlers
│   ├── core/
│   │   ├── config.py            # pydantic-settings Settings singleton
│   │   ├── database.py          # Async SQLAlchemy engine + session factory
│   │   ├── clickhouse.py        # ClickHouse async client
│   │   ├── redis.py             # Redis async client
│   │   ├── auth.py              # Keycloak OIDC + API key validation
│   │   ├── logging_config.py    # structlog configuration (JSON/console output)
│   │   ├── metrics.py           # Prometheus metrics registry (all flowforge_* metrics)
│   │   └── middleware.py        # ObservabilityMiddleware (request IDs, HTTP metrics)
│   ├── models/                  # SQLAlchemy ORM models (PostgreSQL only)
│   ├── schemas/                 # Pydantic request/response schemas
│   └── services/                # Business logic layer
├── tests/                       # Mirrors app/ structure
├── alembic/                     # Database migrations
│   └── versions/
└── pyproject.toml
```

## Dependency Injection

All services and database sessions are injected via `Depends()` from `app/api/deps.py`. Route handlers never instantiate services directly.

```python
# Correct
async def get_workflow(
    workflow_id: UUID,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db),
    compiler: WorkflowCompiler = Depends(get_compiler),
) -> WorkflowResponse: ...

# Wrong — never do this in a route
async def get_workflow(workflow_id: UUID):
    db = AsyncSession(engine)  # NO
    compiler = WorkflowCompiler()  # NO
```

## Async Everywhere

- All route handlers, service methods, and database operations use `async/await`.
- All query compilation and execution runs inline — no task queue. Latency is critical for real-time streaming BI.

## SQLAlchemy Models = PostgreSQL App Metadata ONLY

Models in `app/models/` map to PostgreSQL tables that store application metadata:
- Workflows, dashboards, widgets, users, API keys, dashboard filters

Models do NOT exist for ClickHouse tables, Materialize views, or Redis data. Those are accessed via raw clients in `app/core/`.

## Multi-Tenancy in Models and Routes

### TenantMixin

All tenant-scoped models use the `TenantMixin` from `app/core/database.py`, which provides a `tenant_id: UUID` column (NOT NULL, indexed). Tenant-scoped models: `User`, `Workflow`, `Dashboard`, `APIKey`.

Child models (`Widget`, `DashboardFilter`) inherit tenant scope from their parent `Dashboard` — they do NOT carry their own `tenant_id` column.

### Route Handler Pattern — ALWAYS Filter by Tenant

Every route handler that reads or writes tenant-scoped data MUST inject `tenant_id` via `Depends(get_current_tenant_id)` and use it in all queries. A missing tenant filter is a data leak.

```python
# CORRECT — tenant-filtered query
@router.get("")
async def list_workflows(
    tenant_id: UUID = Depends(get_current_tenant_id),
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    q = select(Workflow).where(Workflow.tenant_id == tenant_id)
    ...

# CORRECT — tenant-checked create
@router.post("")
async def create_workflow(
    body: WorkflowCreate,
    tenant_id: UUID = Depends(get_current_tenant_id),
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    workflow = Workflow(
        name=body.name,
        tenant_id=tenant_id,
        created_by=user_id,
        ...
    )

# CORRECT — tenant-checked single-item fetch (prevents IDOR)
@router.get("/{workflow_id}")
async def get_workflow(
    workflow_id: UUID,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Workflow).where(
            Workflow.id == workflow_id,
            Workflow.tenant_id == tenant_id,  # REQUIRED
        )
    )

# WRONG — no tenant filter (data leak!)
@router.get("/{workflow_id}")
async def get_workflow(workflow_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))  # NO
```

### Cross-Tenant Reference Prevention

When creating a `Widget`, verify that BOTH the target `Dashboard` AND the source `Workflow` belong to the caller's tenant. Never allow a widget to reference a workflow from a different tenant.

### Tenant Context in Services

Services that interact with external stores or caching must receive `tenant_id`:
- **PreviewService**: Cache keys MUST include `tenant_id` to prevent cross-tenant cache leaks
- **WorkflowCompiler**: Compiled SQL MUST inject `WHERE symbol IN (:allowed_symbols)` for serving-layer market data tables (these tables have no `tenant_id` column — isolation is via symbol-based ACL)
- **SchemaRegistry**: Catalog is cached per tenant (different tenants may see different tables)
- **WebSocketManager**: Pub/sub channels are prefixed with `tenant_id`

## Pydantic Schema Naming

| Suffix | Purpose |
|---|---|
| `*Create` | Request body for POST |
| `*Update` | Request body for PATCH/PUT |
| `*Response` | Single-item response |
| `*ListResponse` | Paginated list response |

## Service Layer

| Service | Responsibility |
|---|---|
| `schema_registry` | Reads schemas from ClickHouse `system.columns` + Materialize `mz_catalog`, caches in Redis |
| `schema_engine` | Server-side DAG schema validation; registered transform per node type |
| `workflow_compiler` | Topological sort → SQLGlot AST → merge adjacent nodes → target per segment |
| `query_router` | Freshness-based dispatch to ClickHouse / Materialize / Redis |
| `formula_parser` | `[column]` bracket syntax → AST → SQL; validates against input schema |
| `websocket_manager` | Execution status + live data pushes; Redis pub/sub for multi-instance |

## Observability

- **Structured logging**: `structlog` with `contextvars` for async-safe per-request context (`request_id`, `tenant_id`, `user_id`). Development uses console output; production uses JSON.
- **Metrics**: `prometheus-client` with all metrics defined centrally in `app/core/metrics.py`. Scraped via `GET /metrics`.
- **Request correlation**: `ObservabilityMiddleware` generates a UUID4 `request_id` per HTTP request, binds it to structlog context, and returns it as `X-Request-ID` response header.
- **Health checks**: `/health/live` (liveness), `/health/ready` (readiness — checks PostgreSQL, Redis, ClickHouse). Legacy `/health` preserved for backward compatibility.

## SQL Generation

- **Always** use SQLGlot to build queries. Never string-concatenate SQL.
- Use `dialect="clickhouse"` for ClickHouse targets.
- Use `dialect="postgres"` for Materialize targets (PG wire protocol).
- Parameterize all user-supplied values.

## Testing Conventions

- Use `httpx.AsyncClient` for API integration tests.
- `asyncio_mode = "auto"` in pytest config.
- Mock external stores (ClickHouse, Materialize, Redis) — never require running instances.
- Factory functions for test data, not deep fixture chains.

## Configuration

All config via `pydantic-settings` `Settings` class in `app/core/config.py`. Environment variables are the source. Never call `os.getenv()` directly.

## Auth Dependencies

Authentication and tenant context are provided by two FastAPI dependencies in `app/core/auth.py` and `app/api/deps.py`:

| Dependency | Returns | Used for |
|---|---|---|
| `get_current_user_id` | `UUID` — user's Keycloak subject | Tracking `created_by`, per-user access checks |
| `get_current_tenant_id` | `UUID` — tenant from JWT claim | ALL data filtering, cache scoping, query isolation |
| `get_current_user_claims` | `dict` — full JWT payload | Role checks (`admin`, `analyst`, `viewer`) |

All authenticated routes (everything except `/health` and `/embed`) MUST inject at minimum `get_current_tenant_id`. The embed route uses API key auth, which resolves to a tenant via the `api_keys` table.

## Application Factory

The FastAPI app is created via `create_app()` in `app/main.py` with an async `lifespan` context manager:

- **Startup**: Initialize PostgreSQL, ClickHouse, Materialize, Redis clients; refresh SchemaRegistry
- **Shutdown**: Close all client connections gracefully
- The `SchemaRegistry` singleton is stored on `app.state.schema_registry`

## Dev Mode Authentication

For development without Keycloak, the backend accepts a `X-Dev-Tenant` header that sets tenant context directly:

- Controlled by `APP_ENV == "development"` in Settings
- MUST be disabled in production — never accept `X-Dev-Tenant` when `APP_ENV != "development"`
- Returns a dev user with `sub="dev-user"`, `email="dev@flowforge.local"`, `roles=["admin"]`
- The `X-Dev-Tenant` check runs BEFORE JWT validation in the auth dependency

## Preview System (3-Layer Execution Model)

Data preview ("click a node, see first 100 rows") uses three layers:

1. **Frontend debounce + cancellation**: 300ms debounce after last click; cancel in-flight requests on node switch
2. **Content-addressed Redis cache**: Cache key = hash of `(tenant_id, target_node_id, subgraph_configs, offset, limit)`. TTL: 5 minutes. Cache hit = instant response
3. **Query constraints (server-side safety)**: `LIMIT 100`, `max_execution_time = 3s`, `max_memory_usage = 100MB`, `max_rows_to_read = 10M`

Preview endpoint: `POST /api/v1/preview` — accepts `{ graph, target_node_id }`, returns `{ columns, rows, row_count, execution_ms, cache_hit, truncated }`.

## Settings Overview

All configuration via `pydantic-settings` `Settings` class in `app/core/config.py`. Key groups:

| Group | Variables |
|-------|-----------|
| App | `APP_ENV` |
| PostgreSQL | `DATABASE_URL` |
| ClickHouse | `CLICKHOUSE_HOST`, `CLICKHOUSE_PORT` |
| Materialize | `MATERIALIZE_HOST`, `MATERIALIZE_PORT` |
| Redis | `REDIS_URL` |
| Auth | `KEYCLOAK_URL`, `KEYCLOAK_REALM`, `KEYCLOAK_CLIENT_ID`, `KEYCLOAK_PUBLIC_KEY` |
| CORS | `CORS_ORIGINS` |
| Preview | `PREVIEW_CACHE_TTL`, `PREVIEW_ROW_LIMIT`, `PREVIEW_MAX_EXECUTION_TIME`, `PREVIEW_MAX_MEMORY` |
| Pagination | `MAX_PAGE_OFFSET` (10,000 hard cap), `DEFAULT_PAGE_SIZE` (50) |

ClickHouse uses **HTTP protocol** (port 8123) via `clickhouse-connect`, not the native protocol.

## Production Database Differences

In production, PostgreSQL and Redis are managed GCP services (Cloud SQL, Memorystore), not pods:
- Connection strings come from Secret Manager via Workload Identity
- Cloud SQL uses Private Service Access (no public IP)
- Cloud SQL Proxy sidecar not required when using Workload Identity + direct private IP
- Redis uses Memorystore private endpoint (VPC-internal)
