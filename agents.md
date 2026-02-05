# FlowForge — Global Agent Rules

> Authoritative source: [`/workspace/planning.md`](./planning.md)
> Implementation specification: [`/workspace/Application plan.md`](./Application%20plan.md)
> Every agent working in this repository MUST follow these rules without exception.

## Project Identity

FlowForge is a visual analytics platform for **fintech trading markets**. It combines an Alteryx-style no-code canvas with embedded BI capabilities. Users build data transformation workflows by dragging nodes on a canvas, then pin outputs to dashboards or embed them in external applications.

FlowForge compiles workflows to SQL against a **read-only** serving layer (ClickHouse, Materialize, Redis). It has three modes — Canvas (author), Dashboards (viewer), Embed (headless) — backed by a single FastAPI backend.

### Single Application, Three Modes

| Mode | URL | Auth | Purpose |
|------|-----|------|---------|
| Canvas | `/canvas` | OIDC (Keycloak) | Author mode — React Flow workspace for building workflows |
| Dashboards | `/dashboards` | OIDC (Keycloak) | Viewer mode — widget grid from pinned canvas outputs |
| Embed | `/embed/:widget_id` | API key (stateless) | Headless mode — chromeless iframe |

---

## 6 Absolute Architectural Rules

1. **App does NOT own data ingestion.** The serving layer (ClickHouse / Materialize / Redis) is read-only from this application's perspective. Never write DDL, INSERT, or CREATE VIEW statements against these stores. The data pipeline is a separate workstream.

2. **Workflows compile to SQL via SQLGlot, NOT DataFrames.** The backend is a thin translation layer, not a compute engine. Pandas and Polars may only be used for formatting preview results or generating test fixtures — never for query execution.

3. **Schema propagation is the core.** Every node type declares its input → output schema transform in BOTH TypeScript (client-side, instant feedback) and Python (server-side, authoritative). If you add or modify a node type, both implementations must be updated and kept in sync.

4. **Query merging is mandatory.** Adjacent compatible nodes MUST be merged into single SQL queries by the workflow compiler. A linear chain of Filter → Select → Sort on the same table produces ONE query, not three. Never generate one-query-per-node output.

5. **Charts use the same component everywhere.** Canvas preview, dashboard widget, and embed iframe all import from `shared/components/charts/`. There are no per-mode chart variants. One implementation, one set of bugs, one place to fix.

6. **Dashboards are projections of workflows.** Widgets point to workflow output nodes (`source_workflow_id` + `source_node_id`). Widgets do NOT store their own queries. No independent dashboard queries exist.

---

## Tech Stack Constraints

| Layer | Stack |
|---|---|
| Backend runtime | Python 3.12+, async FastAPI, Uvicorn |
| ORM | SQLAlchemy 2.0 async (`DeclarativeBase`, `Mapped`, `mapped_column`) |
| App database | PostgreSQL 16 (metadata only — workflows, dashboards, widgets, users) |
| Migrations | Alembic (async) |
| Execution | Direct async — all compilation and query execution inline in FastAPI |
| SQL generation | SQLGlot (never string concatenation) |
| Frontend framework | React 19, strict TypeScript |
| Client state | Zustand (UI state only) |
| Server state | TanStack Query (all fetched data) |
| Styling | Tailwind CSS only — no CSS modules, styled-components, or inline styles |
| Canvas library | `@xyflow/react` v12+ (do NOT import from `reactflow`) |
| Charts | Shared components in `shared/components/charts/` |
| Dashboard layout | `react-grid-layout` |

---

## Code Conventions

- **Python**: Ruff for linting and formatting
- **TypeScript**: ESLint + Prettier
- **Migrations**: Always via Alembic — never hand-edit DDL
- **Import alias**: `@/` maps to `frontend/src/`
- **API prefix**: All REST endpoints under `/api/v1/`
- **Configuration**: `pydantic-settings` `Settings` singleton — never `os.getenv()`

---

## Git Branching Strategy

FlowForge uses **trunk-based development** with short-lived feature branches. `main` is always deployable.

### Branch Naming

All branches follow the pattern `<type>/<short-description>`:

| Prefix | Purpose | Example |
|--------|---------|---------|
| `feat/` | New feature or capability | `feat/groupby-node` |
| `fix/` | Bug fix | `fix/preview-cache-tenant-leak` |
| `refactor/` | Code restructuring (no behavior change) | `refactor/compiler-merge-logic` |
| `docs/` | Documentation only | `docs/gcp-terraform-requirements` |
| `chore/` | Tooling, CI, dependencies | `chore/upgrade-sqlalchemy` |
| `infra/` | Infrastructure / Terraform changes | `infra/gke-cluster-module` |

### Branch Rules

1. **Branch from `main`, merge to `main`.** No long-lived develop, staging, or release branches. Environment promotion is handled by CI/CD workflows, not branches.

2. **One concern per branch.** A branch implements one feature, fixes one bug, or completes one task. If a change spans multiple concerns, split it into sequential PRs.

3. **Keep branches short-lived.** Target < 3 days. If a feature is large, break it into incremental PRs that each leave `main` in a working state (feature flags or incremental implementation over dead-code paths).

4. **Rebase before merging.** Keep a clean linear history. Before opening a PR, rebase onto the latest `main`:
   ```
   git fetch origin
   git rebase origin/main
   ```

5. **Squash-merge for feature branches.** Each PR becomes one commit on `main` with a descriptive message. This keeps the main branch history readable.

6. **Never commit directly to `main`.** All changes go through pull requests with CI checks passing.

7. **Delete branches after merge.** Remote branches are deleted automatically by GitHub after PR merge. Clean up local branches periodically.

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]
```

| Type | When to use |
|------|------------|
| `feat` | New feature (triggers minor version bump) |
| `fix` | Bug fix (triggers patch version bump) |
| `refactor` | Code change that neither fixes a bug nor adds a feature |
| `docs` | Documentation only |
| `chore` | Build, CI, tooling changes |
| `test` | Adding or updating tests |

**Scope** is optional but encouraged: `feat(compiler): add query merging for GroupBy nodes`

### Large Feature Workflow

For features that span multiple PRs (e.g., "Add GroupBy node" requires backend + frontend + tests):

1. Create a tracking issue describing the full feature
2. Implement in sequential PRs, each building on the last:
   - `feat/groupby-backend-schema` — schema transform + compiler rule
   - `feat/groupby-frontend-node` — React Flow node + config panel
   - `feat/groupby-tests` — integration tests
3. Each PR is independently reviewable and leaves `main` working
4. No feature branch that lives for weeks — break it down

### Alembic Migration Branches

Database migrations require extra care:

- **Never branch from a branch that has an uncommitted migration.** Parallel migration branches cause Alembic head conflicts.
- If two branches both need migrations, merge the first before creating the second's migration.
- Migration files include a `down_revision` pointer — rebasing a branch with a migration means re-generating the migration after rebase if the head has changed.

---

## New Node Type Checklist

Adding a new canvas node type requires touching ALL 6 of these files:

1. **Backend schema transform** — `backend/app/services/schema_engine.py` — register `input_schema → output_schema` function
2. **Backend compiler** — `backend/app/services/workflow_compiler.py` — add SQLGlot compilation rule
3. **Frontend schema transform** — `frontend/src/shared/schema/propagation.ts` — mirror the Python transform
4. **Node component** — `frontend/src/features/canvas/nodes/<NodeType>Node.tsx` — React Flow custom node
5. **Config panel** — `frontend/src/features/canvas/panels/<NodeType>Panel.tsx` — schema-aware configuration UI
6. **Type definitions** — update shared types in both `backend/app/schemas/` and `frontend/src/shared/schema/types.ts`

If any of these 6 are missing, the node type is incomplete.

---

## Query Router Rules

The query router (`backend/app/services/query_router.py`) is the ONLY component that knows about backing stores.

| Query intent | Target | Latency target |
|---|---|---|
| Live data (positions, P&L) | Materialize | < 10ms |
| Point lookup (latest quote) | Redis | < 1ms |
| Ad-hoc analytical query | ClickHouse | < 500ms |
| Historical time-range query | ClickHouse rollups | < 500ms |
| App metadata / catalog | PostgreSQL | < 50ms |

Canvas nodes express intent (e.g., "I need the positions table with realtime freshness"), NOT destination. The router dispatches.

---

## Error Handling Patterns

- **Backend**: Raise `HTTPException` with appropriate status codes (400 validation, 404 not found, 409 conflict, 500 internal). Never return 200 with an error payload.
- **Frontend**: React Query `onError` callbacks display toast notifications. Never silently swallow errors.
- **Orphaned widgets**: When a source workflow is deleted, widgets show an explicit error state — never silently disappear.
- **WebSocket**: Auto-reconnect with exponential backoff. Surface connection status to the user.

---

## Multi-Tenancy

FlowForge is **multi-tenant from day one**. Every tenant-scoped resource is isolated by a `tenant_id` UUID column. Tenant identity is derived from Keycloak JWT claims — never from client-supplied headers or URL parameters.

### Core Rules

1. **Tenant ID comes from the JWT.** The backend extracts `tenant_id` from a custom Keycloak claim (`tenant_id` or group mapping). The `get_current_tenant_id()` dependency in `api/deps.py` is the single source of truth. Never accept tenant ID from request bodies, query params, or custom headers.

2. **Every query filters by tenant.** All `SELECT`, `UPDATE`, and `DELETE` queries on tenant-scoped tables (`users`, `workflows`, `dashboards`, `api_keys`) MUST include a `WHERE tenant_id = :tenant_id` clause. A missing tenant filter is a **data leak bug**. Use the `TenantMixin` on all scoped models.

3. **Tenant-scoped models.** These models carry a `tenant_id` column: `User`, `Workflow`, `Dashboard`, `APIKey`. Child models (`Widget`, `DashboardFilter`) inherit tenant scope from their parent `Dashboard` — no separate `tenant_id` column, but cross-tenant references are prevented by the parent's tenant check.

4. **Cross-tenant references are forbidden.** When creating a `Widget`, the route MUST verify that both the target `Dashboard` and the source `Workflow` belong to the same tenant. A widget must never point to a workflow owned by a different tenant.

5. **Cache keys include tenant.** The preview cache key (`preview_service.py`) MUST include `tenant_id` in its hash. Without it, tenant A could see tenant B's cached preview results.

6. **Compiled SQL includes tenant isolation.** Serving-layer tables contain shared market data (no `tenant_id` column). Tenant isolation is enforced via **symbol-based access control**: the workflow compiler injects `WHERE symbol IN (:allowed_symbols)` using the tenant's symbol ACL from the schema registry. This is enforced at the compiler level, not at the route level. PostgreSQL app metadata uses standard `tenant_id` column filtering.

7. **WebSocket channels are tenant-scoped.** Redis pub/sub channel names MUST include `tenant_id` so execution status updates and live data pushes never leak across tenants.

8. **API keys are tenant-scoped.** The `api_keys` table includes `tenant_id`. An API key can only access widgets belonging to dashboards in the same tenant.

9. **Schema catalog is tenant-scoped.** Different tenants may have access to different serving-layer tables. The schema registry caches catalogs per tenant.

10. **PostgreSQL RLS is defense-in-depth.** Row-level security policies on tenant-scoped tables provide a database-level safety net. Application-level filtering is the primary mechanism; RLS is the backstop.

### Tenant Dependency Pattern

```python
# In api/deps.py — the canonical way to get tenant context
async def get_current_tenant_id(request: Request) -> UUID:
    claims = await get_current_user_claims(request)
    tenant_id = claims.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=403, detail="No tenant claim in token")
    return UUID(tenant_id)

# In route handlers — always inject tenant_id
@router.get("")
async def list_workflows(
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    q = select(Workflow).where(Workflow.tenant_id == tenant_id)
    ...
```

---

## Security

- **Canvas / Dashboards**: Keycloak SSO (OIDC token validation) — supports multiple identity providers
- **Embed**: API key authentication (`sk_live_...`), validated server-side, scoped to specific widgets and tenant-bound
- **SQL injection prevention**: All queries built via SQLGlot with parameterized values. Never concatenate user input into SQL strings.
- **No secrets in client bundles**: API keys, database credentials, and session secrets stay server-side.
- **Tenant isolation**: All data access is scoped by `tenant_id` from JWT claims. Missing tenant filters are security bugs. PostgreSQL RLS provides defense-in-depth.

---

## Explicit "Do NOT" List

- **No pipeline dependencies**: Do not import, reference, or depend on Redpanda, Kafka, dbt, Airflow, or Bytewax. This app reads from the serving layer only.
- **No DataFrame execution**: Do not use Pandas or Polars for query execution. SQL via SQLGlot only.
- **No `reactflow` imports**: The package is `@xyflow/react`. Importing from `reactflow` will break.
- **No query results in PostgreSQL**: PostgreSQL stores app metadata (workflows, dashboards, widgets). Query results go to the client, not to PostgreSQL.
- **No CSS-in-JS or CSS modules**: Tailwind only.
- **No `os.getenv()`**: Use `pydantic-settings` `Settings`.

---

## Serving Layer Table Catalog

The application reads from these tables/views — it does NOT create or write to them. The data pipeline populates them independently.

| Table | Store | Freshness | Content |
|-------|-------|-----------|---------|
| `flowforge.raw_trades` | ClickHouse | Warm (seconds) | Raw trade events |
| `flowforge.raw_quotes` | ClickHouse | Warm (seconds) | Raw quote events |
| `metrics.vwap_5min` | ClickHouse | Warm (seconds) | 5-min VWAP windows (Bytewax) |
| `metrics.rolling_volatility` | ClickHouse | Warm (seconds) | Rolling volatility (Bytewax) |
| `metrics.hourly_rollup` | ClickHouse | Cool (minutes) | OHLCV per symbol per hour (MV) |
| `metrics.daily_rollup` | ClickHouse | Cool (minutes) | OHLCV per symbol per day (MV) |
| `marts.fct_trades` | ClickHouse | Cold (hours) | Enriched trade facts (dbt) |
| `marts.dim_instruments` | ClickHouse | Cold (hours) | Instrument reference data (dbt) |
| `marts.rpt_daily_pnl` | ClickHouse | Cold (hours) | Daily P&L report (dbt) |
| `live_positions` | Materialize | Hot (< 100ms) | Real-time net position per symbol |
| `live_quotes` | Materialize | Hot (< 100ms) | Latest bid/ask per symbol |
| `live_pnl` | Materialize | Hot (< 100ms) | Unrealized P&L per symbol |
| `latest:vwap:*` | Redis | Warm (seconds) | Point lookup for latest VWAP |
| `latest:position:*` | Redis | Warm (seconds) | Point lookup for latest position |

---

## Infrastructure & Development

### Local Development Stack

Development uses **k3d** (k3s-in-Docker on WSL2) orchestrated by **Tilt** for live-reload. All services run in the `flowforge` K8s namespace.

**K8s DNS naming**: All inter-service communication uses `<service>.flowforge.svc.cluster.local`.

### Core Dev Commands

```
tilt up                          # Start all services (Tilt UI: http://localhost:10350)
tilt down                        # Stop all services
kubectl exec deploy/backend -n flowforge -- pytest       # Run backend tests
kubectl exec deploy/frontend -n flowforge -- npm test    # Run frontend tests
```

### Port Mappings

| Service | Port | Protocol |
|---------|------|----------|
| Backend (FastAPI) | 8000 | HTTP |
| Frontend (Vite) | 5173 | HTTP |
| ClickHouse | 8123 | HTTP |
| Materialize | 6875 | PG wire |
| Redis | 6379 | Redis |
| PostgreSQL | 5432 | PG wire |
| Redpanda (Kafka) | 9092 | Kafka |
| Redpanda Admin | 9644 | HTTP |
| Redpanda Console | 8180 | HTTP |
| Airflow | 8280 | HTTP |

### Dev Mode Authentication

For development without Keycloak, the backend accepts a `X-Dev-Tenant` header to set tenant context directly. Controlled by `APP_ENV=development` — MUST be disabled in production.

---

## Chart Library

All charts use **Apache ECharts** via `echarts-for-react`. Chart types: Bar, Line, Candlestick, Scatter, KPI Card, Pivot Table. All live in `frontend/src/shared/components/charts/`.

---

## Canvas Node Types

### Phase 1 (Core)
- **DataSource** — Select a table from the schema catalog
- **Filter** — Add WHERE conditions (schema passes through unchanged)
- **Select** — Choose columns to keep (schema narrows)
- **Sort** — Add ORDER BY clauses (schema passes through unchanged)
- **TableView** — Terminal node — paginated table output

### Phase 2 (Analytical)
- **GroupBy** — GROUP BY + aggregate functions (schema changes to group keys + aggregated columns)
- **Join** — Two-input JOIN (INNER, LEFT, RIGHT, FULL)
- **Union** — Two-input UNION
- **Formula** — Computed columns via `[column]` bracket-notation expressions
- **Rename** — Rename columns
- **Unique** — DISTINCT
- **Sample** — Random sample (LIMIT with ORDER BY RAND())

### Phase 3 (Visualization)
- Bar Chart, Line Chart, Candlestick, Scatter Plot, KPI Card, Pivot Table

---

## Implementation Phases

| Phase | Focus | Key Deliverable |
|-------|-------|-----------------|
| 0 | Scaffolding | All services start, health checks pass |
| 1 | Core Canvas | 5 nodes (DataSource, Filter, Select, Sort, TableView) + preview + save/load |
| 2 | Analytical Nodes | GroupBy, Join, Union, Formula + query merging optimization |
| 3 | Visualization + Dashboards | Chart nodes + dashboard CRUD + widget pinning + global filters |
| 4 | Live Data + Embed | WebSocket push + Materialize/Redis integration + embed mode |
| 5 | Polish | Templates, undo/redo, RBAC, audit logging, versioning |

---

## Cloud Infrastructure (GCP)

Production infrastructure is managed by **Terraform** targeting Google Cloud Platform. See [`terraform/agents.md`](./terraform/agents.md) for detailed requirements.

Key GCP services:
- **GKE**: Application workloads + self-hosted ClickHouse/Materialize
- **Cloud SQL**: Managed PostgreSQL (replaces the pod-based PostgreSQL from dev)
- **Memorystore**: Managed Redis (replaces the pod-based Redis from dev)
- **Artifact Registry**: Docker images
- **Secret Manager**: All secrets (no secrets in K8s ConfigMaps)
- **Workload Identity**: IAM for pods (no JSON key files)

Environments: `dev`, `staging`, `prod` — each in its own GCP project.

CI/CD via GitHub Actions. See [`.github/workflows/agents.md`](./.github/workflows/agents.md).
