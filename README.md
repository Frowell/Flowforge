# FlowForge

**A visual analytics canvas + embedded BI layer for fintech trading markets. Compiles no-code workflows to SQL against a read-only serving layer.**

![Stack](https://img.shields.io/badge/React_19-Frontend-blue)
![Stack](https://img.shields.io/badge/FastAPI-Backend-green)
![Stack](https://img.shields.io/badge/ClickHouse-Analytical-yellow)
![Stack](https://img.shields.io/badge/Materialize-Streaming-purple)
![Stack](https://img.shields.io/badge/PostgreSQL-Metadata-blue)
![Stack](https://img.shields.io/badge/Redis-Cache-red)

## What is FlowForge?

FlowForge is an Alteryx-style visual analytics platform where users:
1. **Build workflows** by dragging nodes on a canvas (filter, sort, join, aggregate, chart)
2. **Pin outputs to dashboards** as auto-refreshing widgets
3. **Embed widgets** in external applications via iframe

The application reads from a serving layer (ClickHouse, Materialize, Redis) — it never writes to it. The data pipeline is a separate workstream.

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
│  Workflow CRUD │ Query Router │ WebSocket Manager            │
│  Schema Registry │ Workflow Compiler │ Live Data Service     │
└───────────────────────────┬─────────────────────────────────┘
                            │
              ┌─────────────┼─────────────────┐
              ▼             ▼                  ▼
      ┌─────────────┐ ┌─────────┐ ┌────────────────────┐
      │ ClickHouse  │ │  Redis  │ │ Materialize        │
      │ Analytical  │ │ Cache + │ │ Streaming SQL      │
      │ queries     │ │ Pub/Sub │ │ views              │
      └─────────────┘ └─────────┘ └────────────────────┘
              ▲             ▲                  ▲
              └─────────────┴──────────────────┘
                            │
                   DATA PIPELINE
                   (Redpanda → Bytewax → ClickHouse)
```

## Three Modes, One Backend

| Mode | URL | Auth | Purpose |
|------|-----|------|---------|
| **Canvas** | `/canvas` | Keycloak SSO | Author mode — build workflows visually |
| **Dashboards** | `/dashboards` | Keycloak SSO | Viewer mode — widget grid with global filters |
| **Embed** | `/embed/:widget_id` | API key | Headless mode — chromeless iframe widget |

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
   - This starts PostgreSQL, Redis, ClickHouse, Redpanda, and Materialize

3. **Start the full pipeline:**
   ```bash
   ./scripts/start-pipeline.sh
   ```

4. **Open in browser:**
   - Frontend: http://localhost:5173
   - API docs: http://localhost:8000/docs
   - ClickHouse: http://localhost:8123

### Pipeline Script Options

```bash
./scripts/start-pipeline.sh          # Start all components
./scripts/start-pipeline.sh --seed   # Start with historical data seeding
./scripts/start-pipeline.sh --stop   # Stop all components
./scripts/start-pipeline.sh --status # Show running components
```

The script starts:
- Data generator (synthetic trades/quotes → Redpanda)
- Bytewax VWAP flow (5-min VWAP windows)
- Bytewax Volatility flow (1h/24h rolling volatility)
- FastAPI backend
- Vite frontend

## Canvas Node Types

### Phase 1 — Core (5 nodes)
| Node | Purpose |
|------|---------|
| Data Source | Select table from catalog, choose columns |
| Filter | WHERE clause with type-aware operators |
| Select | Choose and reorder columns |
| Sort | ORDER BY with multi-column support |
| Table View | Paginated data grid output |

### Phase 2 — Analytical (10 nodes)
| Node | Purpose |
|------|---------|
| Group By | GROUP BY with aggregations (SUM, AVG, COUNT, etc.) |
| Join | INNER/LEFT/RIGHT/FULL joins with key mapping |
| Union | UNION ALL with column alignment |
| Formula | Computed columns with expression builder |
| Rename | Column name mapping |
| Unique | DISTINCT deduplication |
| Sample | Random row sampling |
| Limit | Row limit with offset |
| Pivot | Row/column pivoting |
| Window | Window functions (LAG, LEAD, ROW_NUMBER, etc.) |

### Phase 3 — Visualization (6 nodes)
| Node | Purpose |
|------|---------|
| Bar Chart | Horizontal/vertical bar charts |
| Line Chart | Time-series line charts |
| Candlestick | OHLC candlestick with volume |
| Scatter Plot | X/Y scatter with size/color dimensions |
| KPI Card | Single-value metric display |
| Pivot Table | Interactive pivot/crosstab |

## Data Pipeline

The pipeline (in `pipeline/`) generates and processes market data:

| Component | Purpose |
|-----------|---------|
| `generator/` | Synthetic trade/quote generator → Redpanda |
| `bytewax/flows/vwap.py` | 5-minute VWAP windows → ClickHouse + Redis |
| `bytewax/flows/volatility.py` | Rolling 1h/24h volatility → ClickHouse + Redis |
| `bytewax/flows/anomaly.py` | Spread/volume/price anomaly detection → alerts |
| `dbt/` | Cold path transformations (staging, marts) |
| `airflow/` | dbt orchestration DAG |

### Sample Data

The devcontainer includes seed data that loads automatically:
- 50,000 sample trades (last 7 days)
- 100,000 sample quotes
- 10 symbols (AAPL, MSFT, GOOGL, AMZN, NVDA, TSLA, META, JPM, BAC, GS)
- Pre-computed daily/hourly OHLCV rollups
- Dimension tables (instruments with sectors)
- Sample portfolio positions

## Key Features

### Implemented
- [x] Visual workflow builder with 21 node types
- [x] Schema-aware config panels (dropdowns auto-populate from upstream schemas)
- [x] Query merging (Filter → Select → Sort = one SQL query)
- [x] Data preview on any node (first 100 rows)
- [x] Workflow save/load with versioning
- [x] Dashboard grid with drag/resize widgets
- [x] Global dashboard filters (date range, dropdowns)
- [x] Chart drill-down with URL state sharing
- [x] Widget auto-refresh (5s, 30s, 1m, 5m, or live WebSocket)
- [x] Embed mode with API key auth
- [x] RBAC (admin, analyst, viewer roles)
- [x] Audit logging with admin UI
- [x] Undo/redo on canvas
- [x] Keyboard shortcuts
- [x] Template workflows

### Remaining
- [ ] Live query mode (Materialize → WebSocket push)
- [ ] Workflow export/import (JSON)
- [ ] E2E Playwright tests

## Make Commands

```bash
make help         # Show all commands
make dev          # Start backend + frontend
make backend      # Start FastAPI only
make frontend     # Start Vite only
make test         # Run all tests
make lint         # Lint & format all code
make migrate      # Run database migrations
make db-shell     # Open psql shell
```

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | React 19, TypeScript, @xyflow/react v12, Zustand, TanStack Query v5, Tailwind CSS, Recharts |
| Backend | Python 3.12+, async FastAPI, SQLAlchemy 2.0 async, SQLGlot, Pydantic v2 |
| App DB | PostgreSQL 16 (metadata only) |
| Analytical | ClickHouse (mart tables, rollups) |
| Streaming | Materialize (real-time views) |
| Cache | Redis 7 (schema cache, pub/sub, rate limiting) |
| Events | Redpanda (Kafka-compatible) |
| Pipeline | Bytewax (streaming), dbt (batch), Airflow (orchestration) |
| Auth | Keycloak SSO (OIDC) + API keys |
| Infra | Terraform (GCP), GitHub Actions CI/CD |

## Project Structure

```
flowforge/
├── backend/                 # FastAPI application
│   ├── app/
│   │   ├── api/routes/      # REST endpoints
│   │   ├── core/            # Config, auth, clients
│   │   ├── models/          # SQLAlchemy ORM
│   │   ├── schemas/         # Pydantic models
│   │   └── services/        # Business logic
│   ├── alembic/             # Database migrations
│   └── tests/
├── frontend/                # React SPA
│   └── src/
│       ├── features/        # Canvas, dashboards, embed
│       └── shared/          # Charts, schema, auth
├── pipeline/                # Data pipeline
│   ├── generator/           # Synthetic data generator
│   ├── bytewax/             # Streaming flows
│   ├── dbt/                 # Batch transformations
│   └── airflow/             # Orchestration
├── terraform/               # GCP infrastructure
├── k8s/                     # Kubernetes manifests
├── scripts/                 # Dev utilities
└── .devcontainer/           # Docker Compose + init scripts
```

## Documentation

| Document | Purpose |
|----------|---------|
| [Application Plan](./Application%20plan.md) | Implementation status and remaining work |
| [Planning](./planning.md) | Product scope and phase breakdown |
| [CLAUDE.md](./CLAUDE.md) | Agent coding rules |
| [docs/node-type-guide.md](./docs/node-type-guide.md) | Node implementation checklist |
| [docs/multi-tenancy.md](./docs/multi-tenancy.md) | Tenant isolation patterns |
| [docs/serving-layer.md](./docs/serving-layer.md) | Query router and table catalog |

## License

Proprietary — all rights reserved.
