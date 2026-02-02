# FlowForge

**A visual analytics canvas + embedded BI layer that compiles workflows to SQL against a read-only serving layer.**

![Stack](https://img.shields.io/badge/React_19-Frontend-blue)
![Stack](https://img.shields.io/badge/FastAPI-Backend-green)
![Stack](https://img.shields.io/badge/ClickHouse-Analytical-yellow)
![Stack](https://img.shields.io/badge/Materialize-Streaming-purple)
![Stack](https://img.shields.io/badge/PostgreSQL-Metadata-blue)
![Stack](https://img.shields.io/badge/Redis-Cache-red)

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      React SPA                               │
│                                                              │
│  /canvas            /dashboards          /embed/:id          │
│  React Flow         Widget grid          Chromeless widget   │
│  workspace          + global filters     + API key auth      │
│                                                              │
│  ┌──────────────── shared ─────────────────────────────────┐ │
│  │ query-engine │ schema-registry │ chart-renderer │ ws-mgr│ │
│  └──────────────────────────────────────────────────────────┘ │
└───────────────────────────┬─────────────────────────────────┘
                            │
                     REST + WebSocket
                            │
┌───────────────────────────┴─────────────────────────────────┐
│                      FastAPI Backend                         │
│                                                              │
│  ┌────────────┐ ┌────────────────┐ ┌──────────────────────┐ │
│  │ Workflow    │ │ Query Router   │ │ WebSocket Manager    │ │
│  │ CRUD       │ │                │ │                      │ │
│  │            │ │ Dispatches by  │ │ Subscribes to Redis  │ │
│  │ Save/load  │ │ data freshness │ │ pub/sub + Materialize│ │
│  │ workflows, │ │ to the right   │ │ change streams,      │ │
│  │ dashboards,│ │ backing store  │ │ pushes to connected  │ │
│  │ widget     │ │                │ │ dashboard clients    │ │
│  │ layouts    │ │                │ │                      │ │
│  └────────────┘ └───────┬────────┘ └──────────────────────┘ │
│                         │                                    │
│  ┌──────────────────────┤  ┌──────────────────────────────┐ │
│  │ Schema Registry      │  │ Workflow Compiler             │ │
│  │                      │  │                               │ │
│  │ Reads table/column   │  │ Translates canvas DAG into   │ │
│  │ metadata from the    │  │ ClickHouse SQL, Materialize  │ │
│  │ serving layer.       │  │ queries, or Redis lookups    │ │
│  │ Propagates schemas   │  │ depending on node types      │ │
│  │ through canvas DAG   │  │ and freshness requirements   │ │
│  └──────────────────────┘  └──────────────────────────────┘ │
└───────────────────────────┬─────────────────────────────────┘
                            │
              ┌─────────────┼─────────────────┐
              ▼             ▼                  ▼
      ┌─────────────┐ ┌─────────┐ ┌────────────────────┐
      │ ClickHouse  │ │  Redis  │ │ Materialize        │
      │             │ │         │ │ (or RisingWave)    │
      │ Analytical  │ │ Sub-ms  │ │                    │
      │ queries on  │ │ current │ │ Streaming SQL      │
      │ mart tables │ │ state   │ │ views for live     │
      │ + rollups   │ │         │ │ data               │
      └─────────────┘ └─────────┘ └────────────────────┘
              ▲             ▲                  ▲
              └─────────────┴──────────────────┘
                            │
                   DATA PIPELINE
                   (separate workstream)
```

## Three Modes, One Backend

**Canvas (`/canvas`)** — Author mode. Power users drag nodes onto a React Flow workspace, configure transforms via schema-aware GUI forms, preview intermediate results, and wire up output visualizations. Workflows compile to SQL via SQLGlot against the serving layer.

**Dashboards (`/dashboards`)** — Viewer mode. Consumers see a grid of live widgets pinned from canvas output nodes. Widgets are projections of workflow outputs — no independent queries.

**Embed (`/embed/:widget_id`)** — Headless mode. A single widget rendered chromeless for iframe embedding. API key authentication, URL params for filter overrides.

## Quick Start

### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) with Dev Containers support
- [VS Code](https://code.visualstudio.com/) with the [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)

### Setup

1. **Clone and open in VS Code:**
   ```bash
   git clone <repo-url> flowforge
   cd flowforge
   code .
   ```

2. **Reopen in container:**
   - `Ctrl+Shift+P` → "Dev Containers: Reopen in Container"

3. **Start development:**
   ```bash
   make dev
   ```

4. **Open in browser:**
   - Frontend: http://localhost:5173
   - API docs: http://localhost:8000/docs

## Key Design Decisions

- **Workflows compile to SQL, not DataFrames.** The backend is a thin translation layer via SQLGlot. The database does the heavy lifting — the app scales with ClickHouse, not with backend hardware.
- **Schema propagation is the core.** Every node declares input → output schema transforms in both TypeScript (instant client feedback) and Python (server-side authoritative). Config panels auto-populate dropdowns from upstream schemas.
- **Query merging is mandatory.** Adjacent compatible nodes merge into single SQL queries. A linear Filter → Select → Sort chain produces one query, not three.
- **Charts render with the same component everywhere.** Canvas preview, dashboard widget, and embed iframe use the same React component.
- **Dashboards are projections of workflows.** Widgets point to workflow output nodes — changing the workflow changes the widget.
- **Direct async execution.** All query compilation and execution happens inline in async FastAPI with WebSocket status streaming. No task queue — latency is critical for real-time streaming BI.

## Canvas Node Types

| Phase | Nodes |
|---|---|
| **Phase 1 — Core** | Data Source, Filter, Select, Sort, Table View |
| **Phase 2 — Analytical** | Group By, Join, Union, Formula, Rename, Unique, Sample |
| **Phase 3 — Visualization** | Bar Chart, Line Chart, Candlestick, Scatter Plot, KPI Card, Pivot Table |

## Make Commands

```
make help         Show all commands
make dev          Start all services (frontend + backend)
make backend      Start FastAPI only
make frontend     Start Vite only
make test         Run all tests
make lint         Lint & format all code
make migrate      Run database migrations
make db-shell     Open psql shell
```

## Tech Stack

| Layer | Stack |
|---|---|
| Frontend | React 19, TypeScript strict, @xyflow/react, Zustand, TanStack Query, Tailwind CSS |
| Backend | Python 3.12+, async FastAPI, SQLAlchemy 2.0 async, SQLGlot |
| App metadata | PostgreSQL 16 |
| Analytical queries | ClickHouse |
| Streaming queries | Materialize |
| Cache / pub-sub | Redis 7 |
| Auth | Keycloak SSO (canvas/dashboards), API key (embed) |
