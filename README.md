# FlowForge

**A visual analytics canvas + embedded BI layer for fintech trading markets. Compiles no-code workflows to SQL against a read-only serving layer.**

![Stack](https://img.shields.io/badge/React_19-Frontend-blue)
![Stack](https://img.shields.io/badge/FastAPI-Backend-green)
![Stack](https://img.shields.io/badge/ClickHouse-Analytical-yellow)
![Stack](https://img.shields.io/badge/Materialize-Streaming-purple)
![Stack](https://img.shields.io/badge/PostgreSQL-Metadata-blue)
![Stack](https://img.shields.io/badge/Redis-Cache-red)

---

## Table of Contents

- [What is FlowForge?](#what-is-flowforge)
- [Architecture Overview](#architecture-overview)
  - [System Diagram](#system-diagram)
  - [Three Modes, One Backend](#three-modes-one-backend)
  - [Design Philosophy](#design-philosophy)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Devcontainer Setup (Recommended)](#devcontainer-setup-recommended)
  - [Manual Setup](#manual-setup)
  - [Docker Compose Profiles](#docker-compose-profiles)
  - [Authentication in Development](#authentication-in-development)
  - [Seeding Sample Data](#seeding-sample-data)
- [How It Works](#how-it-works)
  - [Schema Propagation Engine](#schema-propagation-engine)
  - [Workflow Compilation & Query Merging](#workflow-compilation--query-merging)
  - [Query Router](#query-router)
  - [Preview System](#preview-system)
  - [Dashboard & Widget Lifecycle](#dashboard--widget-lifecycle)
  - [Live Data Flow](#live-data-flow)
  - [Formula Builder](#formula-builder)
  - [Multi-Tenancy](#multi-tenancy)
- [Canvas Node Types](#canvas-node-types)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
  - [Backend](#backend-structure)
  - [Frontend](#frontend-structure)
  - [Infrastructure & Pipeline](#infrastructure--pipeline)
- [API Reference](#api-reference)
- [Configuration Reference](#configuration-reference)
- [Development Commands](#development-commands)
- [Testing](#testing)
- [CI/CD Pipeline](#cicd-pipeline)
- [Production Deployment](#production-deployment)
- [Documentation Index](#documentation-index)
- [License](#license)

---

## What is FlowForge?

FlowForge is an Alteryx-style visual analytics platform purpose-built for fintech trading desks. Users build data transformation workflows by dragging nodes onto a canvas, configure each step through schema-aware GUI panels, then pin chart outputs to live dashboards or embed them in external applications.

**What it does:**

1. **Build workflows visually** — Drag nodes (filter, sort, join, aggregate, chart) onto a React Flow canvas and connect them. Configuration panels auto-populate with available columns and type-appropriate operators from upstream nodes.
2. **Pin outputs to dashboards** — Chart and table outputs from the canvas become auto-refreshing dashboard widgets. Global filters (date range, symbol dropdown) propagate to all widgets simultaneously.
3. **Embed widgets externally** — Any widget renders as a chromeless iframe authenticated via API key, suitable for embedding in customer portals or internal tools.

**What it does NOT do:**

- FlowForge does not own data ingestion. The data pipeline (Redpanda, Bytewax, dbt, Airflow) is a separate workstream.
- FlowForge never writes to ClickHouse, Materialize, or Redis. The serving layer is strictly read-only.
- FlowForge does not execute Python/Pandas/Polars. All data processing compiles to SQL via SQLGlot and executes on the analytical databases.

---

## Architecture Overview

### System Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              React SPA (Vite)                               │
│                                                                             │
│  /canvas                    /dashboards                /embed/:widget_id    │
│  ┌───────────────────┐     ┌──────────────────────┐   ┌──────────────────┐  │
│  │ React Flow v12    │     │ react-grid-layout     │   │ Chromeless       │  │
│  │ workspace         │     │ widget grid           │   │ single widget    │  │
│  │                   │     │                       │   │                  │  │
│  │ 18 node types     │     │ Global filters        │   │ API key auth     │  │
│  │ Schema-aware      │     │ Auto-refresh          │   │ URL param        │  │
│  │ config panels     │     │ Drill-down            │   │ filter overrides │  │
│  └───────────────────┘     └──────────────────────┘   └──────────────────┘  │
│                                                                             │
│  ┌────────────── Shared layer (used by all three modes) ──────────────────┐ │
│  │  Schema Engine (TS)  │  Chart Components (Recharts)  │  WebSocket Mgr  │ │
│  │  TanStack Query      │  Zustand (UI state)           │  Keycloak Auth  │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                           REST + WebSocket
                                  │
┌─────────────────────────────────┴───────────────────────────────────────────┐
│                           FastAPI Backend (async)                            │
│                                                                             │
│  ┌──────────────┐  ┌───────────────────┐  ┌──────────────────────────────┐  │
│  │ Workflow CRUD │  │ Workflow Compiler  │  │ WebSocket Manager            │  │
│  │              │  │                   │  │                              │  │
│  │ Save, load,  │  │ Canvas DAG →      │  │ Redis pub/sub fan-out,      │  │
│  │ version,     │  │ Topological sort → │  │ Materialize SUBSCRIBE,     │  │
│  │ export/import│  │ Query merge →      │  │ dashboard live push         │  │
│  └──────────────┘  │ SQLGlot SQL        │  └──────────────────────────────┘  │
│                    └───────────────────┘                                     │
│  ┌──────────────┐  ┌───────────────────┐  ┌──────────────────────────────┐  │
│  │ Schema       │  │ Query Router      │  │ Live Data Service            │  │
│  │ Registry     │  │                   │  │                              │  │
│  │              │  │ Dispatches by     │  │ Materialize SUBSCRIBE with   │  │
│  │ Discovers    │  │ data freshness    │  │ poll-mode fallback,          │  │
│  │ tables from  │  │ to the right      │  │ ref-counted shared views,    │  │
│  │ CH + MZ      │  │ backing store     │  │ health-check mode switching  │  │
│  └──────────────┘  └────────┬──────────┘  └──────────────────────────────┘  │
│                             │                                               │
│  ┌──────────────┐  ┌───────┴───────────┐  ┌──────────────────────────────┐  │
│  │ Preview      │  │ Formula Parser    │  │ Audit Service                │  │
│  │ Service      │  │                   │  │                              │  │
│  │ Redis-cached │  │ [column] bracket  │  │ Who did what, when.          │  │
│  │ content-hash │  │ notation → AST →  │  │ CRUD, export, import,       │  │
│  │ first 100    │  │ ClickHouse SQL    │  │ role-gated admin panel.      │  │
│  │ rows         │  └───────────────────┘  └──────────────────────────────┘  │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                ┌─────────────────┼──────────────────┐
                ▼                 ▼                   ▼
        ┌──────────────┐  ┌────────────┐  ┌────────────────────┐
        │  ClickHouse  │  │   Redis    │  │   Materialize      │
        │              │  │            │  │                    │
        │  Analytical  │  │  Schema    │  │  Streaming SQL     │
        │  queries on  │  │  cache,    │  │  materialized      │
        │  mart tables │  │  pub/sub,  │  │  views for live    │
        │  + rollups   │  │  rate      │  │  positions, P&L,   │
        │              │  │  limiting  │  │  quotes            │
        └──────────────┘  └────────────┘  └────────────────────┘
                ▲                 ▲                   ▲
                └─────────────────┴───────────────────┘
                                  │
                         DATA PIPELINE
                         (Redpanda → Bytewax → serving layer)
                         Separate workstream. Owns ingestion,
                         transformation, and shaping.
```

### Three Modes, One Backend

FlowForge is a single application that presents three interfaces to different user types, all powered by the same FastAPI backend and shared component library:

| Mode | URL | Auth | Users | Purpose |
|------|-----|------|-------|---------|
| **Canvas** | `/canvas` | Keycloak SSO | Analysts, Admins | Author mode — build and edit workflows on a React Flow workspace |
| **Dashboards** | `/dashboards` | Keycloak SSO | Everyone | Viewer mode — consume pinned widget grid with global filters |
| **Embed** | `/embed/:widget_id` | API key (`sk_live_...`) | External apps | Headless mode — single chromeless widget in an iframe |

The key insight: **a dashboard widget and a canvas output node are the same thing, rendered in different containers**. The same `<BarChart>` component renders identically in a canvas data preview, a dashboard widget card, and an embedded iframe. One implementation, one set of bugs, one place to fix.

### Design Philosophy

Six architectural rules govern every decision in the codebase:

1. **The app does NOT own data ingestion.** The serving layer (ClickHouse, Materialize, Redis) is read-only from FlowForge's perspective. No DDL, no INSERT, no CREATE VIEW. Data arrives via the pipeline.

2. **Workflows compile to SQL via SQLGlot, NOT DataFrames.** The database does the heavy lifting. FlowForge is a thin translation layer that converts visual DAGs into optimized SQL. This means performance scales with ClickHouse/Materialize hardware, not with backend pods.

3. **Schema propagation is the core.** Every node type declares how it transforms input schemas to output schemas, implemented identically in both TypeScript (instant client-side feedback) and Python (authoritative server-side validation). This is what makes the no-code canvas actually work — dropdowns populate with real column names, operators change based on column types, and type mismatches are caught before any query runs.

4. **Query merging is mandatory.** Adjacent compatible nodes merge into single SQL queries. A 5-node linear workflow (Source → Filter → Select → Sort → Table) produces ONE database round-trip, not five. This is the difference between 50ms and 500ms execution.

5. **Charts use the same component everywhere.** Canvas preview, dashboard widget, and embed iframe all import from `shared/components/charts/`. No duplication.

6. **Dashboards are projections of workflows.** A widget points to a workflow output node. It has no independent query. Changing the workflow changes the widget. Deleting the workflow orphans the widget (explicit error state, not silent disappearance).

---

## Getting Started

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (4.0+) with at least 8 GB RAM allocated
- [VS Code](https://code.visualstudio.com/) with the [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)

### Devcontainer Setup (Recommended)

The devcontainer provides a fully configured development environment with all services pre-wired:

```bash
# 1. Clone the repository
git clone <repo-url> flowforge
cd flowforge

# 2. Open in VS Code
code .

# 3. Reopen in container (Ctrl+Shift+P → "Dev Containers: Reopen in Container")
#    This builds the container and starts core services:
#    - PostgreSQL 16 (app metadata)
#    - Redis 7 (cache + pub/sub)
#    - ClickHouse (analytical queries)
#    - Redpanda (Kafka-compatible event streaming)
#
#    The post-create hook automatically:
#    - Installs Python and Node.js dependencies
#    - Runs Alembic database migrations
#    - Seeds ClickHouse with sample market data

# 4. Start the application
make dev
#    This starts both:
#    - FastAPI backend on http://localhost:8000
#    - Vite frontend on http://localhost:5173

# 5. Open in browser
#    Frontend:     http://localhost:5173
#    API docs:     http://localhost:8000/docs
#    ClickHouse:   http://localhost:8123
```

### Manual Setup

If you prefer not to use the devcontainer:

```bash
# Backend
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

You'll need to provide your own PostgreSQL, Redis, ClickHouse, and optionally Materialize and Redpanda instances. Configure them via environment variables (see [Configuration Reference](#configuration-reference)).

### Docker Compose Profiles

The devcontainer uses Docker Compose profiles to keep optional services from consuming resources when not needed:

```bash
# Core services start automatically: PostgreSQL, Redis, ClickHouse, Redpanda

# Start Materialize for real-time streaming views
docker compose --profile streaming up -d

# Start Keycloak for SSO authentication testing
docker compose --profile auth up -d

# Start pgAdmin for database administration
docker compose --profile tools up -d

# Combine profiles
docker compose --profile streaming --profile auth up -d
```

| Profile | Service | Port | Purpose |
|---------|---------|------|---------|
| *(core)* | PostgreSQL | 5432 | App metadata (workflows, dashboards, users) |
| *(core)* | Redis | 6379 | Schema cache, WebSocket pub/sub, rate limiting |
| *(core)* | ClickHouse | 8123 | Analytical queries on mart tables and rollups |
| *(core)* | Redpanda | 9092 | Kafka-compatible event streaming |
| `streaming` | Materialize | 6875 | Streaming SQL materialized views |
| `auth` | Keycloak | 8081 | OIDC identity provider |
| `tools` | pgAdmin | 8080 | PostgreSQL admin UI |

### Authentication in Development

By default, the devcontainer runs with **dev auth mode** enabled (`VITE_DEV_AUTH=true` in `frontend/.env`). This bypasses Keycloak entirely and provides a mock user with:

- User ID: `00000000-0000-0000-0000-000000000001`
- Tenant ID: `00000000-0000-0000-0000-000000000002`
- Roles: `admin` (full access)

To test with real Keycloak authentication:

```bash
# 1. Start Keycloak
docker compose --profile auth up -d

# 2. Disable dev auth in frontend/.env
VITE_DEV_AUTH=false

# 3. Keycloak admin console: http://localhost:8081/admin (admin/admin)
```

Pre-configured test users in the `flowforge` realm:

| Email | Password | Tenant | Role |
|-------|----------|--------|------|
| admin@tenant-a.test | admin123 | tenant-a | admin |
| analyst@tenant-a.test | analyst123 | tenant-a | analyst |
| admin@tenant-b.test | admin123 | tenant-b | admin |
| viewer@tenant-b.test | viewer123 | tenant-b | viewer |

### Seeding Sample Data

```bash
# Seed ClickHouse with sample market data (runs automatically in devcontainer)
make seed

# Seed 6 months of historical trades for time-series testing
make seed-historical

# Start the live data generator (synthetic trades/quotes → Redpanda → ClickHouse)
make generator
```

Sample data includes:
- 50,000 trades and 100,000 quotes across the last 7 days
- 10 symbols: AAPL, MSFT, GOOGL, AMZN, NVDA, TSLA, META, JPM, BAC, GS
- Pre-computed OHLCV rollups (hourly and daily)
- Dimension tables (instruments with sectors, exchanges)
- Sample portfolio positions

---

## How It Works

### Schema Propagation Engine

The schema engine is the architectural core of FlowForge. It makes the no-code canvas functional by giving every configuration panel contextual awareness of what data is available upstream.

```
User connects Filter node to DataSource node
         │
         ▼
┌─────────────────────────────────────────────────────┐
│ TypeScript Schema Engine (runs client-side, instant) │
│                                                     │
│ 1. DataSource outputs: [symbol, price, quantity,    │
│    event_time, exchange]                            │
│                                                     │
│ 2. Filter panel receives this schema:               │
│    - Column dropdown: shows all 5 columns           │
│    - Operator picker: "symbol" is string →          │
│      shows =, !=, contains, starts_with             │
│    - "price" is float → shows =, !=, >, <, >=, <=  │
│    - "event_time" is datetime → shows before, after │
│                                                     │
│ 3. Filter output schema: same 5 columns             │
│    (passthrough — filters rows, not columns)        │
└─────────────────────────────────────────────────────┘
         │
         ▼ (on workflow execution)
┌─────────────────────────────────────────────────────┐
│ Python Schema Engine (runs server-side, authoritative│
│                                                     │
│ Re-validates the full DAG before any query executes. │
│ Catches: missing columns, type mismatches, broken   │
│ connections, circular references.                    │
└─────────────────────────────────────────────────────┘
```

Every node type declares its schema transform:

```
Node Type       Input Schema → Output Schema
─────────       ──────────────────────────────────────
Data Source     (none) → table schema from catalog
Filter          passthrough (same columns, fewer rows)
Select          subset of input columns (user picks which)
Rename          input columns with name substitutions
Sort            passthrough (same columns, reordered rows)
Limit           passthrough (capped row count)
Sample          passthrough (random subset of rows)
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

Both the TypeScript and Python implementations are tested against the same set of 11 shared JSON fixtures to ensure they produce identical output for identical inputs (cross-validation).

### Workflow Compilation & Query Merging

When a user previews data or runs a workflow, the backend compiles the canvas DAG into executable SQL:

```
Step 1: Topological Sort
   Determine execution order respecting node dependencies

Step 2: Schema Validation
   Re-validate every connection (authoritative server-side check)

Step 3: Query Merging ← THIS IS THE CRITICAL OPTIMIZATION
   Adjacent compatible nodes collapse into single SQL queries

Step 4: Target Selection
   Query router picks ClickHouse, Materialize, or Redis per segment

Step 5: Execution
   Run compiled queries, return results via REST or stream via WebSocket
```

**Query merging in practice:**

```
Canvas DAG:
  [DataSource: trades] → [Filter: symbol='AAPL'] → [Sort: time DESC] → [Table View]

Without merging (naive): 3 database round-trips
  Query 1: SELECT * FROM fct_trades
  Query 2: SELECT * FROM (...) WHERE symbol = 'AAPL'
  Query 3: SELECT * FROM (...) ORDER BY event_time DESC

With merging: 1 database round-trip
  SELECT * FROM fct_trades
  WHERE symbol = 'AAPL'
  ORDER BY event_time DESC
  LIMIT 1000
```

```
Complex DAG:
  [Source: trades] ──→ [Join on symbol] ←── [Source: instruments]
                              │
                       [GroupBy: sector, SUM(notional)]
                              │
                         [Bar Chart]

Merged into 1 query:
  SELECT i.sector, SUM(t.quantity * t.price) AS notional
  FROM fct_trades t
  JOIN dim_instruments i ON t.symbol = i.symbol
  GROUP BY i.sector
```

All SQL is generated via **SQLGlot** — never string concatenation. User-supplied values are always parameterized to prevent SQL injection.

### Query Router

The query router is the only component that knows about the backing stores. Canvas nodes express intent ("I need the positions table with real-time freshness"), and the router dispatches to the right database:

```
Intent                          Target              Latency
──────────────────────────      ─────────────────   ──────────
Live data (positions, P&L)      Materialize         < 10ms
Point lookup (latest quote)     Redis               < 1ms
Ad-hoc analytical query         ClickHouse          < 500ms
Historical time-range query     ClickHouse rollups  < 500ms
App metadata / catalog          PostgreSQL          < 50ms
```

SQL dialect is set per target: `dialect="clickhouse"` for ClickHouse (HTTP protocol, port 8123), `dialect="postgres"` for Materialize (PG wire protocol, port 6875).

### Preview System

Canvas data previews ("click a node, see its output") use a three-layer execution model:

```
Layer 1: Client-Side Schema (instant, no network)
  TypeScript propagation shows output columns and types
  immediately as nodes are connected — before any query runs.

Layer 2: Content-Addressed Redis Cache (< 1ms on hit)
  Cache key = SHA256(tenant_id, target_node_id, upstream_configs, offset, limit)
  TTL: 5 minutes. UI-only fields (position, selection) are stripped
  from the hash so dragging a node doesn't invalidate the cache.

Layer 3: Live Execution (on cache miss)
  Compile node subgraph → merged SQL → execute against serving layer
  Safety constraints: LIMIT 100 rows, 3s timeout, 100MB memory cap
  Cache result for next request.
```

### Dashboard & Widget Lifecycle

```
1. User builds a workflow with a chart output node on the canvas
2. User clicks "Pin to Dashboard" → picks or creates a target dashboard
3. System creates a Widget record:
   - dashboard_id → which dashboard
   - source_workflow_id → which workflow
   - source_node_id → which output node
   - layout (x, y, w, h) → position in the grid
4. Widget appears on the dashboard in a react-grid-layout grid
5. Widget query executes on dashboard load and refreshes on interval:
   - Manual, 5s, 30s, 1m, 5m, or Live (WebSocket)
6. Global filters (date range, dropdowns) inject WHERE clauses into
   every widget's compiled query simultaneously
7. Drill-down: click a chart element → filter chips appear → URL updates
   → shareable deep link with embedded filter state
```

**Widgets are pointers, not copies.** Changing the source workflow updates the widget. Deleting the source workflow shows an explicit error state on the widget ("Source workflow deleted"), not a silent disappearance.

### Live Data Flow

For real-time dashboard updates, FlowForge supports two modes with automatic health-check switching:

```
Mode 1: Materialize SUBSCRIBE (preferred, < 100ms latency)
  ┌────────────┐    SUBSCRIBE TO    ┌──────────────┐    Redis     ┌────────────┐
  │ Materialize │ ─── live_pnl ───→ │ LiveData     │ ── pub/sub → │ WebSocket  │
  │ (streaming  │    WITH (SNAPSHOT  │ Service      │              │ Manager    │
  │  SQL view)  │     = false)       │ (backend)    │              │ → clients  │
  └────────────┘                    └──────────────┘              └────────────┘

Mode 2: Poll Fallback (when Materialize is unavailable)
  ┌────────────┐    SELECT * FROM    ┌──────────────┐    Redis     ┌────────────┐
  │ ClickHouse │ ── fct_trades ───→ │ LiveData     │ ── pub/sub → │ WebSocket  │
  │ (or other  │    every 5s         │ Service      │              │ Manager    │
  │  source)   │                     │ (backend)    │              │ → clients  │
  └────────────┘                    └──────────────┘              └────────────┘

Health Check (every 30s):
  - Materialize up?   → upgrade poll-mode widgets to SUBSCRIBE
  - Materialize down? → downgrade SUBSCRIBE widgets to poll
  - Multiple widgets on same view share one SUBSCRIBE connection (ref-counted)
```

### Formula Builder

A restricted expression language for calculated columns — the low-code escape hatch for users who need arithmetic, conditionals, or functions without writing SQL:

```
Syntax:
  [column_name]                    Column reference (bracket notation)
  [revenue] - [cost]               Arithmetic
  IF([qty] > 1000, "large", "sm")  Conditionals
  ROUND([price] * [qty], 2)        Functions

Available Functions:
  Math:   ABS, ROUND, CEIL, FLOOR, MOD, POWER, SQRT, LOG
  Text:   UPPER, LOWER, TRIM, LEFT, RIGHT, LENGTH, CONCAT, REPLACE
  Date:   YEAR, MONTH, DAY, HOUR, DATE_DIFF, DATE_ADD, NOW
  Logic:  IF, CASE, COALESCE, NULLIF
  Agg:    SUM, AVG, COUNT, MIN, MAX (inside Group By only)
  Window: LAG, LEAD, ROW_NUMBER, RANK (with Sort defined)

Compilation:
  User writes:   ([revenue] - [cost]) / [revenue] * 100
  Compiles to:   (revenue - cost) / revenue * 100

  User writes:   IF([quantity] > 1000, "large", "small")
  Compiles to:   CASE WHEN quantity > 1000 THEN 'large' ELSE 'small' END
```

Expressions are parsed to AST client-side (for syntax highlighting and validation) and compiled to SQL server-side via `formula_parser.py`.

### Multi-Tenancy

FlowForge is multi-tenant by design. Every piece of data is scoped to a `tenant_id` extracted from the JWT:

```
Request → JWT validation → extract tenant_id claim → inject into every query

Core rules:
  1. tenant_id comes from JWT (never from request body or URL params)
  2. Every database query includes WHERE tenant_id = :tenant_id
  3. Cross-tenant access returns 404 (not 403) to prevent enumeration
  4. Cache keys include tenant_id (prevents cross-tenant cache leaks)
  5. WebSocket channels are prefixed with tenant_id
  6. API keys are scoped to a tenant via the api_keys table
```

The serving layer (ClickHouse, Materialize) doesn't have `tenant_id` columns — those tables contain market data shared across tenants. Isolation for market data tables is via symbol-based ACL: the workflow compiler injects `WHERE symbol IN (:allowed_symbols)` based on the tenant's entitlements.

See [`docs/multi-tenancy.md`](./docs/multi-tenancy.md) for the complete set of isolation rules and code patterns.

---

## Canvas Node Types

### Phase 1 — Core (5 nodes)

| Node | Category | Config Panel | Compiles To |
|------|----------|-------------|-------------|
| **Data Source** | Input | Table picker from schema catalog, column selection | `SELECT` from ClickHouse/Materialize |
| **Filter** | Transform | Column dropdown, type-aware operator picker, value input, AND/OR groups | `WHERE` clause |
| **Select** | Transform | Checkbox column list, drag to reorder | `SELECT` column list |
| **Sort** | Transform | Column dropdown, ASC/DESC toggle, multi-column priority | `ORDER BY` clause |
| **Table View** | Output | Pagination, column visibility, sort-on-click | Rendered `<DataGrid>` |

### Phase 2 — Analytical (10 nodes)

| Node | Category | Config Panel | Compiles To |
|------|----------|-------------|-------------|
| **Group By** | Aggregate | Dimension picker, metric + aggregation function (SUM/AVG/COUNT/MIN/MAX) | `GROUP BY` + aggregates |
| **Join** | Combine | Join type (inner/left/right/full), key column mapping from each input | `JOIN ... ON` |
| **Union** | Combine | Column alignment mapping between inputs | `UNION ALL` |
| **Formula** | Calculate | Expression editor with `[column]` refs, function palette, type preview | Computed column expression |
| **Rename** | Transform | Column name mapping (old → new) | `SELECT col AS new_name` |
| **Unique** | Transform | Column subset for deduplication key | `DISTINCT` |
| **Sample** | Transform | Row count or percentage, random seed option | `SAMPLE` or `LIMIT` |
| **Limit** | Transform | Max rows + offset | `LIMIT ... OFFSET` |
| **Pivot** | Aggregate | Row/column dimension pickers, value + aggregation | Pivot query |
| **Window** | Calculate | Window function, partition columns, order columns | Window expression |

### Phase 3 — Visualization (6 nodes)

| Node | Category | Config Panel | Renders As |
|------|----------|-------------|------------|
| **Bar Chart** | Output | X/Y axis columns, color grouping, orientation, stacked | Recharts `<BarChart>` |
| **Line Chart** | Output | Time axis, Y-axis series, line style, area fill | Recharts `<LineChart>` |
| **Candlestick** | Output | OHLC column mapping, time axis, volume subplot | Recharts custom |
| **Scatter Plot** | Output | X/Y axis, size column, color column | Recharts `<ScatterChart>` |
| **KPI Card** | Output | Metric column, aggregation, threshold coloring | Custom card component |
| **Pivot Table** | Output | Row/column dimensions, value + aggregation | Pivoted data grid |

---

## Tech Stack

| Layer | Technology | Why |
|-------|------------|-----|
| **Frontend** | React 19, strict TypeScript | Modern React with concurrent features |
| **Canvas** | `@xyflow/react` v12 | Best-in-class node graph editor for React |
| **Client state** | Zustand 5 + zundo | Minimal store with built-in undo/redo |
| **Server state** | TanStack Query v5 | Automatic caching, refetching, optimistic updates |
| **Styling** | Tailwind CSS 3.4 | Utility-first, no CSS-in-JS, no CSS modules |
| **Charts** | Recharts 2.13 | Composable React chart components |
| **Dashboard layout** | react-grid-layout 1.5 | Drag/resize widget grid |
| **Data grid** | TanStack Table v8 | Headless, sortable, paginated tables |
| **Auth (client)** | keycloak-js 26 | OIDC adapter for SPA |
| **Build** | Vite 6 | Fast HMR, ESM-native bundling |
| **Backend** | Python 3.12+, async FastAPI | High-performance async web framework |
| **ORM** | SQLAlchemy 2.0 async | Type-safe async ORM with `Mapped` columns |
| **SQL generation** | SQLGlot 25+ | AST-based SQL generation (never string concat) |
| **Validation** | Pydantic v2 | Request/response schema validation |
| **App DB** | PostgreSQL 16 | App metadata only (workflows, dashboards, users) |
| **Analytical** | ClickHouse | Columnar OLAP for mart tables and rollups |
| **Streaming** | Materialize | Streaming SQL materialized views |
| **Cache** | Redis 7 | Schema cache, pub/sub for WebSocket fan-out, rate limiting |
| **Events** | Redpanda | Kafka-compatible streaming (pipeline ingestion) |
| **Auth (server)** | Keycloak 26 (OIDC) | SSO identity provider with multi-tenant support |
| **Pipeline** | Bytewax, dbt, Airflow | Streaming + batch transformation (separate workstream) |
| **Infra** | Terraform (GCP), GitHub Actions | IaC + CI/CD |
| **K8s** | Kustomize overlays (dev/prod) | Environment-specific configuration |

---

## Project Structure

```
flowforge/
├── backend/                          # FastAPI application
│   ├── app/
│   │   ├── api/
│   │   │   ├── deps.py              # Dependency injection (DB, auth, services)
│   │   │   └── routes/              # Thin REST route handlers
│   │   │       ├── health.py        # /health, /health/live, /health/ready
│   │   │       ├── workflows.py     # Workflow CRUD + export/import + versions
│   │   │       ├── executions.py    # Execute workflow, get status
│   │   │       ├── dashboards.py    # Dashboard CRUD
│   │   │       ├── widgets.py       # Widget CRUD + pin/unpin
│   │   │       ├── embed.py         # Embed widget data (API key auth)
│   │   │       ├── schema.py        # Schema catalog (tables, columns)
│   │   │       ├── templates.py     # Workflow template CRUD
│   │   │       ├── api_keys.py      # API key management
│   │   │       ├── audit.py         # Audit log query
│   │   │       ├── ws.py            # WebSocket endpoint
│   │   │       └── metrics.py       # Prometheus /metrics
│   │   ├── core/
│   │   │   ├── config.py            # pydantic-settings (all env vars)
│   │   │   ├── database.py          # Async SQLAlchemy engine + sessions
│   │   │   ├── auth.py              # Keycloak OIDC + API key + dev bypass
│   │   │   ├── clickhouse.py        # ClickHouse HTTP client
│   │   │   ├── materialize.py       # Materialize asyncpg pool + SUBSCRIBE
│   │   │   ├── redis.py             # Redis async client
│   │   │   ├── logging_config.py    # structlog (JSON in prod, console in dev)
│   │   │   ├── metrics.py           # Prometheus metrics registry
│   │   │   └── middleware.py        # ObservabilityMiddleware (request IDs)
│   │   ├── models/                  # SQLAlchemy ORM (PostgreSQL only)
│   │   │   ├── user.py              # User, UserRole enum
│   │   │   ├── workflow.py          # Workflow, WorkflowVersion
│   │   │   ├── dashboard.py         # Dashboard, Widget, DashboardFilter, APIKey
│   │   │   └── audit_log.py         # AuditLog, AuditAction, AuditResourceType
│   │   ├── schemas/                 # Pydantic request/response models
│   │   └── services/               # Business logic layer
│   │       ├── schema_registry.py   # Discover tables from CH + Materialize
│   │       ├── schema_engine.py     # DAG schema validation (17 transforms)
│   │       ├── workflow_compiler.py # Canvas DAG → merged SQL via SQLGlot
│   │       ├── query_router.py      # Dispatch to CH/Materialize/Redis
│   │       ├── formula_parser.py    # [column] bracket syntax → SQL AST
│   │       ├── preview_service.py   # Content-addressed Redis cache + execution
│   │       ├── live_data_service.py # SUBSCRIBE + poll fallback + health check
│   │       ├── websocket_manager.py # WS connection tracking, Redis pub/sub
│   │       ├── widget_data_service.py # Widget query execution + caching
│   │       ├── audit_service.py     # Audit log creation
│   │       ├── rate_limiter.py      # Redis fixed-window rate limiter (embed)
│   │       └── template_registry.py # Workflow template management
│   ├── alembic/                     # Database migrations
│   │   └── versions/               # 2 migrations (initial + audit logs)
│   ├── tests/                       # 234 tests (mirrors app/ structure)
│   │   ├── api/                     # Route integration tests
│   │   ├── services/                # Service unit tests
│   │   └── integration/             # Tests requiring real services
│   └── pyproject.toml               # Dependencies, linting, test config
│
├── frontend/                        # React SPA
│   ├── src/
│   │   ├── features/
│   │   │   ├── canvas/              # Editor mode
│   │   │   │   ├── components/      # Canvas.tsx, NodePalette, ConfigPanel, etc.
│   │   │   │   ├── nodes/           # 18 node components (DataSourceNode, etc.)
│   │   │   │   ├── panels/          # 16 config panels (FilterPanel, etc.)
│   │   │   │   ├── hooks/           # useWorkflow, useSchemaEngine, etc.
│   │   │   │   └── stores/          # workflowStore (Zustand + zundo undo/redo)
│   │   │   ├── dashboards/          # Viewer mode
│   │   │   │   ├── components/      # DashboardGrid, WidgetCard, GlobalFilters
│   │   │   │   ├── hooks/           # useDashboard, useWidgetData, etc.
│   │   │   │   └── stores/          # dashboardStore
│   │   │   ├── embed/               # Headless mode
│   │   │   │   ├── EmbedRoot.tsx    # Minimal shell, API key auth
│   │   │   │   └── EmbedWidget.tsx  # Single widget renderer
│   │   │   └── admin/               # Admin pages
│   │   │       └── AuditLogPage.tsx # Audit trail viewer
│   │   ├── shared/
│   │   │   ├── components/
│   │   │   │   ├── charts/          # 7 chart components (shared across all modes)
│   │   │   │   │   ├── BarChart.tsx
│   │   │   │   │   ├── LineChart.tsx
│   │   │   │   │   ├── CandlestickChart.tsx
│   │   │   │   │   ├── ScatterPlot.tsx
│   │   │   │   │   ├── KPICard.tsx
│   │   │   │   │   ├── PivotTable.tsx
│   │   │   │   │   └── ChartRenderer.tsx  # Dispatch by chart type
│   │   │   │   ├── DataGrid.tsx     # TanStack Table wrapper
│   │   │   │   └── FormulaEditor.tsx # Expression input + highlighting
│   │   │   ├── schema/
│   │   │   │   ├── propagation.ts   # Client-side schema engine (17 transforms)
│   │   │   │   ├── registry.ts      # Schema registry API client
│   │   │   │   └── types.ts         # ColumnSchema, NodeType definitions
│   │   │   ├── auth/
│   │   │   │   └── keycloak.ts      # Keycloak OIDC adapter
│   │   │   ├── websocket/
│   │   │   │   └── manager.ts       # WebSocket connection management
│   │   │   └── query-engine/
│   │   │       ├── client.ts        # HTTP API client
│   │   │       └── types.ts         # Query/response types
│   │   ├── App.tsx                  # Router + layout + auth guard
│   │   ├── main.tsx                 # Entry point
│   │   └── test-setup.ts            # Vitest setup (happy-dom, ResizeObserver mock)
│   ├── e2e/                         # Playwright E2E tests (5 P0 flows)
│   ├── package.json
│   ├── vite.config.ts
│   ├── vitest.config.ts
│   ├── playwright.config.ts
│   ├── tsconfig.json
│   ├── tailwind.config.js
│   └── .env                         # VITE_DEV_AUTH, VITE_API_BASE_URL
│
├── pipeline/                        # Data pipeline (separate workstream)
│   ├── generator/                   # Synthetic trade/quote generator → Redpanda
│   ├── bytewax/                     # Streaming flows (VWAP, volatility, anomaly)
│   ├── dbt/                         # Batch transformations (staging → marts)
│   └── airflow/                     # dbt orchestration DAG
│
├── k8s/                             # Kubernetes manifests
│   ├── base/                        # Base resources (all services)
│   │   ├── infra/                   # PostgreSQL, Redis, ClickHouse, etc.
│   │   └── app/                     # Backend + frontend deployments
│   └── overlays/
│       ├── dev/                     # Dev-specific patches
│       └── prod/                    # HPA, PDB, Ingress, resource limits
│
├── terraform/                       # GCP infrastructure (40 files, ~2K lines)
│   ├── modules/                     # networking, gke, cloudsql, memorystore, etc.
│   └── environments/                # dev, staging, prod
│
├── .github/workflows/               # CI/CD (7 workflows)
├── .devcontainer/                   # Docker Compose + init scripts + Keycloak realm
├── scripts/                         # Dev utilities (start-pipeline, seed, etc.)
├── docs/                            # Documentation
│   ├── decisions/                   # Architecture Decision Records (ADRs)
│   ├── rfcs/                        # Proposals for significant changes
│   ├── archive/                     # Completed planning docs (historical)
│   ├── node-type-guide.md           # Node type checklist + query merging rules
│   ├── multi-tenancy.md             # Tenant isolation patterns
│   └── serving-layer.md             # Table catalog + query router dispatch
├── tests/fixtures/schema/           # Shared cross-validation JSON fixtures
├── Makefile                         # Development commands
└── CLAUDE.md                        # Agent coding rules
```

---

## API Reference

All endpoints are prefixed with `/api/v1/`. Interactive Swagger docs are available at `http://localhost:8000/docs`.

### Workflows

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/workflows` | SSO | List workflows (paginated, tenant-scoped) |
| `GET` | `/workflows/{id}` | SSO | Get workflow by ID |
| `POST` | `/workflows` | SSO (admin/analyst) | Create workflow |
| `PATCH` | `/workflows/{id}` | SSO (admin/analyst) | Update workflow (auto-snapshots version) |
| `DELETE` | `/workflows/{id}` | SSO (admin/analyst) | Delete workflow |
| `GET` | `/workflows/{id}/export` | SSO (admin/analyst) | Export workflow as JSON |
| `POST` | `/workflows/import` | SSO (admin/analyst) | Import workflow (regenerates all IDs) |
| `GET` | `/workflows/{id}/versions` | SSO | List workflow versions |
| `POST` | `/workflows/{id}/versions/{vid}/rollback` | SSO (admin/analyst) | Rollback to version |

### Dashboards & Widgets

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/dashboards` | SSO | List dashboards |
| `POST` | `/dashboards` | SSO (admin/analyst) | Create dashboard |
| `PATCH` | `/dashboards/{id}` | SSO (admin/analyst) | Update dashboard |
| `DELETE` | `/dashboards/{id}` | SSO (admin/analyst) | Delete dashboard |
| `GET` | `/widgets` | SSO | List widgets for a dashboard |
| `POST` | `/widgets` | SSO (admin/analyst) | Pin widget to dashboard |
| `PATCH` | `/widgets/{id}` | SSO (admin/analyst) | Update widget config/layout |
| `DELETE` | `/widgets/{id}` | SSO (admin/analyst) | Remove widget from dashboard |

### Execution & Preview

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/executions` | SSO | Execute workflow subgraph |
| `GET` | `/executions/{id}` | SSO | Get execution status |

### Embed

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/embed/{widget_id}/data` | API key | Fetch widget data for embed |

### Schema & Templates

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/schema/tables` | SSO | List available tables from serving layer |
| `GET` | `/schema/tables/{name}/columns` | SSO | Get columns for a table |
| `GET` | `/templates` | SSO | List workflow templates |

### Infrastructure

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/health` | None | Legacy health check |
| `GET` | `/health/live` | None | Liveness probe (K8s) |
| `GET` | `/health/ready` | None | Readiness probe (checks PG, Redis, CH) |
| `GET` | `/metrics` | None | Prometheus scrape endpoint |
| `WS` | `/ws/dashboard/{id}` | SSO | WebSocket for live data push |

---

## Configuration Reference

All configuration is via environment variables, managed by `pydantic-settings` in `backend/app/core/config.py`. Never use `os.getenv()` directly.

### Application

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_ENV` | `development` | `development` or `production`. Controls auth bypass, logging format, CORS |
| `SECRET_KEY` | `dev-secret-change-in-prod` | JWT signing key |
| `CORS_ORIGINS` | `["http://localhost:5173"]` | Allowed CORS origins (JSON array) |
| `LOG_LEVEL` | `INFO` | structlog level (DEBUG, INFO, WARNING, ERROR) |
| `METRICS_ENABLED` | `true` | Enable Prometheus metrics export |

### PostgreSQL (App Metadata)

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://flowforge:flowforge@db:5432/flowforge` | Async ORM connection |
| `DATABASE_URL_SYNC` | `postgresql://flowforge:flowforge@db:5432/flowforge` | Alembic migrations |

### ClickHouse (Analytical Queries)

| Variable | Default | Description |
|----------|---------|-------------|
| `CLICKHOUSE_HOST` | `localhost` | HTTP endpoint |
| `CLICKHOUSE_PORT` | `8123` | HTTP port (not native 9000) |
| `CLICKHOUSE_DATABASE` | `default` | Database name |
| `CLICKHOUSE_USER` | `default` | Auth user |
| `CLICKHOUSE_PASSWORD` | *(empty)* | Auth password |

### Materialize (Streaming SQL)

| Variable | Default | Description |
|----------|---------|-------------|
| `MATERIALIZE_HOST` | `localhost` | PG wire endpoint |
| `MATERIALIZE_PORT` | `6875` | PG wire port |
| `MATERIALIZE_DATABASE` | `materialize` | Database name |
| `MATERIALIZE_USER` | `materialize` | Auth user |
| `MATERIALIZE_SUBSCRIBE_ENABLED` | `true` | Enable SUBSCRIBE for live data |
| `MATERIALIZE_POOL_MIN_SIZE` | `2` | Connection pool minimum |
| `MATERIALIZE_POOL_MAX_SIZE` | `10` | Connection pool maximum |

### Redis

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_URL` | `redis://redis:6379/0` | Redis connection URL |

### Keycloak (OIDC)

| Variable | Default | Description |
|----------|---------|-------------|
| `KEYCLOAK_URL` | `http://keycloak:8080` | Keycloak base URL |
| `KEYCLOAK_REALM` | `flowforge` | OIDC realm |
| `KEYCLOAK_CLIENT_ID` | `flowforge-app` | Client ID |
| `KEYCLOAK_CLIENT_SECRET` | *(empty)* | Client secret (optional for public clients) |

### Frontend

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_DEV_AUTH` | `true` | Bypass Keycloak with mock dev user |
| `VITE_API_BASE_URL` | `http://localhost:8000` | Backend API base URL |

---

## Development Commands

```bash
# Application
make dev              # Start backend + frontend with live-reload
make backend          # Start FastAPI only (0.0.0.0:8000)
make frontend         # Start Vite only (0.0.0.0:5173)

# Database
make migrate          # Run Alembic migrations (alembic upgrade head)
make migrate-new msg="description"  # Create new migration with autogenerate
make db-shell         # Open psql shell to PostgreSQL
make db-reset         # Drop and recreate database (DESTRUCTIVE)

# Testing
make test             # Run all tests (backend + frontend)
make test-back        # Backend pytest with coverage
make test-front       # Frontend vitest

# Code Quality
make lint             # Ruff (Python) + ESLint + Prettier (TypeScript)
make typecheck        # mypy (Python) + tsc --noEmit (TypeScript)

# Data
make seed             # Seed dev user + ClickHouse sample data
make seed-historical  # 6 months of historical trades
make generator        # Start synthetic data generator → Redpanda
make check            # Verify connectivity to all services

# Pipeline
./scripts/start-pipeline.sh          # Start full pipeline + app
./scripts/start-pipeline.sh --seed   # Start with historical data
./scripts/start-pipeline.sh --stop   # Stop all components
./scripts/start-pipeline.sh --status # Show running components

# Cleanup
make clean            # Remove build artifacts, caches, dist
```

---

## Testing

### Test Suite Summary

| Suite | Framework | Tests | Coverage |
|-------|-----------|-------|----------|
| Backend unit + integration | pytest (async) | 234 | API routes, services, tenant isolation |
| Frontend unit | Vitest + happy-dom | 101 | Nodes, panels, charts, hooks, schema engine, stores |
| Schema cross-validation | pytest + Vitest | 22 (11 per engine) | Python/TypeScript parity across 11 fixtures |
| E2E | Playwright (Chromium) | 5 flows | Workflow creation, save/load, dashboards, embed, live data |

### Running Tests

```bash
# All backend tests (skips integration tests requiring real services)
cd backend && pytest

# Backend integration tests (requires ClickHouse/Materialize running)
cd backend && pytest -m integration

# All frontend unit tests
cd frontend && npx vitest run

# Schema parity validation (both engines against shared fixtures)
bash scripts/validate-schema-parity.sh

# E2E tests (requires running frontend + backend)
cd frontend && npx playwright test
```

### Test Architecture

**Backend tests** mock all external stores (ClickHouse, Materialize, Redis) — they never require running instances. Integration tests (marked `@pytest.mark.integration`) connect to real services and are skipped in CI unless services are available.

**Frontend tests** use `happy-dom` for DOM simulation. React Flow components mock `@xyflow/react` handles. TanStack Query hooks are tested via a `QueryClientProvider` wrapper.

**Cross-validation** ensures the TypeScript and Python schema engines produce identical output for identical inputs. Both engines load the same 11 JSON fixture files from `tests/fixtures/schema/` covering: linear chains, joins, group-by, formula, union, pivot, window, rename, complex DAGs, and edge cases.

---

## CI/CD Pipeline

### GitHub Actions Workflows

| Workflow | Trigger | Jobs |
|----------|---------|------|
| `ci.yml` | PR to main | Backend lint/format/type/test, Frontend lint/format/type/test, Integration tests (optional) |
| `build.yml` | Push to main | Build Docker images → GCP Artifact Registry |
| `deploy-dev.yml` | Push to main | Deploy to GKE dev cluster |
| `deploy-staging.yml` | Manual | Deploy to GKE staging |
| `deploy-prod.yml` | Manual | Deploy to GKE prod |
| `terraform-plan.yml` | PR with TF changes | Terraform plan preview |
| `terraform-apply.yml` | Push to main (TF paths) | Apply Terraform changes |

### CI Checks (Required to Merge)

```
Backend:
  ✓ ruff check backend/           # Lint (E, W, F, I, N, UP, B, SIM rules)
  ✓ ruff format --check backend/  # Format
  ✓ mypy backend/app/             # Type check
  ✓ pytest backend/tests/ -m "not integration"  # Unit tests

Frontend:
  ✓ npx eslint src/               # Lint
  ✓ npx tsc --noEmit              # Type check
  ✓ npx prettier --check src/     # Format
  ✓ npx vitest run                # Unit tests
```

---

## Production Deployment

### Infrastructure (GCP via Terraform)

```
┌─────────────────────────────────────────────────────────────────┐
│                        GCP Project                               │
│                                                                  │
│  ┌──────────────────┐  ┌────────────────────────────────────┐   │
│  │ Artifact Registry │  │ GKE Cluster                        │   │
│  │ Docker images     │  │                                    │   │
│  └──────────────────┘  │  ┌─────────┐  ┌─────────────────┐  │   │
│                        │  │ Backend │  │ Frontend (nginx) │  │   │
│  ┌──────────────────┐  │  │ pods    │  │ pods             │  │   │
│  │ Secret Manager   │  │  │ HPA 2-10│  │ HPA 2-5         │  │   │
│  │ Credentials      │  │  └─────────┘  └─────────────────┘  │   │
│  └──────────────────┘  │                                    │   │
│                        │  ┌──────────────────────────────┐  │   │
│  ┌──────────────────┐  │  │ Ingress (TLS via cert-mgr)   │  │   │
│  │ Cloud DNS        │  │  │ /api/* → backend             │  │   │
│  │ Public endpoint  │  │  │ /* → frontend                │  │   │
│  └──────────────────┘  │  └──────────────────────────────┘  │   │
│                        └────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────┐  ┌──────────────────┐                     │
│  │ Cloud SQL        │  │ Memorystore      │                     │
│  │ (PostgreSQL 16)  │  │ (Redis 7)        │                     │
│  │ Private IP       │  │ Private endpoint  │                     │
│  │ Auto backups     │  │ VPC-internal      │                     │
│  └──────────────────┘  └──────────────────┘                     │
└─────────────────────────────────────────────────────────────────┘
```

Terraform modules: `networking` (VPC, subnets, NAT), `gke` (cluster, node pools, Workload Identity), `cloudsql` (PostgreSQL, private IP, backups), `memorystore` (Redis), `registry` (Artifact Registry), `secrets` (Secret Manager), `iam` (service accounts), `dns` (Cloud DNS).

Three environments (`dev`, `staging`, `prod`), each in a separate GCP project with isolated state (GCS backend).

### Kubernetes Overlays

```bash
# Dev (default resources, no autoscaling)
kubectl apply -k k8s/overlays/dev/

# Production (HPA, PDB, Ingress, resource limits)
kubectl apply -k k8s/overlays/prod/
```

Production overlay adds:
- **HPA**: Backend scales 2-10 pods at 70% CPU; Frontend scales 2-5 pods
- **PDB**: minAvailable: 1 for both backend and frontend (zero-downtime deploys)
- **Ingress**: TLS termination via cert-manager, WebSocket annotation, path-based routing
- **Resource limits**: Backend 512Mi/500m request, 1Gi/2000m limit; Frontend 128Mi/200m request

In production, PostgreSQL and Redis are GCP managed services (Cloud SQL, Memorystore) accessed via Private Service Access — not in-cluster pods.

---

## Documentation Index

| Document | Description |
|----------|-------------|
| [CLAUDE.md](./CLAUDE.md) | Agent coding rules (architectural constraints, conventions) |
| [docs/decisions/](./docs/decisions/) | Architecture Decision Records — why key technical decisions were made |
| [docs/rfcs/](./docs/rfcs/) | Proposals for significant changes (pre-decision) |
| [docs/node-type-guide.md](./docs/node-type-guide.md) | Node type checklist, schema propagation rules, query merging |
| [docs/multi-tenancy.md](./docs/multi-tenancy.md) | Tenant isolation patterns, code examples, test requirements |
| [docs/serving-layer.md](./docs/serving-layer.md) | Table catalog, query router dispatch rules, SQL dialects |
| [backend/CLAUDE.md](./backend/CLAUDE.md) | Backend-specific rules (models, services, auth, testing) |
| [backend/app/api/CLAUDE.md](./backend/app/api/CLAUDE.md) | API route conventions, endpoint catalog, auth patterns |
| [terraform/agents.md](./terraform/agents.md) | Terraform module structure and GCP infrastructure |
| [.github/workflows/agents.md](./.github/workflows/agents.md) | CI/CD workflow documentation |
| [docs/archive/](./docs/archive/) | Completed planning docs (historical reference) |

---

## License

Proprietary — all rights reserved.
