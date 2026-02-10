# FlowForge — Agent Rules

> Decisions: [`docs/decisions/`](./docs/decisions/) | RFCs: [`docs/rfcs/`](./docs/rfcs/) | Archive: [`docs/archive/`](./docs/archive/)
> Every agent in this repo MUST follow these rules without exception.

## Project Identity

FlowForge is a visual analytics platform for **fintech trading markets** — an Alteryx-style no-code canvas + embedded BI. Users build data transformation workflows by dragging nodes, then pin outputs to dashboards or embed them externally.

Compiles workflows to SQL against a **read-only** serving layer (ClickHouse, Materialize, Redis). Three modes — Canvas (author), Dashboards (viewer), Embed (headless) — one FastAPI backend.

| Mode | URL | Auth | Purpose |
|------|-----|------|---------|
| Canvas | `/canvas` | OIDC (Keycloak) | React Flow workspace for building workflows |
| Dashboards | `/dashboards` | OIDC (Keycloak) | Widget grid from pinned canvas outputs |
| Embed | `/embed/:widget_id` | API key (stateless) | Chromeless iframe |

---

## 6 Absolute Architectural Rules

1. **App does NOT own data ingestion.** The serving layer is read-only. Never write DDL, INSERT, or CREATE VIEW against ClickHouse/Materialize/Redis.
2. **Workflows compile to SQL via SQLGlot, NOT DataFrames.** Pandas/Polars only for formatting preview results or test fixtures.
3. **Schema propagation is the core.** Every node type declares input → output schema transform in BOTH TypeScript and Python, kept in sync.
4. **Query merging is mandatory.** Adjacent compatible nodes merge into single SQL queries. Filter → Select → Sort = ONE query.
5. **Charts use the same component everywhere.** Canvas preview, dashboard widget, and embed iframe all import from `shared/components/charts/`.
6. **Dashboards are projections of workflows.** Widgets point to workflow output nodes. No independent dashboard queries.

---

## Tech Stack Constraints

| Layer | Stack |
|---|---|
| Backend | Python 3.12+, async FastAPI, Uvicorn |
| ORM | SQLAlchemy 2.0 async (`DeclarativeBase`, `Mapped`, `mapped_column`) |
| App DB | PostgreSQL 16 (metadata only) |
| Migrations | Alembic (async) |
| SQL generation | SQLGlot (never string concatenation) |
| Frontend | React 19, strict TypeScript |
| Client state | Zustand (UI only) |
| Server state | TanStack Query |
| Styling | Tailwind CSS only |
| Canvas | `@xyflow/react` v12+ (NOT `reactflow`) |
| Charts | Recharts in `shared/components/charts/` |
| Dashboard layout | `react-grid-layout` |

---

## Code Conventions

- **Python**: Ruff for lint + format
- **TypeScript**: ESLint + Prettier
- **Migrations**: Alembic only — never hand-edit DDL
- **Import alias**: `@/` → `frontend/src/`
- **API prefix**: `/api/v1/`
- **Config**: `pydantic-settings` `Settings` — never `os.getenv()`

---

## Explicit "Do NOT" List

- **No pipeline dependencies**: No imports of Redpanda, Kafka, dbt, Airflow, or Bytewax
- **No DataFrame execution**: SQL via SQLGlot only
- **No `reactflow` imports**: The package is `@xyflow/react`
- **No query results in PostgreSQL**: PostgreSQL = app metadata only
- **No CSS-in-JS or CSS modules**: Tailwind only
- **No `os.getenv()`**: Use `pydantic-settings`

---

## Focused Guides

| Topic | Document |
|-------|----------|
| Architecture decisions (ADRs) — why key choices were made | [`docs/decisions/`](./docs/decisions/) |
| Proposals for significant changes (RFCs) | [`docs/rfcs/`](./docs/rfcs/) |
| Node types, checklist, schema propagation, query merging | [`docs/node-type-guide.md`](./docs/node-type-guide.md) |
| Multi-tenancy rules, code patterns, tenant isolation | [`docs/multi-tenancy.md`](./docs/multi-tenancy.md) |
| Serving layer tables, query router, SQL dialects | [`docs/serving-layer.md`](./docs/serving-layer.md) |
| Backend structure, models, services, auth | [`backend/CLAUDE.md`](./backend/CLAUDE.md) |
| API routes, endpoint catalog, auth patterns | [`backend/app/api/CLAUDE.md`](./backend/app/api/CLAUDE.md) |
| Terraform infrastructure (GCP) | [`terraform/agents.md`](./terraform/agents.md) |
| CI/CD workflows (GitHub Actions) | [`.github/workflows/agents.md`](./.github/workflows/agents.md) |

---

## Error Handling

- **Backend**: `HTTPException` with correct status codes (400, 404, 409, 500). Never 200 + error payload.
- **Frontend**: React Query `onError` → toast notifications. Never swallow errors.
- **Orphaned widgets**: Explicit error state when source workflow is deleted.
- **WebSocket**: Auto-reconnect with exponential backoff.

---

## Security

- **Canvas / Dashboards**: Keycloak SSO (OIDC). **Embed**: API key (`sk_live_...`).
- **SQL injection prevention**: SQLGlot with parameterized values. Never concatenate.
- **Tenant isolation**: All data scoped by `tenant_id` from JWT. Missing filters = security bug. See [`docs/multi-tenancy.md`](./docs/multi-tenancy.md).
- **No secrets in client bundles**.

---

## Git Strategy

Trunk-based development. `main` is always deployable. **Never commit directly to `main`.**

**Branch naming**: `<type>/<short-desc>` — `feat/`, `fix/`, `refactor/`, `docs/`, `chore/`, `infra/`

**Commits**: [Conventional Commits](https://www.conventionalcommits.org/) — `feat(scope): description`

**Rules**: Branch from main, one concern per branch, rebase before merge, squash-merge, delete after merge.

**Alembic migrations**: Never branch from a branch with an uncommitted migration. Parallel migration branches cause head conflicts.

---

## Implementation Phases

| Phase | Focus | Key Deliverable |
|-------|-------|-----------------|
| 0 | Scaffolding | Services start, health checks pass |
| 1 | Core Canvas | 5 nodes + preview + save/load |
| 2 | Analytical Nodes | GroupBy, Join, Union, Formula + query merging |
| 3 | Visualization + Dashboards | Charts + dashboard CRUD + widget pinning |
| 4 | Live Data + Embed | WebSocket + Materialize/Redis + embed mode |
| 5 | Polish | Templates, undo/redo, RBAC, audit logging |

---

## Cloud Infrastructure (GCP)

Production on GCP managed by Terraform. See [`terraform/agents.md`](./terraform/agents.md).

Key services: GKE, Cloud SQL (PostgreSQL), Memorystore (Redis), Artifact Registry, Secret Manager, Workload Identity.

Environments: `dev`, `staging`, `prod` — each in its own GCP project. CI/CD via GitHub Actions — see [`.github/workflows/agents.md`](./.github/workflows/agents.md).

---

## Agent Dispatch Patterns

### Adding a New Node Type (Parallel)

Node types require changes in both backend and frontend. These can be developed in parallel:

**Backend Agent** (scope: `backend/`):
1. Schema transform in `app/services/schema_engine.py`
2. Compiler rule in `app/services/workflow_compiler.py`
3. Pydantic schemas in `app/schemas/`
4. Tests in `tests/`

**Frontend Agent** (scope: `frontend/src/`):
1. Schema transform in `shared/schema/propagation.ts`
2. Node component in `features/canvas/nodes/<Type>Node.tsx`
3. Config panel in `features/canvas/panels/<Type>Panel.tsx`
4. Shared types in `shared/schema/types.ts`

**Synthesis** (after both complete):
- Verify TypeScript and Python schema transforms produce identical output for the same inputs
- Run full test suite (`pytest` + `vitest`)
- Verify no import errors across the boundary

### Cross-Cutting Changes (Serial)

These must be done sequentially — do NOT parallelize:
- Database migrations (Alembic head conflicts)
- Changes to shared type definitions that both agents consume
- Modifications to this `agents.md`

---

## Agent Safety Rails

### Pre-Flight: SQL Generation Changes

Before modifying `workflow_compiler.py` or `query_router.py`:
- [ ] Read the existing compilation tests in `backend/tests/`
- [ ] Understand the current merge strategy for the node type
- [ ] Verify the target SQL dialect (ClickHouse vs Postgres)
- [ ] Confirm parameterization — no string concatenation of user input

### Pre-Flight: Frontend Changes

Before modifying canvas nodes or chart components:
- [ ] Confirm import from `@xyflow/react` (NOT `reactflow`)
- [ ] Confirm styling uses Tailwind only
- [ ] Confirm chart components live in `shared/components/charts/`
- [ ] Verify React Query for server state, Zustand for UI state only

### Pre-Flight: Cross-Cutting

Before any change that touches both backend and frontend:
- [ ] Check the Node Type Checklist — all 6 files covered?
- [ ] Schema transforms match between Python and TypeScript?
- [ ] No Alembic migration conflicts with other open branches?

---

## Multi-Agent Safety

### File Ownership Boundaries

To prevent merge conflicts when multiple agents work in parallel:

| Scope | Owns | Does NOT touch |
|-------|------|----------------|
| Backend Agent | `backend/**` | `frontend/**`, `terraform/**`, root docs |
| Frontend Agent | `frontend/**` | `backend/**`, `terraform/**`, root docs |
| Infra Agent | `terraform/**`, `.github/workflows/**` | `backend/**`, `frontend/**` |
| Docs Agent | `docs/**`, `*.md` in root | `backend/**`, `frontend/**` |

### Alembic Migration Safety

- Only ONE agent may create migrations at a time
- Check current Alembic head before generating: `alembic heads`
- If head has changed since branch creation, regenerate the migration

### Commit Scoping

Each agent commits only files within its scope. The synthesis step (human or coordinator) merges and resolves any cross-boundary issues.

---

## Model Selection for Subagents

| Task | Recommended Model | Rationale |
|------|-------------------|-----------|
| Scaffolding (boilerplate, configs) | Haiku | Fast, low-cost, pattern-following |
| Schema transforms, compiler rules | Sonnet | Needs to reason about SQL AST and type transformations |
| Complex debugging, architecture decisions | Opus | Deep reasoning for multi-file, multi-concern problems |
| Code review, test analysis | Sonnet | Good balance of depth and speed |
| Documentation, README updates | Haiku | Structured writing from existing content |

---

## Parallel-Safe vs Serial-Only

### Safe to Parallelize

- Backend schema engine + Frontend schema propagation (same node type)
- Backend tests + Frontend tests (independent test suites)
- Multiple independent node types (e.g., Rename + Unique + Sample simultaneously)
- Terraform modules (networking, GKE, CloudSQL are independent)

### Must Be Serial

- Alembic migrations (only one branch at a time)
- Changes to `agents.md`
- Shared type definitions consumed by both backend and frontend
- CI/CD workflow changes that depend on each other (build → deploy)

---

## Synthesis Protocol

After parallel agents complete, verify:

1. **Type boundary**: Backend Pydantic schemas match frontend TypeScript types
2. **Schema parity**: Python and TypeScript schema transforms produce identical results for the same test inputs
3. **Import health**: `ruff check backend/` and `npx tsc --noEmit` both pass
4. **Test suite**: `pytest backend/tests/` and `npx vitest run` both pass
5. **No orphan files**: Every new file is imported/referenced somewhere

---

## Shorthands

| Shorthand | Meaning |
|-----------|---------|
| `gate` | A checkpoint requiring human approval before proceeding (e.g., "gate: merge to main") |
| `sync` | A point where parallel agents must complete and their outputs must be reconciled before the next step |
