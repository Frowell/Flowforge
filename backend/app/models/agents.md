# Models — Agent Rules

> Parent rules: [`/workspace/backend/agents.md`](../../agents.md) | Architecture: [`/workspace/planning.md`](../../../planning.md)

## What Belongs Here

SQLAlchemy ORM models for PostgreSQL application metadata:

| Model | Key columns |
|---|---|
| `Workflow` | id, name, description, graph_json (JSONB — serialized React Flow state), created_by, created_at, updated_at |
| `Dashboard` | id, name, description, created_by, created_at, updated_at |
| `Widget` | id, dashboard_id (FK), source_workflow_id (FK), source_node_id, layout (JSONB: {x,y,w,h}), config_overrides (JSONB), created_at |
| `User` | id, email, role, created_at |
| `DashboardFilter` | id, dashboard_id (FK), filter_type, target_column, config (JSONB), position |
| `APIKey` | id, key_hash, user_id (FK), scoped_widget_ids, created_at, revoked_at |

## What Does NOT Belong Here

- ClickHouse table models — accessed via raw client in `app/core/clickhouse.py`
- Materialize view models — accessed via raw client or PG wire protocol
- Redis data models — accessed via `app/core/redis.py`
- Query results — never stored in PostgreSQL

## Conventions

- Use `DeclarativeBase` (SQLAlchemy 2.0), not the legacy `declarative_base()`.
- Type all columns with `Mapped[T]` and `mapped_column()`.
- UUID primary keys (not auto-increment integers).
- Every model has `created_at` and `updated_at` timestamps.
- Use `relationship()` with explicit `back_populates` on both sides.
- Store flexible/nested data as JSONB (`graph_json`, `layout`, `config_overrides`, `config`).
- Never add columns for data that belongs in the serving layer.

## Multi-Tenancy

### TenantMixin

All tenant-scoped models use the `TenantMixin` from `app/core/database.py`:

```python
class TenantMixin:
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
```

### Tenant-Scoped Models

| Model | Has `tenant_id`? | Notes |
|---|---|---|
| `User` | **Yes** | Users belong to a tenant |
| `Workflow` | **Yes** | Workflows are tenant-isolated |
| `Dashboard` | **Yes** | Dashboards are tenant-isolated |
| `APIKey` | **Yes** | API keys are tenant-scoped |
| `Widget` | No | Inherits tenant from parent `Dashboard` (via `dashboard_id` FK) |
| `DashboardFilter` | No | Inherits tenant from parent `Dashboard` (via `dashboard_id` FK) |

### Key columns (updated)

| Model | Key columns |
|---|---|
| `Workflow` | id, **tenant_id**, name, description, graph_json (JSONB), created_by, created_at, updated_at |
| `Dashboard` | id, **tenant_id**, name, description, created_by, created_at, updated_at |
| `Widget` | id, dashboard_id (FK), source_workflow_id (FK), source_node_id, layout (JSONB), config_overrides (JSONB), created_at |
| `User` | id, **tenant_id**, email, role, created_at |
| `DashboardFilter` | id, dashboard_id (FK), filter_type, target_column, config (JSONB), position |
| `APIKey` | id, **tenant_id**, key_hash, user_id (FK), scoped_widget_ids, created_at, revoked_at |

### Cross-Tenant Reference Prevention

When creating a `Widget`, the application layer MUST verify that both `dashboard_id` and `source_workflow_id` resolve to the same tenant. This is checked in the route handler, not via database constraints (since `Widget` doesn't have its own `tenant_id` column).
