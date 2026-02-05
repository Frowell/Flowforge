# FlowForge — Application Plan

> This document is a living reference for the FlowForge application.
> It describes what has been built, the architecture, known gaps, and remaining work.
> For agent coding rules see [`CLAUDE.md`](./CLAUDE.md). For product scope see [`planning.md`](./planning.md).

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Implementation Status](#2-implementation-status)
3. [Architecture Reference](#3-architecture-reference)
4. [Known Discrepancies](#4-known-discrepancies)
5. [Remaining Work](#5-remaining-work)
6. [Testing Strategy](#6-testing-strategy)
7. [Key Technical Decisions](#7-key-technical-decisions)
8. [Success Criteria](#8-success-criteria)

---

## 1. Project Overview

FlowForge is a visual analytics platform for fintech trading markets. It combines an Alteryx-style no-code canvas with embedded BI capabilities. Users build data transformation workflows by dragging nodes on a canvas, then pin outputs to dashboards or embed them in external applications.

### What FlowForge IS

- A **canvas** where non-technical users build data workflows visually (filter, sort, join, aggregate, chart)
- A **dashboard system** where pinned canvas outputs render as widgets with auto-refresh
- An **embed layer** where individual widgets render in headless iframes for external applications
- A **query compiler** that translates visual workflows into SQL targeting ClickHouse, Materialize, or Redis

### What FlowForge is NOT

- FlowForge does NOT own data ingestion, transformation pipelines, or orchestration
- The data pipeline (Redpanda → Bytewax → ClickHouse, Materialize, dbt, Airflow) is a separate workstream
- FlowForge reads from the serving layer — it never writes to it (except app metadata in PostgreSQL)

### Single Application, Three Modes

| Mode | URL | Auth | Purpose |
|------|-----|------|---------|
| Canvas | `/canvas` | OIDC (Keycloak) | Author mode — React Flow workspace for building workflows |
| Dashboards | `/dashboards` | OIDC (Keycloak) | Viewer mode — widget grid from pinned canvas outputs |
| Embed | `/embed/:widget_id` | API key (stateless) | Headless mode — chromeless iframe |

### Technology Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 19 + strict TypeScript |
| Canvas | `@xyflow/react` v12 (NOT `reactflow`) |
| State (UI) | Zustand 5 + zundo (undo/redo) |
| State (server) | TanStack Query v5 |
| Routing | react-router-dom v7 |
| Styling | Tailwind CSS 3.4 |
| Charts | Recharts 2.13 in `shared/components/charts/` |
| Dashboard layout | react-grid-layout 1.5 |
| Auth (frontend) | keycloak-js 26 |
| Build | Vite 6 |
| Backend | Python 3.12+, async FastAPI, Uvicorn |
| ORM | SQLAlchemy 2.0 async (`DeclarativeBase`, `Mapped`, `mapped_column`) |
| App DB | PostgreSQL 16 (metadata only) |
| Migrations | Alembic (async) |
| SQL generation | SQLGlot (never string concatenation) |
| Validation | Pydantic v2 |
| Auth (backend) | Keycloak OIDC + API key + dev bypass |
| ClickHouse client | clickhouse-connect |
| Materialize client | asyncpg |
| Redis client | redis-py (async) |
| WebSocket | FastAPI WebSocket + Redis pub/sub |

---

## 2. Implementation Status

### 2.1 Backend

**Models** (8 classes across 4 files in `backend/app/models/`):

| File | Classes |
|------|---------|
| `user.py` | `User`, `UserRole` (enum: admin, analyst, viewer) |
| `workflow.py` | `Workflow`, `WorkflowVersion` |
| `dashboard.py` | `Dashboard`, `Widget`, `DashboardFilter`, `APIKey` |
| `audit_log.py` | `AuditLog`, `AuditAction`, `AuditResourceType` |

All models use `TenantMixin` for multi-tenancy (`tenant_id` on `User`, `Workflow`, `Dashboard`, `APIKey`, `AuditLog`). Child models (`Widget`, `DashboardFilter`) inherit tenant scope from parent `Dashboard`.

**Routes** (13 files in `backend/app/api/routes/`):

| Route | Endpoints |
|-------|-----------|
| `health.py` | `/health`, `/health/live`, `/health/ready` |
| `workflows.py` | Workflow CRUD (list, get, create, update, delete) |
| `dashboards.py` | Dashboard CRUD |
| `widgets.py` | Widget CRUD + pin/unpin from canvas |
| `executions.py` | Execute workflow subgraph, get execution status |
| `schema.py` | Schema catalog (tables/columns from serving layer) |
| `metrics.py` | Prometheus metrics endpoint (`/metrics`) |
| `audit.py` | Audit log query |
| `api_keys.py` | API key creation/revocation for embed mode |
| `embed.py` | Embed widget data fetch (API key auth) |
| `templates.py` | Workflow template CRUD |
| `ws.py` | WebSocket for execution status + live data |

**Services** (11 files in `backend/app/services/`):

| Service | Responsibility |
|---------|---------------|
| `schema_registry.py` | Reads table/column metadata from ClickHouse + Materialize, Redis cache |
| `schema_engine.py` | Server-side DAG schema validation, node type transforms |
| `workflow_compiler.py` | DAG → SQLGlot AST → merged SQL queries, tenant filter injection |
| `query_router.py` | Dispatches queries to ClickHouse/Materialize/Redis by freshness |
| `formula_parser.py` | Bracket-notation formula parsing → SQL AST |
| `preview_service.py` | Content-addressed Redis cache for canvas preview |
| `websocket_manager.py` | WebSocket connection tracking, Redis pub/sub |
| `widget_data_service.py` | Widget query execution for dashboards + embed |
| `audit_service.py` | Audit log creation |
| `rate_limiter.py` | Redis fixed-window rate limiting (embed endpoints) |
| `template_registry.py` | Workflow template management |

**Auth** (`backend/app/core/auth.py`):
- Keycloak OIDC: JWT validation against JWKS (RS256), auto key rotation
- API key: SHA256 hashed, scoped to widgets/dashboards, tenant-scoped
- Dev bypass: `APP_ENV=development` skips Keycloak for local dev
- Role enforcement: `require_role()` dependency

**Alembic migrations**: 2 migration files in `backend/alembic/versions/`:
1. `92284ff9b280_initial_schema.py` — Users, workflows, dashboards, widgets, API keys, dashboard filters
2. `add_audit_logs_table.py` — Audit log table + indexes

**Tests**: 25 test files, ~65 test functions across `backend/tests/`:
- `api/` — 9 test files (workflows, dashboards, widgets, embed auth, WebSocket, templates, API keys, health, RBAC)
- `services/` — 10 test files (schema engine, workflow compiler, query router, preview, formula parser, audit, tenant isolation, versioning)
- All async, using `httpx.AsyncClient` for API integration

### 2.2 Frontend

**Canvas nodes** (18 components + BaseNode in `frontend/src/features/canvas/nodes/`):

| Phase 1 (Core) | Phase 2 (Analytical) | Phase 3 (Visualization) |
|----------------|---------------------|------------------------|
| DataSourceNode | GroupByNode | ChartOutputNode |
| FilterNode | JoinNode | TableOutputNode |
| SelectNode | UnionNode | KPIOutputNode |
| SortNode | FormulaNode | |
| | RenameNode | |
| | UniqueNode | |
| | SampleNode | |
| | LimitNode | |
| | PivotNode | |
| | WindowNode | |

**Config panels** (16 files in `frontend/src/features/canvas/panels/`):
DataSourcePanel, FilterPanel, SelectPanel, SortPanel, RenamePanel, UniquePanel, SamplePanel, LimitPanel, GroupByPanel, JoinPanel, UnionPanel, FormulaPanel, PivotPanel, WindowPanel, ChartConfigPanel, KPIPanel

**Canvas components**: Canvas.tsx, ConfigPanel.tsx, NodePalette.tsx, DataPreview.tsx, ExecutionStatus.tsx, TemplatePicker.tsx, WorkflowPicker.tsx

**Canvas hooks**: useWorkflow, useSchemaEngine, useDataPreview, useExecution, useKeyboardShortcuts, useWorkflowVersions, useTemplates

**Canvas store**: Zustand workflowStore with zundo undo/redo

**Schema propagation** (`frontend/src/shared/schema/propagation.ts`):
- 17 node type transforms: `data_source`, `filter`, `select`, `rename`, `sort`, `join`, `union`, `group_by`, `pivot`, `formula`, `unique`, `sample`, `limit`, `window`, `chart_output`, `table_output`, `kpi_output`
- Synchronous topological sort (Kahn's algorithm)
- Runs on every connection change for instant feedback

**Charts** (7 files in `frontend/src/shared/components/charts/`):
BarChart, LineChart, CandlestickChart, ScatterPlot, KPICard, PivotTable, ChartRenderer (dispatch component)
- Library: **Recharts** 2.13 (not ECharts)
- Same components used in canvas preview, dashboard widgets, and embed

**Dashboard** (`frontend/src/features/dashboards/`):
- Components: DashboardGrid, WidgetCard, GlobalFilters, DashboardPicker, PinToDialog
- Hooks: useDashboard, useWidgetData, useWidget, useDashboardWidgets, useGlobalFilters
- Store: dashboardStore (Zustand)

**Embed** (`frontend/src/features/embed/`):
- EmbedRoot (minimal shell, API key auth), EmbedWidget (single widget renderer)

**Shared utilities**:
- `shared/auth/keycloak.ts` — Keycloak OIDC adapter
- `shared/websocket/manager.ts` — WebSocket connection management
- `shared/query-engine/client.ts` + `types.ts` — API client
- `shared/schema/registry.ts` + `types.ts` — Schema registry client
- `shared/components/DataGrid.tsx`, `Navbar.tsx`, `ConnectionStatus.tsx`, `FormulaEditor.tsx`

**Tests**: 2 test files, ~54 test cases:
- `features/canvas/__tests__/workflowStore.test.ts` — Zustand store operations
- `shared/schema/__tests__/propagation.test.ts` — Schema propagation for all 17 node types

### 2.3 Infrastructure

**Devcontainer** (`.devcontainer/`):
- PostgreSQL, Redis, ClickHouse, Materialize, Redpanda
- Init scripts: `init-db.sql`, `init-materialize.sh`
- Post-create/post-start lifecycle hooks

**Kubernetes** (`k8s/`):
- `base/` — kustomization.yaml, namespace.yaml
- `overlays/dev/` — kustomization.yaml, resource-limits.yaml
- Minimal manifests — production deployment managed by Terraform + GKE

**Terraform** (`terraform/` — 40 files, ~2,080 lines):

| Module | Resources |
|--------|-----------|
| `networking` | VPC, subnets, NAT, Private Service Access |
| `gke` | GKE cluster, node pools, Workload Identity |
| `cloudsql` | Cloud SQL PostgreSQL, private IP, backups |
| `memorystore` | Redis, private IP |
| `registry` | Artifact Registry for Docker images |
| `secrets` | Secret Manager for credentials |
| `iam` | Service accounts, Workload Identity bindings |
| `dns` | Cloud DNS for public endpoints |

Environments: `dev`, `staging`, `prod` (each in separate GCP project, GCS backend for state).

**CI/CD** (`.github/workflows/` — 7 workflows):

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `ci.yml` | Push to all branches | Lint, type-check, test (backend + frontend) |
| `build.yml` | Push to main | Build Docker images → Artifact Registry |
| `deploy-dev.yml` | Manual / auto (main) | Deploy to GKE dev |
| `deploy-staging.yml` | Manual | Deploy to GKE staging |
| `deploy-prod.yml` | Manual | Deploy to GKE prod |
| `terraform-plan.yml` | PR with TF changes | Terraform plan preview |
| `terraform-apply.yml` | Push to main (TF) | Apply Terraform changes |

### 2.4 Pipeline (Separate Workstream)

The pipeline exists in `pipeline/` for co-development but is architecturally independent:

| Component | Files | Status |
|-----------|-------|--------|
| Generator | `generator/generator.py`, Dockerfile, requirements.txt | Built |
| Bytewax VWAP | `bytewax/flows/vwap.py`, Dockerfile, requirements.txt | Built |
| Bytewax volatility | `bytewax/flows/volatility.py` | **Missing** |
| Bytewax anomaly | `bytewax/flows/anomaly.py` | **Missing** |
| dbt models | staging (2), intermediate (1), marts (3), seeds (1) | Partial — missing `int_clearing_matched.sql`, `counterparties.csv`, tests |
| Materialize SQL | `000_sources.sql`, `001_staging.sql`, `002_views.sql` | **Missing** |
| Airflow | `dags/dbt_cold_path.py` | Built |

### 2.5 What's Verified

- Backend: `ruff check` clean, `pytest` passing (65 tests), all API endpoints tested
- Frontend: `tsc --noEmit` clean, `vitest` passing (54 tests), all 17 schema transforms tested
- CI: GitHub Actions green on push
- Multi-tenancy: Tenant isolation verified in dedicated test suite
- Auth: Keycloak OIDC + API key + dev bypass all tested

---

## 3. Architecture Reference

### 3.1 Integration Contract

The pipeline provides data to the serving layer. FlowForge reads from it. The contract:

```
Serving Layer         Technology      What it provides to FlowForge
─────────────         ──────────      ─────────────────────────────
Analytical store      ClickHouse      Mart tables, rollup tables, materialized views
Live streaming        Materialize     Real-time materialized views (positions, P&L, quotes)
Point lookups         Redis           Latest state (current price, position size)
App metadata          PostgreSQL      Workflows, dashboards, users, API keys, audit logs
Schema catalog        CH system.*     Column names, types, table sizes (queryable)
```

See [`docs/serving-layer.md`](./docs/serving-layer.md) for the full table catalog and query router dispatch rules.

### 3.2 Schema Engine Contract

Every node type declares how it transforms schemas. Both TypeScript (client-side, instant feedback) and Python (server-side, authoritative) implement identical transforms.

```
Node Type       Input Schema → Output Schema
─────────       ──────────────────────────────────────────
Data Source     (none) → table schema from catalog
Filter          passthrough (same columns, fewer rows)
Select          subset of input columns
Rename          input columns with name substitutions
Sort            passthrough (same columns, reordered rows)
Limit           passthrough (fewer rows)
Sample          passthrough (fewer rows)
Unique          passthrough (deduplicated rows)
Group By        group keys + aggregate output columns
Join            merged schemas from both inputs
Union           aligned schemas from both inputs
Pivot           group keys + pivoted value columns
Formula         input columns + new calculated column
Window          input columns + new window function column
Chart Output    (terminal, no output schema)
Table Output    (terminal, no output schema)
KPI Output      (terminal, no output schema)
```

See [`docs/node-type-guide.md`](./docs/node-type-guide.md) for the node type checklist and query merging rules.

### 3.3 Query Router Dispatch

```
Query Type                    Target              Latency Target
──────────────────────────    ─────────────────   ──────────────
Live data (positions, P&L)    Materialize         < 10ms
Point lookup (latest quote)   Redis               < 1ms
Ad-hoc analytical query       ClickHouse          < 500ms
Historical time-range query   ClickHouse rollups   < 500ms
Metadata / catalog            PostgreSQL          < 50ms
```

The query router (`backend/app/services/query_router.py`) is the ONLY component that knows about backing stores. Canvas nodes express intent, not destination.

### 3.4 Workflow Compilation

The backend compiles canvas DAGs into executable queries in 5 steps:

1. **Topological sort** the node graph to determine execution order
2. **Schema validate** every connection in the DAG
3. **Merge adjacent nodes** into single queries where possible (Filter → Select → Sort = one `SELECT ... WHERE ... ORDER BY`)
4. **Determine target** for each query segment based on source table freshness
5. **Execute** compiled queries, returning results via REST or streaming via WebSocket

**Query merging example:**

```
Canvas:  [Data Source: trades] → [Filter: symbol = 'AAPL'] → [Sort: time DESC] → [Table View]

Naive:   3 queries
Merged:  SELECT * FROM fct_trades WHERE symbol = 'AAPL' ORDER BY event_time DESC LIMIT 1000

Canvas:  [Source A: trades] → [Join on symbol] ← [Source B: instruments]
                                     ↓
                              [Group By: sector, SUM(notional)]
                                     ↓
                              [Bar Chart]

Merged:  SELECT i.sector, SUM(t.quantity * t.price) as notional
         FROM fct_trades t
         JOIN dim_instruments i ON t.symbol = i.symbol
         GROUP BY i.sector
```

### 3.5 Preview System

Three-layer execution model for canvas data previews:

1. **Client-side schema**: Instant feedback — TypeScript propagation shows output columns/types without querying
2. **Cached preview**: Content-addressed Redis cache keyed on `tenant_id:node_config_hash` — returns previous results if config hasn't changed
3. **Live execution**: On cache miss, compiles node subgraph to SQL, executes against serving layer, caches result, returns first 100 rows

### 3.6 Dashboard Live Update Flow

Designed but not fully wired end-to-end:

```
Materialize change stream → Redis pub/sub → WebSocket Manager → Connected dashboard clients
```

- WebSocket infrastructure exists (`ws.py` route, `websocket_manager.py` service)
- Redis pub/sub channels are tenant-scoped
- Frontend WebSocket hook exists (`shared/websocket/manager.ts`)
- **Not wired**: Materialize change subscription → Redis publish loop

### 3.7 Formula Builder

Expression language for calculated columns:

```
expression  = term (('+' | '-') term)*
term        = factor (('*' | '/') factor)*
factor      = NUMBER | STRING | COLUMN_REF | function_call | '(' expression ')'
COLUMN_REF  = '[' column_name ']'
function    = FUNC_NAME '(' expression (',' expression)* ')'

Functions: ABS, ROUND, CEIL, FLOOR, UPPER, LOWER, TRIM, LEFT, RIGHT, LENGTH,
           IF, CASE, COALESCE, SUM, AVG, COUNT, MIN, MAX, LAG, LEAD, ROW_NUMBER, RANK
```

Expressions parse to AST client-side (syntax validation) and compile to ClickHouse/Materialize SQL server-side via `formula_parser.py`.

### 3.8 Dashboard Data Model

```
workflow        → id, name, graph_json, tenant_id, created_by, timestamps
workflow_version → id, workflow_id, version_number, graph_json, timestamps
dashboard       → id, name, description, tenant_id, created_by, timestamps
widget          → id, dashboard_id, source_workflow_id, source_node_id, layout (x,y,w,h), config_overrides
dashboard_filter → id, dashboard_id, filter_type, target_column, config, position
api_key         → id, tenant_id, key_hash, scoped_widget_ids, created_by, timestamps
audit_log       → id, tenant_id, user_id, action, resource_type, resource_id, details, timestamps
```

A widget is a pointer to a canvas output node. Changing the workflow changes the widget. Deleting the workflow orphans the widget (shows error state).

---

## 4. Known Discrepancies

### 4.1 Chart Library — RESOLVED

All documentation has been updated to reference **Recharts** (the library actually used in the codebase). Previously, docs referenced Apache ECharts via `echarts-for-react` which was never installed.

### 4.2 Missing `infra/` Directory

The original plan references an `infra/` directory for ClickHouse init SQL, PostgreSQL init SQL, and Redpanda console config. This directory does not exist. Init scripts live in `.devcontainer/` instead:
- `.devcontainer/init-db.sql` (PostgreSQL)
- `.devcontainer/init-materialize.sh` (Materialize)
- ClickHouse init is handled by the devcontainer docker-compose

### 4.3 Missing Pipeline Files

The original plan specified files that don't exist:
- `pipeline/bytewax/flows/volatility.py` — not created
- `pipeline/bytewax/flows/anomaly.py` — not created
- `pipeline/materialize/` directory — not created (Materialize SQL scripts)
- `pipeline/dbt/models/intermediate/int_clearing_matched.sql` — not created
- `pipeline/dbt/seeds/counterparties.csv` — not created
- `pipeline/dbt/tests/` — not created

These are pipeline workstream items, not application items.

### 4.4 K8s Manifest Coverage

The original plan specified full manifests for all infrastructure (Redpanda, ClickHouse, Materialize, Redis, PostgreSQL), pipeline (Bytewax, Airflow, data generator), and application (backend, frontend). Only namespace + dev overlay exist. Production deployment is handled by Terraform + GKE, so the full K8s manifests may not be needed.

### 4.5 Repo Structure Differences

The original plan specified a tree with `AGENTS.md` files and symlinks to `CLAUDE.md`. The actual codebase has `CLAUDE.md` files directly (not symlinks from `AGENTS.md`). Some planned directories (e.g., `docs/PLANNING.md`, `docs/ARCHITECTURE.md`, `docs/DECISIONS.md`) were replaced by `planning.md` at root and focused guides in `docs/`.

---

## 5. Remaining Work

### Tier 1: Documentation Alignment (Low Effort)

- [x] Update `CLAUDE.md` tech stack table: ECharts → Recharts
- [x] Update `docs/node-type-guide.md` chart library section: ECharts → Recharts
- [ ] Remove references to non-existent `infra/` directory from documentation
- [x] Ensure all CLAUDE.md files reference correct package versions

### Tier 2: Testing Gaps (Medium Effort, High Impact)

**Frontend test expansion** (current: 54 tests, target: 150+):
- [ ] Canvas component tests (Canvas.tsx, ConfigPanel.tsx, NodePalette.tsx)
- [ ] Individual node component render tests (18 nodes)
- [ ] Config panel interaction tests (16 panels)
- [ ] Chart component render tests (6 chart types)
- [ ] Dashboard component tests (DashboardGrid, WidgetCard, GlobalFilters)
- [ ] Embed component tests (EmbedRoot, EmbedWidget)
- [ ] Hook tests (useWorkflow, useSchemaEngine, useDataPreview, useExecution)

**Cross-validation fixture**:
- [ ] Create shared JSON test fixtures consumed by both Python and TypeScript schema engines
- [ ] Verify identical output for same inputs across both implementations
- [ ] Location: `tests/fixtures/schema_transforms.json` (shared)

**E2E tests** (Playwright):
- [ ] Set up `e2e/` directory with Playwright config
- [ ] P0 flow: Create workflow → add nodes → connect → preview → save
- [ ] P0 flow: Pin output to dashboard → verify widget appears
- [ ] P0 flow: Embed widget → verify renders with API key
- [ ] P0 flow: Global dashboard filter → verify all widgets update
- [ ] P0 flow: Template → customize → save as new workflow

### Tier 3: Integration Verification (Medium Effort, High Impact)

- [ ] End-to-end test with real ClickHouse (not mocked) — verify compiled SQL executes correctly
- [ ] End-to-end test with real Materialize — verify live query routing
- [ ] Redis point lookup verification — verify query router dispatches correctly
- [ ] WebSocket live data push — wire Materialize change stream → Redis pub/sub → client
- [ ] Preview cache invalidation — verify stale previews are evicted on workflow edit

### Tier 4: Production Readiness (High Effort)

**K8s production overlay**:
- [ ] Backend + frontend Deployment manifests
- [ ] HPA (Horizontal Pod Autoscaler) for backend
- [ ] PDB (Pod Disruption Budget)
- [ ] Ingress with TLS termination
- [ ] ConfigMaps for environment-specific settings

**Auth production config**:
- [ ] Keycloak realm configuration (realm export JSON)
- [ ] Client registration for Canvas + Dashboard modes
- [ ] Role mapping (admin → `require_role("admin")`, analyst, viewer)
- [ ] Multi-tenant realm-per-customer vs single-realm decision

**Database**:
- [ ] Verify Alembic migrations cover all ORM models (currently 2 migrations for 8 model classes)
- [ ] Migration for `WorkflowVersion` if not covered
- [ ] Add migration smoke test to CI (apply + downgrade + re-apply)

### Tier 5: Missing Pipeline Components (Separate Workstream)

- [ ] `pipeline/bytewax/flows/volatility.py` — Rolling volatility calculation
- [ ] `pipeline/bytewax/flows/anomaly.py` — Spread/volume anomaly detection
- [ ] `pipeline/materialize/` — CREATE SOURCE + staging + materialized views SQL
- [ ] `pipeline/dbt/models/intermediate/int_clearing_matched.sql`
- [ ] `pipeline/dbt/seeds/counterparties.csv`
- [ ] `pipeline/dbt/tests/assert_no_orphan_trades.sql`

### Tier 6: Polish Features

- [ ] Dashboard drill-down: click chart element → filtered detail view
- [ ] Auto-refresh configuration per widget (5s, 30s, 1m, 5m, live)
- [ ] Embed responsive sizing: widget fills iframe container
- [ ] RBAC enforcement audit: verify `require_role()` on all sensitive routes
- [ ] Audit log admin panel: queryable audit trail UI
- [ ] Error states: orphaned widgets, failed queries, disconnected WebSocket, stale schema
- [ ] Workflow export/import (JSON)
- [ ] Dashboard URL sharing with embedded filter state

---

## 6. Testing Strategy

### Current Coverage

| Layer | Test Files | Test Cases | Framework |
|-------|-----------|------------|-----------|
| Backend API | 9 | ~30 | pytest + httpx.AsyncClient |
| Backend services | 10 | ~35 | pytest (async) |
| Frontend store | 1 | ~20 | Vitest |
| Frontend schema | 1 | ~34 | Vitest |
| **Total** | **21** | **~119** | |

### Target Coverage

| Layer | Current | Target | Priority |
|-------|---------|--------|----------|
| Backend | 65 tests | 100+ | Medium (already good) |
| Frontend unit | 54 tests | 150+ | **High** |
| E2E (Playwright) | 0 | 5 P0 flows | **High** |
| Cross-validation | 0 | 17 transforms | **High** |

### E2E Test Plan (Playwright)

5 P0 flows that verify the full stack:

1. **Workflow creation**: Navigate to canvas → drag DataSource node → configure table → drag Filter → connect → preview data → save workflow
2. **Pin to dashboard**: Open workflow → select chart output → click "Pin to Dashboard" → verify widget appears on dashboard
3. **Embed widget**: Create API key → navigate to `/embed/:widget_id?api_key=...` → verify chart renders
4. **Dashboard filters**: Open dashboard with 3 widgets → apply date range filter → verify all widgets re-query
5. **Template to dashboard**: Open template picker → select template → customize → save → pin to dashboard

### Cross-Validation Fixture Format

Shared JSON fixtures for Python ↔ TypeScript schema engine parity:

```json
{
  "test_name": "filter_passthrough",
  "node_type": "filter",
  "node_config": { "column": "price", "operator": "gt", "value": 100 },
  "input_schema": [
    { "name": "symbol", "type": "string" },
    { "name": "price", "type": "float" }
  ],
  "expected_output_schema": [
    { "name": "symbol", "type": "string" },
    { "name": "price", "type": "float" }
  ]
}
```

Both engines load these fixtures and verify identical output.

---

## 7. Key Technical Decisions

**Query merging is critical for performance.** A naive implementation sends one query per node. The compiler merges adjacent compatible nodes into single queries. Filter → Select → Sort on the same table = one query, not three round-trips.

**Schema propagation runs client-side first.** The TypeScript schema engine provides instant feedback — dropdowns populate immediately, type errors highlight on connect, not on run. The Python server-side engine is authoritative and validates before execution.

**Charts render with the same component everywhere.** A `<BarChart>` in a canvas preview, a dashboard widget, and an embedded iframe is the same React component with different container styling.

**The workflow compiler targets SQL, not DataFrames.** Canvas workflows compile to ClickHouse SQL or Materialize SQL via SQLGlot. The database does the heavy lifting. Pandas/Polars only for formatting preview results.

**Dashboards are projections of canvas workflows.** A widget points to a workflow output node. No independent dashboard queries. Changing the workflow changes the widget.

---

## 8. Success Criteria

### Phase 0: Foundation — VERIFIED
- [x] Devcontainer starts with all backing stores
- [x] FastAPI health check responds
- [x] React SPA routes render
- [x] CI pipeline runs lint + test on push

### Phase 1: Core Canvas — STRUCTURALLY COMPLETE
- [x] 5 core node types (DataSource, Filter, Select, Sort, TableView) implemented
- [x] Schema propagation engine (TypeScript + Python)
- [x] Workflow save/load
- [x] Workflow compiler with query merging
- [ ] Verified end-to-end with real ClickHouse data

### Phase 2: Analytical Nodes — STRUCTURALLY COMPLETE
- [x] GroupBy, Join, Union, Formula, Rename, Unique, Sample nodes
- [x] Formula parser (bracket-notation → SQL)
- [x] Additional nodes: Limit, Pivot, Window
- [ ] Verified multi-source DAG compilation (joins, subqueries)

### Phase 3: Visualization + Dashboards — STRUCTURALLY COMPLETE
- [x] 6 chart types (Bar, Line, Candlestick, Scatter, KPI, Pivot)
- [x] Dashboard grid layout with widget cards
- [x] Pin-to-dashboard dialog
- [x] Global dashboard filters
- [ ] Dashboard drill-down
- [ ] Dashboard URL sharing

### Phase 4: Live Data + Embed — PARTIALLY COMPLETE
- [x] WebSocket infrastructure (route + manager + frontend hook)
- [x] Embed mode (EmbedRoot + EmbedWidget + API key auth)
- [x] API key management (create/revoke)
- [ ] Live data push (Materialize → Redis pub/sub → WebSocket → client)
- [ ] Auto-refresh configuration per widget
- [ ] Embed responsive sizing

### Phase 5: Polish — PARTIALLY COMPLETE
- [x] Template workflows + template picker
- [x] Workflow versioning
- [x] Undo/redo (zundo)
- [x] Keyboard shortcuts
- [x] Audit logging (model + service + route)
- [x] Role-based access (UserRole enum + require_role)
- [ ] RBAC enforcement audit across all routes
- [ ] Audit log admin panel UI
- [ ] Error states (orphaned widgets, failed queries, stale schema)
