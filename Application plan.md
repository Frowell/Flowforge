# FlowForge Implementation Plan

> This document is the single source of truth for implementing FlowForge.
> It contains every architectural decision, every file, every configuration,
> and every script needed to build the platform from scratch. Follow it literally.
> When this document and any other source conflict, this document wins.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Repository Structure](#2-repository-structure)
3. [Infrastructure — Local K8s with k3d](#3-infrastructure--local-k8s-with-k3d)
4. [K8s Manifests](#4-k8s-manifests)
5. [Tiltfile — Dev Loop Orchestration](#5-tiltfile--dev-loop-orchestration)
6. [Dockerfiles](#6-dockerfiles)
7. [Data Pipeline — Four Temperature Lanes](#7-data-pipeline--four-temperature-lanes)
8. [Application Layer — Canvas + BI + Embed](#8-application-layer--canvas--bi--embed)
9. [Multi-Tenancy](#9-multi-tenancy)
10. [Authentication — Keycloak](#10-authentication--keycloak)
11. [Schema Engine](#11-schema-engine)
12. [Query Router](#12-query-router)
13. [Workflow Compiler](#13-workflow-compiler)
14. [Data Preview and Pagination](#14-data-preview-and-pagination)
15. [Dashboard System](#15-dashboard-system)
16. [Frontend Architecture](#16-frontend-architecture)
17. [Backend Architecture](#17-backend-architecture)
18. [Seed Data and Data Generator](#18-seed-data-and-data-generator)
19. [AGENTS.md and Memory Files](#19-agentsmd-and-memory-files)
20. [Development Workflow](#20-development-workflow)
21. [Testing Strategy](#21-testing-strategy)
22. [Implementation Phases](#22-implementation-phases)

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
- FlowForge reads from the serving layer. It never writes to it (except app metadata in PostgreSQL)
- The pipeline exists in the same monorepo for co-development but is architecturally independent

### The Integration Contract

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

### Single Application, Three Modes

FlowForge is ONE application with three URL-based modes sharing one backend:

| Mode | URL | Auth | Purpose |
|------|-----|------|---------|
| Canvas | `/canvas` | OIDC (Keycloak) | Author mode — React Flow workspace for building workflows |
| Dashboards | `/dashboards` | OIDC (Keycloak) | Viewer mode — widget grid from pinned canvas outputs |
| Embed | `/embed/:widget_id` | API key (stateless) | Headless mode — chromeless iframe |

Dashboard widgets ARE canvas output nodes rendered differently. They are not separate objects. A widget record references a workflow ID + output node ID. When the workflow updates, the widget updates. No sync problem.

### Technology Stack

| Layer | Technology | Justification |
|-------|-----------|---------------|
| Frontend | React 18 + TypeScript + React Flow v12 | Industry standard for node-based UIs |
| State | Zustand | Lightweight, no boilerplate, works with React Flow |
| Data fetching | TanStack Query v5 | Cache management, optimistic updates, WebSocket integration |
| Styling | Tailwind CSS | Utility-first, no CSS modules, no styled-components |
| Charts | Apache ECharts via echarts-for-react | Candlestick, heatmap, treemap support. Same component renders in canvas, dashboard, and embed |
| Backend | FastAPI (Python 3.12, async) | I/O-bound workload, mature ecosystem, Polars fallback for edge cases |
| ORM | SQLAlchemy 2.0 (async) | PostgreSQL app metadata only |
| Migrations | Alembic | Schema migrations for PostgreSQL |
| Validation | Pydantic v2 | Request/response models, settings management |
| Auth | Keycloak (self-hosted) | Multi-tenant OIDC, realm-per-customer, zero external auth dependencies |
| ClickHouse client | clickhouse-connect | HTTP protocol, simpler debugging, adequate performance |
| Materialize client | asyncpg | PG wire protocol compatible |
| Redis client | redis-py (async) | Standard async Redis |
| WebSocket | FastAPI WebSocket + Redis pub/sub | Live data push to dashboards |

### Why Python (not Go)

The backend is I/O-bound: it waits on database queries, not CPU computation. Databases do the heavy lifting. FastAPI + async handles concurrent connections well. Polars is available for the rare DataFrame fallback. The ecosystem (Keycloak clients, SQLAlchemy, ClickHouse drivers) is mature. WebSocket fan-out memory at scale (500 connections ≈ 1GB vs 50MB in Go) is irrelevant — revenue at that connection count dwarfs the infrastructure cost difference.

### Why SQL-First Compilation

The workflow compiler's primary target is SQL, not DataFrames. 90%+ of workflows execute as pure SQL against ClickHouse or Materialize. The database does the heavy lifting. DataFrame fallback (Polars) exists only for edge cases: cross-database joins, CSV uploads, complex formulas that can't compile to SQL.

Query merging is critical: a 5-node linear workflow compiles to 1 SQL query with nested subqueries, not 5 round trips. This is the difference between 50ms and 500ms.

---

## 2. Repository Structure

One monorepo. No polyrepo. The workflow compiler spans frontend components, backend validation, and SQL generation — that's one feature across multiple directories, and it must be one PR.

```
flowforge/
├── AGENTS.md                              # Cross-tool agent instructions (the real file)
├── CLAUDE.md -> AGENTS.md                 # Symlink for Claude Code compatibility
├── CLAUDE.local.md                        # Personal overrides (gitignored)
├── Tiltfile                               # Dev loop orchestration
├── Makefile                               # Convenience commands
├── docker-compose.yml                     # Fallback for non-K8s development
├── docker-compose.run.yml                 # Override: actual entrypoints (not sleep infinity)
│
├── backend/                               # FastAPI application
│   ├── AGENTS.md                          # Backend-specific agent instructions
│   ├── CLAUDE.md -> AGENTS.md             # Symlink
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── alembic/
│   │   └── versions/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                        # FastAPI app factory
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── config.py                  # Pydantic Settings (all env vars)
│   │   │   ├── database.py                # Async SQLAlchemy session factory
│   │   │   ├── clickhouse.py              # ClickHouse client factory
│   │   │   ├── materialize.py             # Materialize (asyncpg) client factory
│   │   │   ├── redis.py                   # Async Redis client factory
│   │   │   ├── auth.py                    # Keycloak JWT validation + get_current_user
│   │   │   └── tenant.py                  # Tenant extraction from JWT
│   │   ├── models/                        # SQLAlchemy models (PostgreSQL)
│   │   │   ├── __init__.py
│   │   │   ├── base.py                    # Declarative base with tenant_id mixin
│   │   │   ├── workflow.py
│   │   │   ├── dashboard.py
│   │   │   ├── widget.py
│   │   │   ├── api_key.py
│   │   │   └── audit_log.py
│   │   ├── schemas/                       # Pydantic models (API contracts)
│   │   │   ├── __init__.py
│   │   │   ├── workflow.py
│   │   │   ├── dashboard.py
│   │   │   ├── widget.py
│   │   │   ├── preview.py
│   │   │   └── schema_info.py
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── deps.py                    # Shared dependencies (get_db, get_tenant, etc.)
│   │   │   └── routes/
│   │   │       ├── __init__.py
│   │   │       ├── health.py
│   │   │       ├── workflows.py
│   │   │       ├── dashboards.py
│   │   │       ├── widgets.py
│   │   │       ├── preview.py             # Data preview endpoint
│   │   │       ├── schema.py              # Schema discovery endpoint
│   │   │       └── embed.py               # Embed endpoints (API key auth)
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── schema_registry.py         # Caches table/column metadata
│   │   │   ├── schema_engine.py           # Propagates schemas through node graphs
│   │   │   ├── query_router.py            # Dispatches queries to correct backing store
│   │   │   ├── workflow_compiler.py        # Compiles node graphs to SQL
│   │   │   ├── formula_parser.py          # Parses formula expressions to SQL
│   │   │   └── websocket_manager.py       # WebSocket connection management
│   │   └── websocket/
│   │       ├── __init__.py
│   │       └── handler.py                 # WebSocket endpoint for live data
│   └── tests/
│       ├── conftest.py                  # Async DB session, tenant fixtures, factory helpers
│       ├── api/                         # Route handler integration tests
│       │   ├── test_workflows.py
│       │   ├── test_dashboards.py
│       │   ├── test_widgets.py
│       │   ├── test_preview.py
│       │   ├── test_embed_auth.py
│       │   └── test_health.py
│       └── services/                    # Service unit tests
│           ├── test_workflow_compiler.py
│           ├── test_schema_engine.py
│           ├── test_query_router.py
│           ├── test_formula_parser.py
│           └── test_tenant_isolation.py
│
├── frontend/                              # React SPA
│   ├── AGENTS.md                          # Frontend-specific agent instructions
│   ├── CLAUDE.md -> AGENTS.md             # Symlink
│   ├── Dockerfile
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   ├── index.html
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── routes.tsx                     # React Router: /canvas, /dashboards, /embed/:id
│       ├── features/
│       │   ├── canvas/
│       │   │   ├── Canvas.tsx             # Main canvas component (React Flow wrapper)
│       │   │   ├── store.ts              # Zustand store for canvas state
│       │   │   ├── nodes/                 # React Flow custom node components
│       │   │   │   ├── DataSourceNode.tsx
│       │   │   │   ├── FilterNode.tsx
│       │   │   │   ├── SelectNode.tsx
│       │   │   │   ├── SortNode.tsx
│       │   │   │   ├── GroupByNode.tsx
│       │   │   │   ├── JoinNode.tsx
│       │   │   │   ├── FormulaNode.tsx
│       │   │   │   └── TableViewNode.tsx
│       │   │   ├── panels/                # Config panels for each node type
│       │   │   │   ├── DataSourcePanel.tsx
│       │   │   │   ├── FilterPanel.tsx
│       │   │   │   ├── SelectPanel.tsx
│       │   │   │   ├── SortPanel.tsx
│       │   │   │   ├── GroupByPanel.tsx
│       │   │   │   ├── JoinPanel.tsx
│       │   │   │   └── FormulaPanel.tsx
│       │   │   └── preview/
│       │   │       └── PreviewTable.tsx   # Data preview component (100-row table)
│       │   ├── dashboards/
│       │   │   ├── Dashboard.tsx          # Dashboard grid layout
│       │   │   ├── store.ts
│       │   │   └── WidgetContainer.tsx    # Wraps chart/table in dashboard context
│       │   └── embed/
│       │       └── EmbedView.tsx          # Headless single-widget view
│       ├── shared/
│       │   ├── components/
│       │   │   └── charts/                # SHARED chart components — never duplicate
│       │   │       ├── BarChart.tsx
│       │   │       ├── LineChart.tsx
│       │   │       ├── CandlestickChart.tsx
│       │   │       ├── ScatterPlot.tsx
│       │   │       ├── KPICard.tsx
│       │   │       └── PivotTable.tsx
│       │   ├── schema/
│       │   │   └── propagation.ts         # Client-side schema propagation (TypeScript)
│       │   ├── query/
│       │   │   └── queryClient.ts         # TanStack Query configuration
│       │   ├── auth/
│       │   │   ├── AuthProvider.tsx        # Keycloak OIDC provider
│       │   │   └── useAuth.ts
│       │   └── websocket/
│       │       └── useWebSocket.ts        # WebSocket hook for live data
│       ├── types/
│       │   ├── workflow.ts                # TypeScript types matching Pydantic schemas
│       │   ├── node.ts                    # Node type definitions
│       │   └── schema.ts                  # Schema types
│       └── __tests__/                     # Vitest test files
│           ├── setup.ts                   # Global test setup (mocks, cleanup)
│           ├── helpers/
│           │   ├── render.tsx             # Custom render with providers
│           │   └── factories.ts           # Test data factories
│           ├── shared/
│           │   ├── schema/
│           │   │   └── propagation.test.ts
│           │   └── components/
│           │       └── charts/
│           │           └── BarChart.test.tsx
│           └── features/
│               ├── canvas/
│               │   ├── Canvas.test.tsx
│               │   ├── nodes/
│               │   │   └── FilterNode.test.tsx
│               │   └── hooks/
│               │       └── useWorkflow.test.ts
│               └── dashboards/
│                   └── Dashboard.test.tsx
│
├── pipeline/                              # Data pipeline (separate workstream)
│   ├── generator/
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── generator.py                   # Main loop: produces synthetic market data
│   │   ├── models.py                      # Trade, Quote, Order message schemas
│   │   └── distributions.py              # Realistic price walks, volume curves
│   ├── bytewax/
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── flows/
│   │       ├── vwap.py                    # 5-min VWAP windows → ClickHouse + Redis
│   │       ├── volatility.py              # Rolling volatility → ClickHouse
│   │       └── anomaly.py                 # Spread/volume anomaly detection
│   ├── materialize/
│   │   ├── 000_sources.sql                # CREATE SOURCE from Redpanda topics
│   │   ├── 001_staging.sql                # Parse raw JSON → typed columns
│   │   └── 002_views.sql                  # Materialized views: positions, P&L, quotes
│   ├── dbt/
│   │   ├── dbt_project.yml
│   │   ├── profiles.yml                   # Targets ClickHouse
│   │   ├── models/
│   │   │   ├── staging/
│   │   │   │   ├── stg_trades.sql
│   │   │   │   └── stg_instruments.sql
│   │   │   ├── intermediate/
│   │   │   │   ├── int_trades_enriched.sql
│   │   │   │   └── int_clearing_matched.sql
│   │   │   └── marts/
│   │   │       ├── fct_trades.sql
│   │   │       ├── dim_instruments.sql
│   │   │       └── rpt_daily_pnl.sql
│   │   ├── seeds/
│   │   │   ├── instruments.csv
│   │   │   └── counterparties.csv
│   │   └── tests/
│   │       └── assert_no_orphan_trades.sql
│   └── airflow/
│       └── dags/
│           └── dbt_cold_path.py           # DAG that triggers dbt run on schedule
│
├── k8s/                                   # Kubernetes manifests
│   ├── base/
│   │   ├── kustomization.yaml
│   │   ├── namespace.yaml
│   │   ├── infra/
│   │   │   ├── redpanda.yaml
│   │   │   ├── clickhouse.yaml
│   │   │   ├── materialize.yaml
│   │   │   ├── redis.yaml
│   │   │   └── postgres.yaml
│   │   ├── pipeline/
│   │   │   ├── bytewax.yaml
│   │   │   ├── airflow.yaml
│   │   │   ├── data-generator.yaml
│   │   │   └── init-materialize-job.yaml
│   │   └── app/
│   │       ├── backend.yaml
│   │       └── frontend.yaml
│   └── overlays/
│       ├── dev/
│       │   ├── kustomization.yaml
│       │   ├── resource-limits.yaml
│       │   └── configmap-dev.yaml
│       └── prod/
│           ├── kustomization.yaml
│           ├── resource-limits.yaml
│           ├── hpa.yaml
│           ├── pdb.yaml
│           └── ingress.yaml
│
├── infra/                                 # Init scripts and configs for infrastructure
│   ├── clickhouse/
│   │   ├── init.sql                       # Database, users, base tables
│   │   └── create_mvs.sql                # Materialized views for cool path
│   ├── postgres/
│   │   └── init.sql                       # App database, airflow database
│   └── redpanda/
│       └── console-config.yml             # Redpanda Console configuration
│
├── scripts/
│   ├── seed.py                            # Master seed script
│   ├── seed_historical.py                 # Seed 6 months of historical data
│   ├── seed_reference.py                  # Seed reference data (instruments, counterparties)
│   ├── check-connectivity.sh              # Health check all services
│   ├── init-materialize.sh                # Run Materialize SQL setup scripts
│   └── setup-cluster.sh                   # Create k3d cluster
│
├── docs/
│   ├── PLANNING.md                        # Product planning (canvas + BI scope)
│   ├── ARCHITECTURE.md                    # Pipeline architecture (4 temperature lanes)
│   └── DECISIONS.md                       # Technical decision log
│
├── .devcontainer/                         # Per-service devcontainer configs
│   ├── backend/
│   │   └── devcontainer.json
│   ├── frontend/
│   │   └── devcontainer.json
│   └── bytewax/
│       └── devcontainer.json
│
└── .github/
    └── workflows/
        ├── ci.yml
        ├── build-backend.yml
        ├── build-frontend.yml
        └── deploy.yml
```

Every file listed above MUST be created. If a file is listed, it exists. If it is not listed, do not create it.

---

## 3. Infrastructure — Local K8s with k3d

### Why k3d

k3d runs k3s (Rancher's lightweight K8s) inside Docker containers on WSL2. It is the lightest option (~512MB overhead), includes a built-in container registry, and produces the same K8s API as production. The manifests written for k3d work identically on EKS/GKE/AKS.

### Prerequisites

The developer machine must have:
- Windows 10/11 with WSL2 enabled
- Docker Desktop for Windows (with WSL2 backend)
- At minimum 32GB system RAM (20GB allocated to WSL2)

### WSL2 Configuration

Create or update `%UserProfile%\.wslconfig`:

```ini
[wsl2]
memory=20GB
swap=8GB
processors=8
```

Restart WSL after changing: `wsl --shutdown` then reopen terminal.

### Cluster Setup Script

**File: `scripts/setup-cluster.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail

CLUSTER_NAME="flowforge"
REGISTRY_NAME="flowforge-registry"
REGISTRY_PORT="5111"

echo "=== FlowForge Cluster Setup ==="

# Check prerequisites
command -v docker >/dev/null 2>&1 || { echo "ERROR: docker not found"; exit 1; }
command -v k3d >/dev/null 2>&1 || { echo "ERROR: k3d not found. Install: curl -s https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh | bash"; exit 1; }
command -v kubectl >/dev/null 2>&1 || { echo "ERROR: kubectl not found"; exit 1; }
command -v tilt >/dev/null 2>&1 || { echo "ERROR: tilt not found. Install: curl -fsSL https://raw.githubusercontent.com/tilt-dev/tilt/master/scripts/install.sh | bash"; exit 1; }
command -v helm >/dev/null 2>&1 || { echo "ERROR: helm not found. Install: curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash"; exit 1; }

# Delete existing cluster if present
if k3d cluster list | grep -q "$CLUSTER_NAME"; then
  echo "Deleting existing cluster..."
  k3d cluster delete "$CLUSTER_NAME"
fi

echo "Creating k3d cluster: $CLUSTER_NAME"
k3d cluster create "$CLUSTER_NAME" \
  --servers 1 \
  --agents 2 \
  --registry-create "${REGISTRY_NAME}:0:${REGISTRY_PORT}" \
  --port "8000:80@loadbalancer" \
  --port "5173:5173@loadbalancer" \
  --port "8123:8123@loadbalancer" \
  --port "8180:8180@loadbalancer" \
  --port "8280:8280@loadbalancer" \
  --port "6875:6875@loadbalancer" \
  --port "9092:9092@loadbalancer" \
  --port "9644:9644@loadbalancer" \
  --port "6379:6379@loadbalancer" \
  --port "5432:5432@loadbalancer" \
  --k3s-arg "--disable=traefik@server:0" \
  --wait

echo "Cluster created. Verifying..."
kubectl cluster-info
kubectl get nodes

# Create namespace
kubectl create namespace flowforge --dry-run=client -o yaml | kubectl apply -f -

echo ""
echo "=== Cluster Ready ==="
echo "Registry: localhost:${REGISTRY_PORT}"
echo "Namespace: flowforge"
echo ""
echo "Next steps:"
echo "  1. cd to project root"
echo "  2. Run: tilt up"
echo "  3. Open: http://localhost:10350 (Tilt UI)"
```

### Install Script for All CLI Tools

**File: `scripts/install-tools.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail

echo "=== Installing FlowForge Development Tools ==="

# k3d
if ! command -v k3d &>/dev/null; then
  echo "Installing k3d..."
  curl -s https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh | bash
fi

# kubectl
if ! command -v kubectl &>/dev/null; then
  echo "Installing kubectl..."
  curl -LO "https://dl.k8s.io/release/$(curl -Ls https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
  sudo install kubectl /usr/local/bin/
  rm kubectl
fi

# Helm
if ! command -v helm &>/dev/null; then
  echo "Installing Helm..."
  curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
fi

# Tilt
if ! command -v tilt &>/dev/null; then
  echo "Installing Tilt..."
  curl -fsSL https://raw.githubusercontent.com/tilt-dev/tilt/master/scripts/install.sh | bash
fi

# k9s
if ! command -v k9s &>/dev/null; then
  echo "Installing k9s..."
  curl -sS https://webinstall.dev/k9s | bash
fi

# rpk (Redpanda CLI)
if ! command -v rpk &>/dev/null; then
  echo "Installing rpk..."
  curl -LO https://github.com/redpanda-data/redpanda/releases/latest/download/rpk-linux-amd64.zip
  unzip rpk-linux-amd64.zip -d /tmp/rpk
  sudo install /tmp/rpk/rpk /usr/local/bin/
  rm -rf rpk-linux-amd64.zip /tmp/rpk
fi

echo ""
echo "=== All tools installed ==="
echo "Versions:"
k3d version
kubectl version --client --short 2>/dev/null || kubectl version --client
helm version --short
tilt version
k9s version --short 2>/dev/null || echo "k9s installed"
rpk version
```

### Connectivity Check Script

**File: `scripts/check-connectivity.sh`**

```bash
#!/usr/bin/env bash
set -uo pipefail

echo "=== FlowForge Connectivity Check ==="
echo ""

check() {
  local name="$1"
  local cmd="$2"
  printf "%-20s" "$name:"
  if eval "$cmd" >/dev/null 2>&1; then
    echo "✅"
  else
    echo "❌"
  fi
}

check "PostgreSQL" "pg_isready -h postgres.flowforge.svc.cluster.local -p 5432 -U flowforge"
check "Redis" "redis-cli -h redis.flowforge.svc.cluster.local ping | grep -q PONG"
check "ClickHouse HTTP" "curl -sf http://clickhouse.flowforge.svc.cluster.local:8123/ping"
check "Materialize" "psql -h materialize.flowforge.svc.cluster.local -p 6875 -U materialize -c 'SELECT 1'"
check "Redpanda Admin" "curl -sf http://redpanda.flowforge.svc.cluster.local:9644/v1/cluster/health_overview | grep -q is_healthy"

echo ""
echo "=== Redpanda Topics ==="
rpk topic list --brokers redpanda.flowforge.svc.cluster.local:29092 2>/dev/null || echo "rpk not available in this container"

echo ""
echo "=== ClickHouse Tables ==="
curl -sf "http://clickhouse.flowforge.svc.cluster.local:8123/?query=SHOW+TABLES+FROM+flowforge" 2>/dev/null || echo "No tables yet"

echo ""
echo "=== Materialize Views ==="
psql -h materialize.flowforge.svc.cluster.local -p 6875 -U materialize -c "SHOW MATERIALIZED VIEWS" 2>/dev/null || echo "No views yet"
```

---

## 4. K8s Manifests

### Kustomize Base

**File: `k8s/base/kustomization.yaml`**

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: flowforge

resources:
  - namespace.yaml
  # Infrastructure
  - infra/redpanda.yaml
  - infra/clickhouse.yaml
  - infra/materialize.yaml
  - infra/redis.yaml
  - infra/postgres.yaml
  # Pipeline
  - pipeline/data-generator.yaml
  - pipeline/bytewax.yaml
  - pipeline/airflow.yaml
  - pipeline/init-materialize-job.yaml
  # Application
  - app/backend.yaml
  - app/frontend.yaml
```

**File: `k8s/base/namespace.yaml`**

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: flowforge
```

### Infrastructure Manifests

**File: `k8s/base/infra/redpanda.yaml`**

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: redpanda
  namespace: flowforge
spec:
  serviceName: redpanda
  replicas: 1
  selector:
    matchLabels:
      app: redpanda
  template:
    metadata:
      labels:
        app: redpanda
    spec:
      containers:
        - name: redpanda
          image: redpandadata/redpanda:latest
          args:
            - redpanda start
            - --smp 2
            - --memory 1500M
            - --reserve-memory 0M
            - --overprovisioned
            - --node-id 0
            - --kafka-addr PLAINTEXT://0.0.0.0:29092,OUTSIDE://0.0.0.0:9092
            - --advertise-kafka-addr PLAINTEXT://redpanda.flowforge.svc.cluster.local:29092,OUTSIDE://localhost:9092
            - --set redpanda.auto_create_topics_enabled=true
          ports:
            - containerPort: 29092
              name: kafka-internal
            - containerPort: 9092
              name: kafka-external
            - containerPort: 9644
              name: admin
          resources:
            requests:
              memory: "1Gi"
              cpu: "500m"
            limits:
              memory: "2Gi"
              cpu: "2000m"
          readinessProbe:
            httpGet:
              path: /v1/status/ready
              port: 9644
            initialDelaySeconds: 10
            periodSeconds: 5
          volumeMounts:
            - name: data
              mountPath: /var/lib/redpanda/data
  volumeClaimTemplates:
    - metadata:
        name: data
      spec:
        accessModes: ["ReadWriteOnce"]
        resources:
          requests:
            storage: 5Gi
---
apiVersion: v1
kind: Service
metadata:
  name: redpanda
  namespace: flowforge
spec:
  selector:
    app: redpanda
  ports:
    - port: 29092
      targetPort: kafka-internal
      name: kafka-internal
    - port: 9092
      targetPort: kafka-external
      name: kafka-external
    - port: 9644
      targetPort: admin
      name: admin
---
# Redpanda Console
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redpanda-console
  namespace: flowforge
spec:
  replicas: 1
  selector:
    matchLabels:
      app: redpanda-console
  template:
    metadata:
      labels:
        app: redpanda-console
    spec:
      containers:
        - name: console
          image: redpandadata/console:latest
          ports:
            - containerPort: 8080
          env:
            - name: KAFKA_BROKERS
              value: "redpanda.flowforge.svc.cluster.local:29092"
          resources:
            requests:
              memory: "128Mi"
              cpu: "100m"
            limits:
              memory: "256Mi"
              cpu: "500m"
---
apiVersion: v1
kind: Service
metadata:
  name: redpanda-console
  namespace: flowforge
spec:
  selector:
    app: redpanda-console
  ports:
    - port: 8180
      targetPort: 8080
```

**File: `k8s/base/infra/clickhouse.yaml`**

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: clickhouse-init
  namespace: flowforge
data:
  000_init.sql: |
    CREATE DATABASE IF NOT EXISTS flowforge;
    CREATE DATABASE IF NOT EXISTS metrics;
    CREATE DATABASE IF NOT EXISTS marts;

    -- Raw trades table (warm path writes here)
    CREATE TABLE IF NOT EXISTS flowforge.raw_trades (
        trade_id      String,
        event_time    DateTime64(3),
        symbol        String,
        side          Enum8('BUY'=1, 'SELL'=2),
        quantity      Decimal(18,4),
        price         Decimal(18,6),
        notional      Decimal(18,4)
    ) ENGINE = MergeTree()
    ORDER BY (symbol, event_time)
    PARTITION BY toYYYYMM(event_time);

    -- Raw quotes table
    CREATE TABLE IF NOT EXISTS flowforge.raw_quotes (
        symbol        String,
        event_time    DateTime64(3),
        bid           Decimal(18,6),
        ask           Decimal(18,6),
        bid_size      Decimal(18,4),
        ask_size      Decimal(18,4),
        mid_price     Decimal(18,6)
    ) ENGINE = MergeTree()
    ORDER BY (symbol, event_time)
    PARTITION BY toYYYYMM(event_time);

    -- VWAP 5-min windows (Bytewax writes here)
    CREATE TABLE IF NOT EXISTS metrics.vwap_5min (
        symbol        String,
        window_end    DateTime64(3),
        vwap          Decimal(18,6),
        volume        Decimal(18,4),
        trade_count   UInt32,
        spread_bps    Decimal(8,2)
    ) ENGINE = MergeTree()
    ORDER BY (symbol, window_end);

    -- Rolling volatility (Bytewax writes here)
    CREATE TABLE IF NOT EXISTS metrics.rolling_volatility (
        symbol        String,
        window_end    DateTime64(3),
        volatility_1h Decimal(18,8),
        volatility_24h Decimal(18,8),
        return_pct    Decimal(18,8)
    ) ENGINE = MergeTree()
    ORDER BY (symbol, window_end);

  001_mvs.sql: |
    -- Cool path: ClickHouse MVs auto-aggregate on insert
    -- IMPORTANT: Target tables MUST be created before their MVs.
    -- ClickHouse requires the destination table to exist when creating a MV with TO clause.

    CREATE TABLE IF NOT EXISTS metrics.hourly_rollup (
        symbol        String,
        hour          DateTime,
        open          Decimal(18,6),
        high          Decimal(18,6),
        low           Decimal(18,6),
        close         Decimal(18,6),
        vwap          Decimal(18,6),
        total_volume  Decimal(18,4),
        trade_count   UInt32
    ) ENGINE = MergeTree()
    ORDER BY (symbol, hour);

    CREATE MATERIALIZED VIEW IF NOT EXISTS metrics.hourly_rollup_mv
    TO metrics.hourly_rollup AS
    SELECT
        symbol,
        toStartOfHour(event_time) AS hour,
        argMin(price, event_time) AS open,
        max(price) AS high,
        min(price) AS low,
        argMax(price, event_time) AS close,
        sum(notional) / sum(quantity) AS vwap,
        sum(quantity) AS total_volume,
        count() AS trade_count
    FROM flowforge.raw_trades
    GROUP BY symbol, hour;

    CREATE TABLE IF NOT EXISTS metrics.daily_rollup (
        symbol        String,
        day           Date,
        open          Decimal(18,6),
        high          Decimal(18,6),
        low           Decimal(18,6),
        close         Decimal(18,6),
        vwap          Decimal(18,6),
        total_volume  Decimal(18,4),
        trade_count   UInt32
    ) ENGINE = MergeTree()
    ORDER BY (symbol, day);

    CREATE MATERIALIZED VIEW IF NOT EXISTS metrics.daily_rollup_mv
    TO metrics.daily_rollup AS
    SELECT
        symbol,
        toDate(event_time) AS day,
        argMin(price, event_time) AS open,
        max(price) AS high,
        min(price) AS low,
        argMax(price, event_time) AS close,
        sum(notional) / sum(quantity) AS vwap,
        sum(quantity) AS total_volume,
        count() AS trade_count
    FROM flowforge.raw_trades
    GROUP BY symbol, day;
---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: clickhouse
  namespace: flowforge
spec:
  serviceName: clickhouse
  replicas: 1
  selector:
    matchLabels:
      app: clickhouse
  template:
    metadata:
      labels:
        app: clickhouse
    spec:
      containers:
        - name: clickhouse
          image: clickhouse/clickhouse-server:latest
          ports:
            - containerPort: 8123
              name: http
            - containerPort: 9000
              name: native
          env:
            - name: CLICKHOUSE_DB
              value: "flowforge"
            - name: CLICKHOUSE_DEFAULT_ACCESS_MANAGEMENT
              value: "1"
          resources:
            requests:
              memory: "2Gi"
              cpu: "1000m"
            limits:
              memory: "4Gi"
              cpu: "2000m"
          readinessProbe:
            exec:
              command: ["clickhouse-client", "--query", "SELECT 1"]
            initialDelaySeconds: 10
            periodSeconds: 5
          volumeMounts:
            - name: data
              mountPath: /var/lib/clickhouse
            - name: init-scripts
              mountPath: /docker-entrypoint-initdb.d
      volumes:
        - name: init-scripts
          configMap:
            name: clickhouse-init
  volumeClaimTemplates:
    - metadata:
        name: data
      spec:
        accessModes: ["ReadWriteOnce"]
        resources:
          requests:
            storage: 10Gi
---
apiVersion: v1
kind: Service
metadata:
  name: clickhouse
  namespace: flowforge
spec:
  selector:
    app: clickhouse
  ports:
    - port: 8123
      targetPort: http
      name: http
    - port: 9000
      targetPort: native
      name: native
```

**File: `k8s/base/infra/materialize.yaml`**

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: materialize
  namespace: flowforge
spec:
  serviceName: materialize
  replicas: 1
  selector:
    matchLabels:
      app: materialize
  template:
    metadata:
      labels:
        app: materialize
    spec:
      containers:
        - name: materialize
          image: materializeinc/materialize:latest
          args: ["--workers=2", "--availability-zone=dev"]
          ports:
            - containerPort: 6875
              name: pg
            - containerPort: 6876
              name: http
          resources:
            requests:
              memory: "1Gi"
              cpu: "500m"
            limits:
              memory: "3Gi"
              cpu: "2000m"
          readinessProbe:
            tcpSocket:
              port: 6875
            initialDelaySeconds: 15
            periodSeconds: 10
          volumeMounts:
            - name: data
              mountPath: /mzdata
  volumeClaimTemplates:
    - metadata:
        name: data
      spec:
        accessModes: ["ReadWriteOnce"]
        resources:
          requests:
            storage: 5Gi
---
apiVersion: v1
kind: Service
metadata:
  name: materialize
  namespace: flowforge
spec:
  selector:
    app: materialize
  ports:
    - port: 6875
      targetPort: pg
      name: pg
    - port: 6876
      targetPort: http
      name: http
```

**File: `k8s/base/infra/redis.yaml`**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
  namespace: flowforge
spec:
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
        - name: redis
          image: redis:7-alpine
          command: ["redis-server", "--appendonly", "yes", "--maxmemory", "256mb", "--maxmemory-policy", "allkeys-lru"]
          ports:
            - containerPort: 6379
          resources:
            requests:
              memory: "128Mi"
              cpu: "100m"
            limits:
              memory: "300Mi"
              cpu: "500m"
          readinessProbe:
            exec:
              command: ["redis-cli", "ping"]
            periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: redis
  namespace: flowforge
spec:
  selector:
    app: redis
  ports:
    - port: 6379
      targetPort: 6379
```

**File: `k8s/base/infra/postgres.yaml`**

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: postgres
  namespace: flowforge
spec:
  serviceName: postgres
  replicas: 1
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
        - name: postgres
          image: postgres:16
          ports:
            - containerPort: 5432
          env:
            - name: POSTGRES_DB
              value: "flowforge"
            - name: POSTGRES_USER
              value: "flowforge"
            - name: POSTGRES_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: postgres-secret
                  key: password
          resources:
            requests:
              memory: "256Mi"
              cpu: "250m"
            limits:
              memory: "512Mi"
              cpu: "1000m"
          readinessProbe:
            exec:
              command: ["pg_isready", "-U", "flowforge"]
            periodSeconds: 5
          volumeMounts:
            - name: data
              mountPath: /var/lib/postgresql/data
            - name: init-scripts
              mountPath: /docker-entrypoint-initdb.d
      volumes:
        - name: init-scripts
          configMap:
            name: postgres-init
  volumeClaimTemplates:
    - metadata:
        name: data
      spec:
        accessModes: ["ReadWriteOnce"]
        resources:
          requests:
            storage: 5Gi
---
apiVersion: v1
kind: Secret
metadata:
  name: postgres-secret
  namespace: flowforge
type: Opaque
stringData:
  password: "dev"
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: postgres-init
  namespace: flowforge
data:
  init.sql: |
    -- Airflow database
    CREATE DATABASE airflow;
    GRANT ALL PRIVILEGES ON DATABASE airflow TO flowforge;
---
apiVersion: v1
kind: Service
metadata:
  name: postgres
  namespace: flowforge
spec:
  selector:
    app: postgres
  ports:
    - port: 5432
      targetPort: 5432
```

### Pipeline Manifests

**File: `k8s/base/pipeline/data-generator.yaml`**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: data-generator
  namespace: flowforge
spec:
  replicas: 1
  selector:
    matchLabels:
      app: data-generator
  template:
    metadata:
      labels:
        app: data-generator
    spec:
      containers:
        - name: generator
          image: flowforge-registry:5111/flowforge-generator:dev
          env:
            - name: REDPANDA_BROKERS
              value: "redpanda.flowforge.svc.cluster.local:29092"
            - name: SYMBOLS
              value: "AAPL,MSFT,GOOGL,AMZN,NVDA,TSLA,META,JPM,BAC,GS"
            - name: TRADES_PER_SECOND
              value: "10"
            - name: QUOTES_PER_SECOND
              value: "50"
          resources:
            requests:
              memory: "128Mi"
              cpu: "100m"
            limits:
              memory: "256Mi"
              cpu: "500m"
```

**File: `k8s/base/pipeline/bytewax.yaml`**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: bytewax-vwap
  namespace: flowforge
spec:
  replicas: 1
  selector:
    matchLabels:
      app: bytewax-vwap
  template:
    metadata:
      labels:
        app: bytewax-vwap
    spec:
      containers:
        - name: bytewax
          image: flowforge-registry:5111/flowforge-bytewax:dev
          command: ["python", "-m", "bytewax.run", "flows.vwap:flow"]
          env:
            - name: REDPANDA_BROKERS
              value: "redpanda.flowforge.svc.cluster.local:29092"
            - name: CLICKHOUSE_HOST
              value: "clickhouse.flowforge.svc.cluster.local"
            - name: CLICKHOUSE_PORT
              value: "8123"
            - name: REDIS_HOST
              value: "redis.flowforge.svc.cluster.local"
            - name: REDIS_PORT
              value: "6379"
          resources:
            requests:
              memory: "256Mi"
              cpu: "250m"
            limits:
              memory: "512Mi"
              cpu: "1000m"
```

**File: `k8s/base/pipeline/airflow.yaml`**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: airflow
  namespace: flowforge
spec:
  replicas: 1
  selector:
    matchLabels:
      app: airflow
  template:
    metadata:
      labels:
        app: airflow
    spec:
      containers:
        - name: airflow
          image: apache/airflow:2.8-python3.12
          ports:
            - containerPort: 8080
          env:
            - name: AIRFLOW__CORE__EXECUTOR
              value: "LocalExecutor"
            - name: AIRFLOW__DATABASE__SQL_ALCHEMY_CONN
              value: "postgresql+psycopg2://flowforge:dev@postgres.flowforge.svc.cluster.local:5432/airflow"
            - name: AIRFLOW__CORE__LOAD_EXAMPLES
              value: "false"
            - name: AIRFLOW__WEBSERVER__EXPOSE_CONFIG
              value: "true"
            - name: AIRFLOW__CORE__DAGS_FOLDER
              value: "/opt/airflow/dags"
            - name: DBT_PROFILES_DIR
              value: "/opt/airflow/dbt"
            - name: CLICKHOUSE_HOST
              value: "clickhouse.flowforge.svc.cluster.local"
          command:
            - bash
            - -c
            - |
              airflow db migrate &&
              airflow users create --username admin --password admin \
                --firstname Dev --lastname User --role Admin --email dev@local || true &&
              airflow scheduler &
              exec airflow webserver
          resources:
            requests:
              memory: "512Mi"
              cpu: "250m"
            limits:
              memory: "1536Mi"
              cpu: "2000m"
          readinessProbe:
            httpGet:
              path: /health
              port: 8080
            initialDelaySeconds: 30
            periodSeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: airflow
  namespace: flowforge
spec:
  selector:
    app: airflow
  ports:
    - port: 8280
      targetPort: 8080
```

**File: `k8s/base/pipeline/init-materialize-job.yaml`**

```yaml
# This job runs once to set up Materialize sources and views.
# It must run AFTER both Materialize and Redpanda are healthy.
# Trigger manually via Tilt or: kubectl apply -f this-file.yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: init-materialize
  namespace: flowforge
spec:
  backoffLimit: 5
  template:
    spec:
      restartPolicy: OnFailure
      initContainers:
        - name: wait-for-materialize
          image: postgres:16
          command:
            - bash
            - -c
            - |
              until pg_isready -h materialize.flowforge.svc.cluster.local -p 6875 -U materialize; do
                echo "Waiting for Materialize..."
                sleep 2
              done
        - name: wait-for-redpanda
          image: curlimages/curl:latest
          command:
            - sh
            - -c
            - |
              until curl -sf http://redpanda.flowforge.svc.cluster.local:9644/v1/cluster/health_overview | grep -q '"is_healthy":true'; do
                echo "Waiting for Redpanda..."
                sleep 2
              done
      containers:
        - name: init
          image: postgres:16
          command:
            - bash
            - -c
            - |
              set -e

              echo "=== Creating Materialize sources ==="
              psql -h materialize.flowforge.svc.cluster.local -p 6875 -U materialize <<'EOF'
              CREATE CONNECTION IF NOT EXISTS redpanda_conn TO KAFKA (
                  BROKER 'redpanda.flowforge.svc.cluster.local:29092',
                  SECURITY PROTOCOL PLAINTEXT
              );

              CREATE SOURCE IF NOT EXISTS raw_trades_source
                FROM KAFKA CONNECTION redpanda_conn (TOPIC 'raw.trades')
                FORMAT JSON
                INCLUDE TIMESTAMP;

              CREATE SOURCE IF NOT EXISTS raw_quotes_source
                FROM KAFKA CONNECTION redpanda_conn (TOPIC 'raw.quotes')
                FORMAT JSON
                INCLUDE TIMESTAMP;
              EOF

              echo "=== Creating staging views ==="
              psql -h materialize.flowforge.svc.cluster.local -p 6875 -U materialize <<'EOF'
              CREATE VIEW IF NOT EXISTS raw_trades_parsed AS
              SELECT
                  (data->>'trade_id')::TEXT AS trade_id,
                  (data->>'event_time')::TIMESTAMPTZ AS event_time,
                  (data->>'symbol')::TEXT AS symbol,
                  (data->>'side')::TEXT AS side,
                  (data->>'quantity')::NUMERIC AS quantity,
                  (data->>'price')::NUMERIC AS price,
                  (data->>'quantity')::NUMERIC * (data->>'price')::NUMERIC AS notional
              FROM raw_trades_source;

              CREATE VIEW IF NOT EXISTS raw_quotes_parsed AS
              SELECT
                  (data->>'symbol')::TEXT AS symbol,
                  (data->>'event_time')::TIMESTAMPTZ AS event_time,
                  (data->>'bid')::NUMERIC AS bid,
                  (data->>'ask')::NUMERIC AS ask,
                  (data->>'bid_size')::NUMERIC AS bid_size,
                  (data->>'ask_size')::NUMERIC AS ask_size,
                  ((data->>'bid')::NUMERIC + (data->>'ask')::NUMERIC) / 2 AS mid_price
              FROM raw_quotes_source;
              EOF

              echo "=== Creating materialized views ==="
              psql -h materialize.flowforge.svc.cluster.local -p 6875 -U materialize <<'EOF'
              CREATE MATERIALIZED VIEW IF NOT EXISTS live_positions AS
              SELECT
                  symbol,
                  SUM(CASE WHEN side = 'BUY' THEN quantity ELSE -quantity END) AS net_qty,
                  SUM(CASE WHEN side = 'BUY' THEN quantity * price ELSE -quantity * price END) AS net_notional,
                  COUNT(*) AS trade_count,
                  MAX(event_time) AS last_update
              FROM raw_trades_parsed
              GROUP BY symbol;

              CREATE MATERIALIZED VIEW IF NOT EXISTS live_quotes AS
              SELECT DISTINCT ON (symbol)
                  symbol,
                  bid,
                  ask,
                  mid_price,
                  bid_size,
                  ask_size,
                  event_time AS last_update
              FROM raw_quotes_parsed
              ORDER BY symbol, event_time DESC;

              CREATE MATERIALIZED VIEW IF NOT EXISTS live_pnl AS
              SELECT
                  p.symbol,
                  p.net_qty,
                  p.net_notional,
                  q.mid_price,
                  (p.net_qty * q.mid_price) - p.net_notional AS unrealized_pnl,
                  GREATEST(p.last_update, q.last_update) AS as_of
              FROM live_positions p
              JOIN live_quotes q ON p.symbol = q.symbol;
              EOF

              echo "=== Materialize initialization complete ==="
```

### Application Manifests

**File: `k8s/base/app/backend.yaml`**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: backend
  namespace: flowforge
spec:
  replicas: 1
  selector:
    matchLabels:
      app: backend
  template:
    metadata:
      labels:
        app: backend
    spec:
      containers:
        - name: backend
          image: flowforge-registry:5111/flowforge-backend:dev
          ports:
            - containerPort: 8000
          envFrom:
            - configMapRef:
                name: backend-config
          resources:
            requests:
              memory: "256Mi"
              cpu: "250m"
            limits:
              memory: "512Mi"
              cpu: "1000m"
          readinessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 10
          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 15
            periodSeconds: 20
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: backend-config
  namespace: flowforge
data:
  APP_ENV: "development"
  CLICKHOUSE_HOST: "clickhouse.flowforge.svc.cluster.local"
  CLICKHOUSE_PORT: "8123"
  MATERIALIZE_HOST: "materialize.flowforge.svc.cluster.local"
  MATERIALIZE_PORT: "6875"
  REDIS_URL: "redis://redis.flowforge.svc.cluster.local:6379"
  DATABASE_URL: "postgresql+asyncpg://flowforge:dev@postgres.flowforge.svc.cluster.local:5432/flowforge"
  REDPANDA_BROKERS: "redpanda.flowforge.svc.cluster.local:29092"
  CORS_ORIGINS: '["http://localhost:5173"]'
---
apiVersion: v1
kind: Service
metadata:
  name: backend
  namespace: flowforge
spec:
  selector:
    app: backend
  ports:
    - port: 8000
      targetPort: 8000
```

**File: `k8s/base/app/frontend.yaml`**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: frontend
  namespace: flowforge
spec:
  replicas: 1
  selector:
    matchLabels:
      app: frontend
  template:
    metadata:
      labels:
        app: frontend
    spec:
      containers:
        - name: frontend
          image: flowforge-registry:5111/flowforge-frontend:dev
          ports:
            - containerPort: 5173
          env:
            - name: VITE_API_URL
              value: "http://localhost:8000"
            - name: VITE_WS_URL
              value: "ws://localhost:8000"
          resources:
            requests:
              memory: "128Mi"
              cpu: "100m"
            limits:
              memory: "512Mi"
              cpu: "1000m"
---
apiVersion: v1
kind: Service
metadata:
  name: frontend
  namespace: flowforge
spec:
  selector:
    app: frontend
  ports:
    - port: 5173
      targetPort: 5173
```

### Dev Overlay

**File: `k8s/overlays/dev/kustomization.yaml`**

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: flowforge

resources:
  - ../../base

patches:
  - path: resource-limits.yaml
```

**File: `k8s/overlays/dev/resource-limits.yaml`**

```yaml
# Reduce resource requests for local development
apiVersion: apps/v1
kind: Deployment
metadata:
  name: backend
  namespace: flowforge
spec:
  template:
    spec:
      containers:
        - name: backend
          resources:
            requests:
              memory: "128Mi"
              cpu: "100m"
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: frontend
  namespace: flowforge
spec:
  template:
    spec:
      containers:
        - name: frontend
          resources:
            requests:
              memory: "64Mi"
              cpu: "50m"
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: data-generator
  namespace: flowforge
spec:
  template:
    spec:
      containers:
        - name: generator
          resources:
            requests:
              memory: "64Mi"
              cpu: "50m"
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: bytewax-vwap
  namespace: flowforge
spec:
  template:
    spec:
      containers:
        - name: bytewax
          resources:
            requests:
              memory: "128Mi"
              cpu: "100m"
```

---

## 5. Tiltfile — Dev Loop Orchestration

**File: `Tiltfile`**

```python
# FlowForge Development Orchestration
# Run: tilt up
# UI:  http://localhost:10350

k8s_namespace('flowforge')

# Apply manifests via kustomize
k8s_yaml(kustomize('k8s/overlays/dev'))

# ─── Infrastructure (public images, no builds) ─────────────────────
k8s_resource('redpanda',
  labels=['infra'],
  port_forwards=['9092:9092', '9644:9644'])

k8s_resource('redpanda-console',
  labels=['infra'],
  port_forwards=['8180:8080'],
  resource_deps=['redpanda'])

k8s_resource('clickhouse',
  labels=['infra'],
  port_forwards=['8123:8123', '9000:9000'])

k8s_resource('materialize',
  labels=['infra'],
  port_forwards=['6875:6875'],
  resource_deps=['redpanda'])

k8s_resource('redis',
  labels=['infra'],
  port_forwards=['6379:6379'])

k8s_resource('postgres',
  labels=['infra'],
  port_forwards=['5432:5432'])

# ─── Backend (live sync, no image rebuild on code change) ──────────
docker_build(
  'flowforge-registry:5111/flowforge-backend',
  context='.',
  dockerfile='backend/Dockerfile',
  live_update=[
    sync('backend/app/', '/app/app/'),
    run('pip install -r /app/requirements.txt',
        trigger=['backend/requirements.txt']),
  ],
)

k8s_resource('backend',
  labels=['app'],
  port_forwards=['8000:8000'],
  resource_deps=['postgres', 'clickhouse', 'redis', 'materialize'])

# ─── Frontend (live sync, Vite HMR handles reload) ────────────────
docker_build(
  'flowforge-registry:5111/flowforge-frontend',
  context='.',
  dockerfile='frontend/Dockerfile',
  live_update=[
    sync('frontend/src/', '/app/src/'),
    sync('frontend/public/', '/app/public/'),
    sync('frontend/index.html', '/app/index.html'),
    run('npm install', trigger=['frontend/package.json']),
  ],
)

k8s_resource('frontend',
  labels=['app'],
  port_forwards=['5173:5173'])

# ─── Data Generator ───────────────────────────────────────────────
docker_build(
  'flowforge-registry:5111/flowforge-generator',
  context='pipeline/generator/',
  dockerfile='pipeline/generator/Dockerfile',
  live_update=[
    sync('pipeline/generator/', '/app/'),
  ],
)

k8s_resource('data-generator',
  labels=['pipeline'],
  resource_deps=['redpanda'])

# ─── Bytewax ─────────────────────────────────────────────────────
docker_build(
  'flowforge-registry:5111/flowforge-bytewax',
  context='pipeline/bytewax/',
  dockerfile='pipeline/bytewax/Dockerfile',
  live_update=[
    sync('pipeline/bytewax/flows/', '/app/flows/'),
  ],
)

k8s_resource('bytewax-vwap',
  labels=['pipeline'],
  resource_deps=['redpanda', 'clickhouse', 'redis'])

# ─── Airflow ─────────────────────────────────────────────────────
k8s_resource('airflow',
  labels=['pipeline'],
  port_forwards=['8280:8080'],
  resource_deps=['postgres', 'clickhouse'])

# ─── One-Off Jobs (manual trigger only) ──────────────────────────
local_resource(
  'init-materialize',
  cmd='kubectl create -f k8s/base/pipeline/init-materialize-job.yaml --namespace flowforge 2>/dev/null || kubectl replace --force -f k8s/base/pipeline/init-materialize-job.yaml --namespace flowforge',
  labels=['jobs'],
  auto_init=False,
  resource_deps=['materialize', 'redpanda'])

local_resource(
  'seed-historical',
  cmd='kubectl exec deploy/backend -n flowforge -- python /workspace/scripts/seed_historical.py',
  labels=['jobs'],
  auto_init=False,
  resource_deps=['backend', 'clickhouse', 'redis'])

local_resource(
  'dbt-run',
  cmd='kubectl exec deploy/airflow -n flowforge -- dbt run --project-dir /opt/airflow/dbt --profiles-dir /opt/airflow/dbt',
  labels=['jobs'],
  auto_init=False,
  resource_deps=['airflow', 'clickhouse'])

local_resource(
  'health-check',
  cmd='kubectl exec deploy/backend -n flowforge -- bash /workspace/scripts/check-connectivity.sh',
  labels=['jobs'],
  auto_init=False)
```

---

## 6. Dockerfiles

### Backend Dockerfile

**File: `backend/Dockerfile`**

```dockerfile
FROM python:3.12-slim AS base

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY backend/app/ /app/app/
COPY backend/alembic.ini /app/
COPY backend/alembic/ /app/alembic/

# For dev: mount scripts from workspace
# For prod: COPY scripts separately

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

### Frontend Dockerfile

**File: `frontend/Dockerfile`**

```dockerfile
FROM node:22-slim AS base

WORKDIR /app

# Dependencies
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install

# Application code
COPY frontend/ .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
```

### Data Generator Dockerfile

**File: `pipeline/generator/Dockerfile`**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "generator.py"]
```

### Bytewax Dockerfile

**File: `pipeline/bytewax/Dockerfile`**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "-m", "bytewax.run", "flows.vwap:flow"]
```

---

## 7. Data Pipeline — Four Temperature Lanes

The pipeline exists to populate the serving layer. FlowForge reads from the serving layer. The pipeline and FlowForge share a repo but are architecturally independent.

### Temperature Model

```
Lane    Latency     Technology              Output Destination
────    ────────    ──────────              ──────────────────
HOT     < 100ms     Redpanda → Materialize  Materialize views + Redis
WARM    seconds     Redpanda → Bytewax      ClickHouse base tables + Redis
COOL    minutes     ClickHouse MVs          ClickHouse rollup tables
COLD    hours       Airflow → dbt           ClickHouse mart tables
```

### Redpanda Topics

The data generator publishes to these topics:

```
raw.trades   — { trade_id, event_time, symbol, side, quantity, price }
raw.quotes   — { symbol, event_time, bid, ask, bid_size, ask_size }
raw.orders   — { order_id, event_time, symbol, side, quantity, price, status }
```

All messages are JSON. Schema enforcement happens at the consumer level, not at Redpanda.

### HOT Path: Materialize

Materialize creates sources from Redpanda topics and materializes SQL views. The views update continuously and are queryable via PG wire protocol. See the init-materialize-job.yaml above for exact SQL.

The FlowForge query router queries Materialize for:
- `live_positions` — current net position per symbol
- `live_quotes` — latest bid/ask per symbol
- `live_pnl` — unrealized P&L per symbol

### WARM Path: Bytewax

Bytewax reads from Redpanda topics, performs windowed computations, and writes results to ClickHouse and Redis.

**File: `pipeline/bytewax/requirements.txt`**

```
bytewax>=0.19
confluent-kafka>=2.3
clickhouse-connect>=0.7
redis>=5.0
orjson>=3.9
```

**File: `pipeline/bytewax/flows/vwap.py`**

```python
"""
5-minute VWAP window calculation.
Reads from raw.trades topic, computes VWAP per symbol per 5-min window,
writes results to ClickHouse metrics.vwap_5min and Redis latest state.
"""
import os
import json
from datetime import timedelta, datetime, timezone

import bytewax.operators as op
from bytewax.dataflow import Dataflow
from bytewax.connectors.kafka import KafkaSource
from bytewax.operators.windowing import TumblingWindower, EventClock, WindowMetadata

import clickhouse_connect
import redis

REDPANDA_BROKERS = os.environ.get("REDPANDA_BROKERS", "redpanda:29092").split(",")
CLICKHOUSE_HOST = os.environ.get("CLICKHOUSE_HOST", "clickhouse")
CLICKHOUSE_PORT = int(os.environ.get("CLICKHOUSE_PORT", "8123"))
REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))

# Clients
ch_client = clickhouse_connect.get_client(host=CLICKHOUSE_HOST, port=CLICKHOUSE_PORT)
r_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)


def parse_trade(msg):
    """Parse raw JSON trade message. Key by symbol."""
    data = json.loads(msg.value)
    return (data["symbol"], {
        "event_time": datetime.fromisoformat(data["event_time"]),
        "price": float(data["price"]),
        "quantity": float(data["quantity"]),
        "notional": float(data["price"]) * float(data["quantity"]),
    })


def extract_event_time(trade):
    """Extract event time for windowing."""
    return trade["event_time"]


class VWAPAccumulator:
    """Accumulates trades within a window to compute VWAP."""
    def __init__(self):
        self.total_notional = 0.0
        self.total_volume = 0.0
        self.trade_count = 0
        self.high = float("-inf")
        self.low = float("inf")

    def add(self, trade):
        self.total_notional += trade["notional"]
        self.total_volume += trade["quantity"]
        self.trade_count += 1
        self.high = max(self.high, trade["price"])
        self.low = min(self.low, trade["price"])
        return self

    @property
    def vwap(self):
        if self.total_volume == 0:
            return 0.0
        return self.total_notional / self.total_volume

    @property
    def spread_bps(self):
        if self.low == 0:
            return 0.0
        return ((self.high - self.low) / self.low) * 10000


def accumulate(acc, trade):
    if acc is None:
        acc = VWAPAccumulator()
    return acc.add(trade)


def emit_vwap(symbol_window):
    """Write VWAP result to ClickHouse and Redis."""
    (symbol, window_meta), acc = symbol_window
    window_end = window_meta.close_time

    # Write to ClickHouse
    ch_client.insert(
        "metrics.vwap_5min",
        [[symbol, window_end, acc.vwap, acc.total_volume, acc.trade_count, acc.spread_bps]],
        column_names=["symbol", "window_end", "vwap", "volume", "trade_count", "spread_bps"],
    )

    # Write latest to Redis
    r_client.hset(f"latest:vwap:{symbol}", mapping={
        "vwap": str(acc.vwap),
        "volume": str(acc.total_volume),
        "trade_count": str(acc.trade_count),
        "spread_bps": str(acc.spread_bps),
        "window_end": window_end.isoformat(),
    })

    return (symbol, acc.vwap)


# Build the dataflow
flow = Dataflow("vwap_5min")

source = KafkaSource(
    brokers=REDPANDA_BROKERS,
    topics=["raw.trades"],
    starting_offset="end",
)

stream = op.input("trades_in", flow, source)
keyed = op.map("parse", stream, parse_trade)

clock = EventClock(extract_event_time, wait_for_system_duration=timedelta(seconds=10))
windower = TumblingWindower(length=timedelta(minutes=5), align_to=datetime(2024, 1, 1, tzinfo=timezone.utc))

windowed = op.window.fold_window("vwap_window", keyed, clock, windower, lambda: None, accumulate)
op.map("emit", windowed, emit_vwap)
```

### COOL Path: ClickHouse Materialized Views

Defined in the ClickHouse init ConfigMap (see clickhouse.yaml above). These auto-trigger on every INSERT to `flowforge.raw_trades`:
- `metrics.hourly_rollup` — OHLCV per symbol per hour
- `metrics.daily_rollup` — OHLCV per symbol per day

### COLD Path: dbt + Airflow

**File: `pipeline/dbt/dbt_project.yml`**

```yaml
name: flowforge
version: '1.0.0'
config-version: 2
profile: flowforge

model-paths: ["models"]
seed-paths: ["seeds"]
test-paths: ["tests"]
```

**File: `pipeline/dbt/profiles.yml`**

```yaml
flowforge:
  target: dev
  outputs:
    dev:
      type: clickhouse
      host: "{{ env_var('CLICKHOUSE_HOST', 'clickhouse') }}"
      port: 8123
      user: default
      password: ""
      schema: marts
      secure: false
```

**File: `pipeline/dbt/models/staging/stg_trades.sql`**

```sql
{{ config(materialized='view') }}

SELECT
    trade_id,
    event_time,
    symbol,
    side,
    quantity,
    price,
    quantity * price AS notional
FROM flowforge.raw_trades
```

**File: `pipeline/dbt/models/staging/stg_instruments.sql`**

```sql
{{ config(materialized='table') }}

SELECT
    symbol,
    name,
    sector,
    exchange,
    currency,
    lot_size
FROM {{ ref('instruments') }}
```

**File: `pipeline/dbt/models/intermediate/int_trades_enriched.sql`**

```sql
{{ config(materialized='table') }}

SELECT
    t.trade_id,
    t.event_time,
    t.symbol,
    t.side,
    t.quantity,
    t.price,
    t.notional,
    i.sector,
    i.exchange,
    i.currency,
    i.name AS instrument_name
FROM {{ ref('stg_trades') }} t
LEFT JOIN {{ ref('stg_instruments') }} i ON t.symbol = i.symbol
```

**File: `pipeline/dbt/models/marts/fct_trades.sql`**

```sql
{{ config(materialized='table', order_by='(symbol, event_time)') }}

SELECT
    trade_id,
    event_time,
    symbol,
    instrument_name,
    sector,
    exchange,
    currency,
    side,
    quantity,
    price,
    notional,
    toDate(event_time) AS trade_date,
    toHour(event_time) AS trade_hour
FROM {{ ref('int_trades_enriched') }}
```

**File: `pipeline/dbt/models/marts/dim_instruments.sql`**

```sql
{{ config(materialized='table') }}

SELECT
    symbol,
    name,
    sector,
    exchange,
    currency,
    lot_size
FROM {{ ref('stg_instruments') }}
```

**File: `pipeline/dbt/models/marts/rpt_daily_pnl.sql`**

```sql
{{ config(materialized='table', order_by='(symbol, trade_date)') }}

SELECT
    symbol,
    toDate(event_time) AS trade_date,
    SUM(CASE WHEN side = 'BUY' THEN -notional ELSE notional END) AS realized_pnl,
    SUM(quantity) AS total_volume,
    COUNT(*) AS trade_count,
    AVG(price) AS avg_price
FROM {{ ref('fct_trades') }}
GROUP BY symbol, trade_date
```

**File: `pipeline/dbt/seeds/instruments.csv`**

```csv
symbol,name,sector,exchange,currency,lot_size
AAPL,Apple Inc,Technology,NASDAQ,USD,1
MSFT,Microsoft Corp,Technology,NASDAQ,USD,1
GOOGL,Alphabet Inc,Technology,NASDAQ,USD,1
AMZN,Amazon.com Inc,Consumer Discretionary,NASDAQ,USD,1
NVDA,NVIDIA Corp,Technology,NASDAQ,USD,1
TSLA,Tesla Inc,Consumer Discretionary,NASDAQ,USD,1
META,Meta Platforms Inc,Communication Services,NASDAQ,USD,1
JPM,JPMorgan Chase,Financials,NYSE,USD,1
BAC,Bank of America,Financials,NYSE,USD,1
GS,Goldman Sachs,Financials,NYSE,USD,1
```

**File: `pipeline/airflow/dags/dbt_cold_path.py`**

```python
"""
DAG that runs dbt models on a schedule.
In dev: every 5 minutes (simulates daily batch without waiting 24h).
In prod: daily at 6 AM UTC.
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator

default_args = {
    "owner": "flowforge",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=1),
}

with DAG(
    dag_id="dbt_cold_path",
    default_args=default_args,
    description="Run dbt models to produce enriched marts",
    schedule_interval="*/5 * * * *",  # Every 5 min in dev. Change to "0 6 * * *" in prod.
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["dbt", "cold-path"],
) as dag:

    dbt_seed = BashOperator(
        task_id="dbt_seed",
        bash_command="cd /opt/airflow/dbt && dbt seed --profiles-dir .",
    )

    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command="cd /opt/airflow/dbt && dbt run --profiles-dir .",
    )

    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command="cd /opt/airflow/dbt && dbt test --profiles-dir .",
    )

    dbt_seed >> dbt_run >> dbt_test
```

---

## 8. Application Layer — Canvas + BI + Embed

### Routing

```
/canvas                     → Canvas.tsx (React Flow workspace)
/canvas/:workflow_id        → Canvas.tsx (load specific workflow)
/dashboards                 → Dashboard list
/dashboards/:dashboard_id   → Dashboard.tsx (widget grid)
/embed/:widget_id           → EmbedView.tsx (chromeless single widget)
```

Canvas and Dashboards use Keycloak OIDC authentication.
Embed uses API key authentication (scoped to specific widgets, stateless).

### Widget Lifecycle

1. User builds workflow on canvas: Source → Filter → Sort → Table View
2. User pins the Table View output node to a dashboard
3. System creates a Widget record: `{ workflow_id, output_node_id, dashboard_id, position, size }`
4. Dashboard renders the widget by executing the workflow up to the pinned output node
5. Widget auto-refreshes on interval or via WebSocket for live data

Widgets are NOT separate objects from canvas outputs. They are references. If the workflow changes, the widget changes. No sync problem.

### Chart Component Sharing

All chart components live in `frontend/src/shared/components/charts/`. They render identically in canvas preview, dashboard widgets, and embed mode. The only difference is the container size. NEVER duplicate chart components into feature folders.

---

## 9. Multi-Tenancy

Every table in PostgreSQL has a `tenant_id` column. Every query filters on it. No exceptions. This is implemented in Phase 0, not later.

### SQLAlchemy Base Model

**In `backend/app/models/base.py`:**

```python
from sqlalchemy import String, Column
from sqlalchemy.orm import DeclarativeBase, declared_attr


class Base(DeclarativeBase):
    pass


class TenantMixin:
    """Mixin that adds tenant_id to every model. Every model MUST use this."""

    @declared_attr
    def tenant_id(cls) -> Column:
        return Column(String(64), nullable=False, index=True)
```

### Every model uses TenantMixin:

```python
class Workflow(TenantMixin, Base):
    __tablename__ = "workflows"
    id = Column(String(36), primary_key=True)
    tenant_id: str  # From TenantMixin — non-nullable, indexed
    name = Column(String(255), nullable=False)
    graph_json = Column(Text, nullable=False)  # React Flow serialized graph
    created_by = Column(String(255), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
```

### Tenant Extraction Middleware

```python
# backend/app/core/tenant.py
from fastapi import Depends
from app.core.auth import get_current_user, User


async def get_tenant(user: User = Depends(get_current_user)) -> str:
    """Extract tenant_id from JWT claims. Used as a dependency on every route."""
    return user.tenant_id
```

### Every Route Uses Tenant Scoping

```python
@router.get("/workflows")
async def list_workflows(
    tenant_id: str = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Workflow).where(Workflow.tenant_id == tenant_id)
    )
    return result.scalars().all()
```

### Serving-Layer Tenant Isolation

The serving-layer tables (ClickHouse, Materialize, Redis) contain **market data**, not tenant-owned data. Trades, quotes, and metrics are shared financial data — AAPL trades belong to the market, not to a specific tenant. These tables do NOT have a `tenant_id` column, and adding one would be incorrect.

Tenant isolation in the serving layer is enforced via **symbol-based access control**:

1. **Schema registry is tenant-scoped.** The `SchemaRegistry` caches a per-tenant catalog of allowed tables and symbols. Different tenants may see different subsets of the serving layer (e.g., Firm A sees equities only, Firm B sees equities + FX).

2. **Allowed-symbols ACL.** Each tenant has an `allowed_symbols` list (stored in PostgreSQL, managed by admin). When the workflow compiler generates SQL, it injects `WHERE symbol IN (:allowed_symbols)` for any query against market data tables. This is applied at the compiler level, not at the route level.

3. **DataSource node enforces catalog.** The DataSource node's table picker only shows tables from the tenant's catalog. Users cannot reference tables outside their tenant's allowed set.

4. **PostgreSQL data IS tenant-scoped.** App metadata (workflows, dashboards, widgets, API keys) uses `tenant_id` columns with strict filtering. This is a different isolation model than the serving layer.

5. **Single-tenant launch is fine.** If you have one customer at launch, there is one Keycloak realm, one tenant, and one allowed-symbols list (all symbols). The code doesn't know or care. When customer #2 signs, add their tenant + symbol ACL. No migration needed.

---

## 10. Authentication — Keycloak

### Architecture

- One Keycloak realm per customer (firm-alpha, firm-beta, etc.)
- Each realm federates with the customer's identity provider (Azure AD, Okta via SAML/OIDC)
- Customer IT controls user provisioning — FlowForge never stores passwords
- Roles: admin, analyst, viewer (mapped from customer's AD groups)

### Three Auth Flows

| Flow | Used By | Mechanism |
|------|---------|-----------|
| Browser OIDC | Canvas, Dashboards | Standard Keycloak login → JWT in cookie/header |
| API Key | Embed mode | `X-API-Key` header, scoped to specific widgets, stateless |
| Client Credentials | Service-to-service (future) | OAuth2 client credentials flow |

### JWT Structure

The JWT contains a `tenant_id` claim (the realm name or a mapped attribute). Every backend route extracts this and uses it to scope queries.

```python
# backend/app/core/auth.py
from dataclasses import dataclass
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from app.core.config import settings

security = HTTPBearer()


@dataclass
class User:
    sub: str
    tenant_id: str
    email: str
    roles: list[str]


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> User:
    """Validate JWT from Keycloak and extract user info."""
    token = credentials.credentials
    try:
        # In production, fetch JWKS from Keycloak and validate properly.
        # For dev, decode with the realm's public key.
        payload = jwt.decode(
            token,
            settings.KEYCLOAK_PUBLIC_KEY,
            algorithms=["RS256"],
            audience=settings.KEYCLOAK_CLIENT_ID,
        )
        return User(
            sub=payload["sub"],
            tenant_id=payload.get("tenant_id", payload.get("azp", "default")),
            email=payload.get("email", ""),
            roles=payload.get("realm_access", {}).get("roles", []),
        )
    except jwt.PyJWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e}",
        )
```

### Embed Auth (API Key)

API keys are **never stored in plaintext**. On creation, the raw key (`sk_live_...`) is returned once; only the SHA-256 hash is persisted. On validation, the incoming key is hashed and looked up by hash. SHA-256 is appropriate here (not bcrypt/argon2) because API keys have high entropy (128-bit UUIDv4) — they are not user-chosen passwords.

```python
# backend/app/core/auth.py (continued)
import hashlib

async def get_embed_auth(
    api_key: str = Header(..., alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
) -> tuple[str, list[str]]:
    """Validate API key for embed mode. Returns (tenant_id, scoped_widget_ids)."""
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    result = await db.execute(
        select(APIKey).where(
            APIKey.key_hash == key_hash,
            APIKey.revoked_at.is_(None),
        )
    )
    key_record = result.scalar_one_or_none()
    if not key_record:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return key_record.tenant_id, key_record.scoped_widget_ids
```

### Dev Mode

For development without Keycloak running, the backend accepts a `X-Dev-Tenant` header that sets tenant_id directly. This is controlled by an environment variable and MUST be disabled in production:

```python
# In auth.py, checked before JWT validation:
if settings.APP_ENV == "development" and "X-Dev-Tenant" in request.headers:
    return User(
        sub="dev-user",
        tenant_id=request.headers["X-Dev-Tenant"],
        email="dev@flowforge.local",
        roles=["admin"],
    )
```

### Keycloak Deployment Phasing

Keycloak is part of the architecture but is NOT deployed in early phases. The rollout is:

| Phase | Auth Mechanism | Notes |
|-------|---------------|-------|
| Phase 0-2 | `X-Dev-Tenant` header bypass | No Keycloak. Backend accepts tenant from header when `APP_ENV=development` |
| Phase 3 | `X-Dev-Tenant` header bypass | Dashboard development continues without OIDC |
| Phase 4 | Keycloak StatefulSet in `k8s/base/infra/keycloak.yaml` | Realm bootstrap for dev, OIDC integration for Canvas + Dashboards, API key auth for Embed |
| Phase 5 | Full RBAC via Keycloak roles | Admin/analyst/viewer enforcement, realm-per-customer |

A minimal Keycloak deployment spec (`k8s/base/infra/keycloak.yaml`) will be added in Phase 4, including:
- Keycloak StatefulSet with PostgreSQL backend (separate from app DB)
- Dev realm export in `k8s/base/infra/keycloak-realm.json` for reproducible setup
- Protocol mapper for `tenant_id` custom JWT claim
- At least two test tenants with sample users for cross-tenant isolation testing

---

## 11. Schema Engine

The schema engine discovers what tables/columns exist in the serving layer and propagates column types through workflow node graphs so the UI can populate dropdowns and validate connections.

### Discovery

On backend startup and periodically (every 60 seconds), the schema registry queries:

```sql
-- ClickHouse
SELECT database, table, name, type
FROM system.columns
WHERE database IN ('flowforge', 'metrics', 'marts')
ORDER BY database, table, name;

-- Materialize
SELECT
    s.name AS schema_name,
    o.name AS object_name,
    c.name AS column_name,
    c.type_oid::regtype::text AS data_type
FROM mz_columns c
JOIN mz_objects o ON c.id = o.id
JOIN mz_schemas s ON o.schema_id = s.id
WHERE s.name NOT IN ('mz_internal', 'mz_catalog', 'pg_catalog', 'information_schema');
```

Results are cached in a `SchemaRegistry` singleton:

```python
# backend/app/services/schema_registry.py
from dataclasses import dataclass

@dataclass(frozen=True)
class ColumnInfo:
    name: str
    data_type: str  # Normalized: "string", "int64", "float64", "datetime", "decimal", "boolean"
    nullable: bool = True

@dataclass(frozen=True)
class TableInfo:
    database: str       # "flowforge", "metrics", "marts", or "materialize"
    table: str
    columns: tuple[ColumnInfo, ...]
    backing_store: str  # "clickhouse", "materialize", "redis"

class SchemaRegistry:
    """Caches discovered schemas from all backing stores."""

    def __init__(self):
        self._tables: dict[str, TableInfo] = {}  # key: "database.table"

    async def refresh(self):
        """Query all backing stores and rebuild cache."""
        ...

    def get_table(self, database: str, table: str) -> TableInfo | None:
        return self._tables.get(f"{database}.{table}")

    def list_tables(self) -> list[TableInfo]:
        return list(self._tables.values())

    def get_columns(self, database: str, table: str) -> list[ColumnInfo]:
        info = self.get_table(database, table)
        return list(info.columns) if info else []
```

### Propagation

Schema propagation determines what columns are available at each node in the graph. It runs in TWO places:

1. **Client-side (TypeScript)** — Instant feedback as users build workflows. Runs synchronously in the browser. Populates config panel dropdowns.
2. **Server-side (Python)** — Authoritative validation before execution. If client and server disagree, server wins.

Each node type declares how it transforms its input schema:

```python
# backend/app/services/schema_engine.py

class SchemaTransform(Protocol):
    def propagate(self, input_schema: list[ColumnInfo], config: dict) -> list[ColumnInfo]:
        """Given input columns and node config, return output columns."""
        ...

# Example: Filter node passes all columns through unchanged
class FilterSchemaTransform:
    def propagate(self, input_schema, config):
        return input_schema  # Filter doesn't change schema, only row count

# Example: Select node returns only chosen columns
class SelectSchemaTransform:
    def propagate(self, input_schema, config):
        selected = set(config.get("columns", []))
        return [col for col in input_schema if col.name in selected]

# Example: Group By node returns group keys + aggregated columns
class GroupBySchemaTransform:
    def propagate(self, input_schema, config):
        group_cols = config.get("group_by", [])
        agg_cols = config.get("aggregations", [])
        result = [col for col in input_schema if col.name in group_cols]
        for agg in agg_cols:
            result.append(ColumnInfo(
                name=f"{agg['function']}_{agg['column']}",
                data_type="float64" if agg["function"] in ("avg", "sum") else "int64",
            ))
        return result
```

The TypeScript version mirrors this exactly in `frontend/src/shared/schema/propagation.ts`.

---

## 12. Query Router

The query router decides which backing store handles each query based on data freshness requirements.

```python
# backend/app/services/query_router.py
from enum import Enum

class BackingStore(Enum):
    CLICKHOUSE = "clickhouse"
    MATERIALIZE = "materialize"
    REDIS = "redis"

class QueryRouter:
    def __init__(self, schema_registry, ch_client, mz_client, redis_client):
        self.schema_registry = schema_registry
        self.ch = ch_client
        self.mz = mz_client
        self.redis = redis_client

    def resolve_store(self, database: str, table: str) -> BackingStore:
        """Determine which backing store owns this table."""
        info = self.schema_registry.get_table(database, table)
        if info is None:
            raise ValueError(f"Unknown table: {database}.{table}")
        return BackingStore(info.backing_store)

    async def execute_query(self, sql: str, store: BackingStore, settings: dict | None = None):
        """Execute compiled SQL against the resolved backing store."""
        if store == BackingStore.CLICKHOUSE:
            return await self._execute_clickhouse(sql, settings)
        elif store == BackingStore.MATERIALIZE:
            return await self._execute_materialize(sql)
        elif store == BackingStore.REDIS:
            raise ValueError("Redis queries use key-value API, not SQL")

    async def execute_redis_lookup(self, key_pattern: str) -> dict:
        """Point lookup in Redis."""
        return await self.redis.hgetall(key_pattern)

    async def _execute_clickhouse(self, sql: str, settings: dict | None = None):
        """Execute against ClickHouse with optional settings (timeouts, memory limits)."""
        default_settings = {
            "max_execution_time": 30,
            "max_memory_usage": 1_000_000_000,  # 1GB
        }
        if settings:
            default_settings.update(settings)
        return self.ch.query(sql, settings=default_settings)

    async def _execute_materialize(self, sql: str):
        """Execute against Materialize via PG wire protocol."""
        async with self.mz.acquire() as conn:
            return await conn.fetch(sql)
```

### Routing Rules

```
Data Source Table                    Backing Store       Reason
────────────────                    ─────────────       ──────
materialize.live_positions          Materialize         Live data, < 10ms
materialize.live_quotes             Materialize         Live data, < 10ms
materialize.live_pnl                Materialize         Live data, < 10ms
flowforge.raw_trades                ClickHouse          Historical, ad-hoc analytical
flowforge.raw_quotes                ClickHouse          Historical, ad-hoc analytical
metrics.vwap_5min                   ClickHouse          Windowed metrics
metrics.rolling_volatility          ClickHouse          Windowed metrics
metrics.hourly_rollup               ClickHouse          Pre-aggregated
metrics.daily_rollup                ClickHouse          Pre-aggregated
marts.fct_trades                    ClickHouse          Enriched mart
marts.dim_instruments               ClickHouse          Reference data
marts.rpt_daily_pnl                 ClickHouse          Reporting
latest:vwap:*                       Redis               Point lookup, < 1ms
latest:position:*                   Redis               Point lookup, < 1ms
```

---

## 13. Workflow Compiler

The compiler takes a React Flow graph (nodes + edges), topologically sorts it, and produces a single SQL query.

### Compilation Steps

1. Receive full graph JSON + target_node_id
2. Walk backward from target node through edges to find the relevant subgraph
3. Topologically sort the subgraph
4. For each node, generate a SQL fragment based on node type + config
5. Merge adjacent nodes into nested subqueries (query merging — critical for performance)
6. Determine backing store from the source node's table
7. Return compiled SQL + backing store identifier

### Node-to-SQL Compilation

```python
# backend/app/services/workflow_compiler.py

class WorkflowCompiler:
    def compile_subgraph(self, graph: dict, target_node_id: str) -> tuple[str, BackingStore]:
        """
        Compile the subgraph ending at target_node_id into a single SQL string.
        Returns (sql, backing_store).
        """
        subgraph = self._extract_subgraph(graph, target_node_id)
        sorted_nodes = self._topological_sort(subgraph)

        # The first node must be a DataSource — it determines the backing store
        source_node = sorted_nodes[0]
        assert source_node["type"] == "data_source"
        database = source_node["data"]["database"]
        table = source_node["data"]["table"]
        store = self.query_router.resolve_store(database, table)

        # Build SQL by wrapping each node's contribution
        sql = f"SELECT * FROM {database}.{table}"

        for node in sorted_nodes[1:]:  # Skip source, already handled
            sql = self._compile_node(node, sql)

        return sql, store

    def _compile_node(self, node: dict, inner_sql: str) -> str:
        """Wrap inner SQL with this node's transformation."""
        node_type = node["type"]
        config = node["data"]

        if node_type == "filter":
            condition = self._compile_filter_condition(config)
            return f"SELECT * FROM ({inner_sql}) AS _t WHERE {condition}"

        elif node_type == "select":
            columns = ", ".join(config["columns"])
            return f"SELECT {columns} FROM ({inner_sql}) AS _t"

        elif node_type == "sort":
            order_parts = []
            for s in config["sorts"]:
                order_parts.append(f"{s['column']} {s['direction']}")
            order_clause = ", ".join(order_parts)
            return f"SELECT * FROM ({inner_sql}) AS _t ORDER BY {order_clause}"

        elif node_type == "group_by":
            group_cols = ", ".join(config["group_by"])
            agg_parts = []
            for agg in config["aggregations"]:
                agg_parts.append(f"{agg['function']}({agg['column']}) AS {agg['function']}_{agg['column']}")
            select_cols = group_cols + ", " + ", ".join(agg_parts)
            return f"SELECT {select_cols} FROM ({inner_sql}) AS _t GROUP BY {group_cols}"

        elif node_type == "join":
            # Join requires TWO input edges — handled differently
            right_sql = self._compile_subgraph_for_join(node, config)
            join_type = config.get("join_type", "INNER")
            left_key = config["left_key"]
            right_key = config["right_key"]
            return (
                f"SELECT * FROM ({inner_sql}) AS _left "
                f"{join_type} JOIN ({right_sql}) AS _right "
                f"ON _left.{left_key} = _right.{right_key}"
            )

        elif node_type == "table_view":
            # Terminal node — add LIMIT/OFFSET for pagination
            page = config.get("page", 0)
            page_size = config.get("page_size", 50)
            offset = page * page_size
            if offset > 10000:
                raise ValueError("Offset exceeds maximum of 10,000. Add filters to narrow results.")
            return f"SELECT * FROM ({inner_sql}) AS _t LIMIT {page_size} OFFSET {offset}"

        else:
            raise ValueError(f"Unknown node type: {node_type}")

    def _compile_filter_condition(self, config: dict) -> str:
        """Compile filter config to SQL WHERE clause."""
        conditions = []
        for f in config.get("filters", []):
            col = f["column"]
            op = f["operator"]  # "=", "!=", ">", "<", ">=", "<=", "LIKE", "IN", "NOT IN", "IS NULL", "IS NOT NULL"
            value = f.get("value")

            if op in ("IS NULL", "IS NOT NULL"):
                conditions.append(f"{col} {op}")
            elif op in ("IN", "NOT IN"):
                values = ", ".join(f"'{v}'" if isinstance(v, str) else str(v) for v in value)
                conditions.append(f"{col} {op} ({values})")
            elif isinstance(value, str):
                conditions.append(f"{col} {op} '{value}'")
            else:
                conditions.append(f"{col} {op} {value}")

        logic = config.get("logic", "AND")
        return f" {logic} ".join(conditions) if conditions else "1=1"
```

### Query Merging

The compiler merges adjacent simple nodes into one query level instead of creating unnecessary nesting. A workflow like Source → Filter → Select → Sort compiles to:

```sql
SELECT col1, col2
FROM flowforge.raw_trades
WHERE price > 100
ORDER BY event_time DESC
```

NOT:

```sql
SELECT * FROM (
  SELECT * FROM (
    SELECT col1, col2 FROM (
      SELECT * FROM flowforge.raw_trades
    ) AS _t
  ) AS _t WHERE price > 100
) AS _t ORDER BY event_time DESC
```

The compiler achieves this by collecting compatible operations before generating SQL. Filter + Select + Sort can share one query level because they don't conflict.

---

## 14. Data Preview and Pagination

### Preview (Non-Terminal Nodes)

"Click a node → see first 100 rows" requires a three-layer approach:

**Layer 1 — Frontend debounce + cancellation:**
- 300ms debounce after last click
- Cancel in-flight requests when user clicks a different node
- Eliminates 60-70% of unnecessary queries

**Layer 2 — Content-addressed cache (Redis):**

```python
import hashlib, json

def compute_preview_cache_key(graph: dict, target_node_id: str) -> str:
    """Content-addressed cache key. Same subgraph + config = same key."""
    subgraph = extract_subgraph(graph, target_node_id)
    content = json.dumps(subgraph, sort_keys=True)
    return f"preview:{hashlib.sha256(content.encode()).hexdigest()}"
```

Cache hit = instant response. Cache miss = compile and execute. TTL: 5 minutes.

**Layer 3 — Query constraints (server-side safety):**

```sql
SELECT * FROM (compiled_subgraph)
LIMIT 100
SETTINGS
    max_execution_time = 3,
    max_memory_usage = 100000000,
    max_rows_to_read = 10000000
```

ClickHouse enforces these server-side. If the preview would scan a billion rows, it hits the cap and returns an error instead of hanging.

### Preview API Endpoint

```
POST /api/v1/preview
Body: {
    "graph": { ... },          // Full React Flow graph JSON
    "target_node_id": "node-3" // Which node to preview
}
Response: {
    "columns": [{"name": "symbol", "type": "string"}, ...],
    "rows": [[...], ...],      // Max 100 rows
    "row_count": 100,
    "execution_ms": 47,
    "cache_hit": true,
    "truncated": true           // true if more than 100 rows exist
}
```

### Pagination (Table View Output Nodes)

Table View is a terminal node. Users browse results with real pagination:

```
Page N: SELECT * FROM (compiled_workflow)
        ORDER BY event_time DESC
        LIMIT 50 OFFSET (N * 50)
```

Hard cap: OFFSET cannot exceed 10,000. Beyond that, the response includes a message: "Add a filter to narrow results" or "Export to CSV."

LIMIT applies AFTER GROUP BY. The compiled SQL is naturally correct — GROUP BY is in the inner query, LIMIT wraps outside.

OFFSET-based pagination (not cursor-based) is acceptable because the hard cap prevents deep-page performance issues. Cursor pagination requires a guaranteed unique sort column, which can't be assumed with arbitrary user-defined workflows.

---

## 15. Dashboard System

### Data Model

```sql
-- PostgreSQL (app metadata)
CREATE TABLE dashboards (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   VARCHAR(64) NOT NULL,
    name        VARCHAR(255) NOT NULL,
    layout_json TEXT NOT NULL,         -- Grid positions: [{widget_id, x, y, w, h}, ...]
    created_by  VARCHAR(255) NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE widgets (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       VARCHAR(64) NOT NULL,
    dashboard_id    UUID REFERENCES dashboards(id) ON DELETE CASCADE,
    workflow_id     UUID NOT NULL,
    output_node_id  VARCHAR(64) NOT NULL,   -- Which canvas node this widget renders
    widget_type     VARCHAR(50) NOT NULL,   -- "table", "bar_chart", "line_chart", etc.
    config_json     TEXT,                    -- Widget-specific config overrides
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE api_keys (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   VARCHAR(64) NOT NULL,
    key         VARCHAR(64) NOT NULL UNIQUE,
    widget_id   UUID REFERENCES widgets(id) ON DELETE CASCADE,
    is_active   BOOLEAN DEFAULT true,
    created_at  TIMESTAMPTZ DEFAULT now(),
    expires_at  TIMESTAMPTZ
);

CREATE INDEX idx_dashboards_tenant ON dashboards(tenant_id);
CREATE INDEX idx_widgets_tenant ON widgets(tenant_id);
CREATE INDEX idx_widgets_dashboard ON widgets(dashboard_id);
CREATE INDEX idx_api_keys_key ON api_keys(key);
CREATE INDEX idx_api_keys_tenant ON api_keys(tenant_id);
```

### Global Filters

Dashboards support global filters (date range, symbol filter) that propagate to all widgets. The schema registry knows which columns are temporal (DateTime types) and which are categorical (String/Enum types), so the UI can auto-populate filter options.

When a global filter is active, the dashboard re-executes each widget's workflow with the filter condition appended to the compiled SQL.

### Live Updates

For dashboards showing live data (Materialize sources), the backend uses **polling with Redis pub/sub fan-out** to push updates. Materialize's `SUBSCRIBE` is a long-lived streaming query that doesn't map cleanly to per-widget push notifications, so we use a simpler pattern:

#### Update Flow

1. **Data pipeline publishes update ticks**: When the pipeline writes new data (via Redpanda → Materialize), it also publishes a lightweight "data changed" message to a Redis pub/sub channel per symbol: `flowforge:{tenant_id}:symbol:{symbol}`
2. **Backend relays to dashboard channels**: A background listener maps symbol channels to affected dashboards (via the widget → workflow → DataSource node → symbol mapping). It publishes to `flowforge:{tenant_id}:dashboard:{dashboard_id}` with a payload indicating which widget(s) are invalidated
3. **WebSocket handler pushes to clients**: Dashboard connects via WebSocket at `ws://localhost:8000/ws/dashboard/{dashboard_id}`. The handler subscribes to the dashboard's Redis channel and forwards invalidation messages to connected clients
4. **Frontend re-fetches affected widgets only**: On receiving an invalidation message, the frontend re-fetches only the specific widget data (not the entire dashboard). TanStack Query's `invalidateQueries` handles this, keyed by `[widget_id]`

#### Stampede Prevention

- **Per-widget refresh jitter**: Frontend adds 50-200ms random jitter before re-fetching to prevent all widgets from hitting the backend simultaneously
- **Stale-while-revalidate**: TanStack Query serves cached data immediately while re-fetching in the background (`staleTime: 1000, gcTime: 30000`)
- **Server-side cache**: Preview cache (Redis, content-addressed) ensures identical queries from multiple clients hit cache, not the database
- **Debounced invalidation**: Backend coalesces rapid symbol updates into a single invalidation per dashboard per 500ms window

#### Fallback: Polling

If Redis pub/sub is unavailable or for simpler deployments, dashboards fall back to polling:
- Poll interval: 5 seconds (configurable per dashboard)
- Each poll re-fetches only widgets whose source workflow targets a Materialize or Redis backing store
- ClickHouse-backed widgets do not auto-refresh (data changes on minute/hour cadence)

---

## 16. Frontend Architecture

### Key Dependencies

```json
{
  "dependencies": {
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "react-router-dom": "^6.20.0",
    "reactflow": "^11.11.0",
    "zustand": "^4.5.0",
    "@tanstack/react-query": "^5.0.0",
    "echarts": "^5.5.0",
    "echarts-for-react": "^3.0.0",
    "keycloak-js": "^25.0.0",
    "axios": "^1.7.0"
  },
  "devDependencies": {
    "typescript": "^5.4.0",
    "vite": "^5.4.0",
    "tailwindcss": "^3.4.0",
    "@types/react": "^18.3.0",
    "vitest": "^1.6.0",
    "eslint": "^9.0.0",
    "prettier": "^3.2.0"
  }
}
```

### Canvas State (Zustand)

```typescript
// frontend/src/features/canvas/store.ts
import { create } from 'zustand';
import { Node, Edge, applyNodeChanges, applyEdgeChanges } from 'reactflow';

interface CanvasState {
  nodes: Node[];
  edges: Edge[];
  selectedNodeId: string | null;
  previewNodeId: string | null;

  // Actions
  onNodesChange: (changes: any) => void;
  onEdgesChange: (changes: any) => void;
  setSelectedNode: (id: string | null) => void;
  setPreviewNode: (id: string | null) => void;
  updateNodeData: (id: string, data: any) => void;
  addNode: (node: Node) => void;
  removeNode: (id: string) => void;
}

export const useCanvasStore = create<CanvasState>((set, get) => ({
  nodes: [],
  edges: [],
  selectedNodeId: null,
  previewNodeId: null,

  onNodesChange: (changes) =>
    set({ nodes: applyNodeChanges(changes, get().nodes) }),
  onEdgesChange: (changes) =>
    set({ edges: applyEdgeChanges(changes, get().edges) }),
  setSelectedNode: (id) => set({ selectedNodeId: id }),
  setPreviewNode: (id) => set({ previewNodeId: id }),
  updateNodeData: (id, data) =>
    set({
      nodes: get().nodes.map((n) =>
        n.id === id ? { ...n, data: { ...n.data, ...data } } : n
      ),
    }),
  addNode: (node) => set({ nodes: [...get().nodes, node] }),
  removeNode: (id) =>
    set({
      nodes: get().nodes.filter((n) => n.id !== id),
      edges: get().edges.filter((e) => e.source !== id && e.target !== id),
    }),
}));
```

### Preview Hook (with debounce + cancellation)

```typescript
// frontend/src/features/canvas/preview/usePreview.ts
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useCanvasStore } from '../store';
import { useDebouncedValue } from '../../shared/hooks/useDebouncedValue';
import axios from 'axios';

export function usePreview() {
  const { nodes, edges, previewNodeId } = useCanvasStore();
  const queryClient = useQueryClient();

  // Debounce the preview node ID by 300ms
  const debouncedNodeId = useDebouncedValue(previewNodeId, 300);

  const query = useQuery({
    queryKey: ['preview', debouncedNodeId, nodes, edges],
    queryFn: async ({ signal }) => {
      if (!debouncedNodeId) return null;
      const response = await axios.post('/api/v1/preview', {
        graph: { nodes, edges },
        target_node_id: debouncedNodeId,
      }, { signal });  // AbortController signal for cancellation
      return response.data;
    },
    enabled: !!debouncedNodeId,
    staleTime: 5 * 60 * 1000,  // 5 minutes (matches server cache TTL)
  });

  return query;
}
```

---

## 17. Backend Architecture

### Application Factory

```python
# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.database import init_db, close_db
from app.core.clickhouse import init_clickhouse, close_clickhouse
from app.core.materialize import init_materialize, close_materialize
from app.core.redis import init_redis, close_redis
from app.services.schema_registry import SchemaRegistry
from app.api.routes import health, workflows, dashboards, widgets, preview, schema, embed


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    await init_clickhouse()
    await init_materialize()
    await init_redis()

    # Initialize schema registry
    registry = SchemaRegistry()
    await registry.refresh()
    app.state.schema_registry = registry

    yield

    # Shutdown
    await close_db()
    await close_clickhouse()
    await close_materialize()
    await close_redis()


def create_app() -> FastAPI:
    app = FastAPI(
        title="FlowForge",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router, tags=["health"])
    app.include_router(workflows.router, prefix="/api/v1", tags=["workflows"])
    app.include_router(dashboards.router, prefix="/api/v1", tags=["dashboards"])
    app.include_router(widgets.router, prefix="/api/v1", tags=["widgets"])
    app.include_router(preview.router, prefix="/api/v1", tags=["preview"])
    app.include_router(schema.router, prefix="/api/v1", tags=["schema"])
    app.include_router(embed.router, prefix="/api/v1/embed", tags=["embed"])

    return app

app = create_app()
```

### Configuration

```python
# backend/app/core/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_ENV: str = "development"

    # PostgreSQL
    DATABASE_URL: str = "postgresql+asyncpg://flowforge:dev@postgres:5432/flowforge"

    # ClickHouse
    CLICKHOUSE_HOST: str = "clickhouse"
    CLICKHOUSE_PORT: int = 8123

    # Materialize
    MATERIALIZE_HOST: str = "materialize"
    MATERIALIZE_PORT: int = 6875

    # Redis
    REDIS_URL: str = "redis://redis:6379"

    # Redpanda
    REDPANDA_BROKERS: str = "redpanda:29092"

    # Auth
    KEYCLOAK_URL: str = "http://keycloak:8080"
    KEYCLOAK_REALM: str = "flowforge"
    KEYCLOAK_CLIENT_ID: str = "flowforge-app"
    KEYCLOAK_PUBLIC_KEY: str = ""

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    # Preview
    PREVIEW_CACHE_TTL: int = 300  # 5 minutes
    PREVIEW_ROW_LIMIT: int = 100
    PREVIEW_MAX_EXECUTION_TIME: int = 3  # seconds
    PREVIEW_MAX_MEMORY: int = 100_000_000  # 100MB

    # Pagination
    MAX_PAGE_OFFSET: int = 10_000
    DEFAULT_PAGE_SIZE: int = 50

    class Config:
        env_file = ".env"

settings = Settings()
```

### Requirements

**File: `backend/requirements.txt`**

```
fastapi>=0.109.0
uvicorn[standard]>=0.27.0
sqlalchemy[asyncio]>=2.0.25
asyncpg>=0.29.0
alembic>=1.13.0
pydantic>=2.6.0
pydantic-settings>=2.1.0
clickhouse-connect>=0.7.0
redis>=5.0.0
python-jose[cryptography]>=3.3.0
PyJWT>=2.8.0
orjson>=3.9.0
polars>=0.20.0
httpx>=0.27.0
websockets>=12.0
python-multipart>=0.0.6
```

---

## 18. Seed Data and Data Generator

### Data Generator

**File: `pipeline/generator/requirements.txt`**

```
confluent-kafka>=2.3.0
orjson>=3.9.0
```

**File: `pipeline/generator/generator.py`**

```python
"""
Synthetic market data generator.
Produces realistic trade and quote messages to Redpanda topics.

Behavior:
- Prices follow random walk with mean reversion
- Volume follows intraday U-shaped curve (high at open/close)
- Spreads widen on high volatility
- Configurable rate via TRADES_PER_SECOND and QUOTES_PER_SECOND env vars
"""
import os
import time
import uuid
import random
import math
from datetime import datetime, timezone
from confluent_kafka import Producer
import orjson

BROKERS = os.environ.get("REDPANDA_BROKERS", "redpanda:29092")
SYMBOLS = os.environ.get("SYMBOLS", "AAPL,MSFT,GOOGL,AMZN,NVDA,TSLA,META,JPM,BAC,GS").split(",")
TRADES_PER_SECOND = int(os.environ.get("TRADES_PER_SECOND", "10"))
QUOTES_PER_SECOND = int(os.environ.get("QUOTES_PER_SECOND", "50"))

# Base prices for each symbol (approximate real prices)
BASE_PRICES = {
    "AAPL": 185.0, "MSFT": 420.0, "GOOGL": 155.0, "AMZN": 190.0,
    "NVDA": 880.0, "TSLA": 245.0, "META": 510.0, "JPM": 195.0,
    "BAC": 35.0, "GS": 420.0,
}

# Current simulated prices (mutated by random walk)
current_prices = {s: BASE_PRICES.get(s, 100.0) for s in SYMBOLS}
# Volatility per symbol (annualized, used to scale random walk)
volatilities = {s: random.uniform(0.15, 0.45) for s in SYMBOLS}


def random_walk_price(symbol: str) -> float:
    """Apply one step of geometric Brownian motion with mean reversion."""
    price = current_prices[symbol]
    base = BASE_PRICES.get(symbol, 100.0)
    vol = volatilities[symbol]

    # Random return (scaled to per-tick)
    dt = 1.0 / (TRADES_PER_SECOND * 3600 * 6.5)  # fraction of a trading day
    drift = -0.5 * (price - base) / base * dt  # Mean reversion
    shock = vol * math.sqrt(dt) * random.gauss(0, 1)

    price *= (1 + drift + shock)
    price = max(price * 0.5, min(price, price * 1.5))  # Clamp to ±50% of current
    current_prices[symbol] = price
    return round(price, 2)


def generate_trade(symbol: str) -> dict:
    price = random_walk_price(symbol)
    quantity = random.choice([10, 25, 50, 100, 200, 500, 1000])
    return {
        "trade_id": str(uuid.uuid4()),
        "event_time": datetime.now(timezone.utc).isoformat(),
        "symbol": symbol,
        "side": random.choice(["BUY", "SELL"]),
        "quantity": quantity,
        "price": price,
    }


def generate_quote(symbol: str) -> dict:
    price = current_prices[symbol]
    spread_bps = random.uniform(1, 10) * volatilities[symbol] * 10
    spread = price * spread_bps / 10000
    bid = round(price - spread / 2, 2)
    ask = round(price + spread / 2, 2)
    return {
        "symbol": symbol,
        "event_time": datetime.now(timezone.utc).isoformat(),
        "bid": bid,
        "ask": ask,
        "bid_size": random.choice([100, 200, 500, 1000, 2000]),
        "ask_size": random.choice([100, 200, 500, 1000, 2000]),
    }


def delivery_report(err, msg):
    if err is not None:
        print(f"Delivery failed: {err}")


def main():
    producer = Producer({"bootstrap.servers": BROKERS})
    print(f"Generator started. Symbols: {SYMBOLS}")
    print(f"Rate: {TRADES_PER_SECOND} trades/s, {QUOTES_PER_SECOND} quotes/s")

    trade_interval = 1.0 / TRADES_PER_SECOND
    quote_interval = 1.0 / QUOTES_PER_SECOND

    last_trade_time = time.monotonic()
    last_quote_time = time.monotonic()

    while True:
        now = time.monotonic()

        if now - last_trade_time >= trade_interval:
            symbol = random.choice(SYMBOLS)
            trade = generate_trade(symbol)
            producer.produce(
                "raw.trades",
                key=symbol.encode(),
                value=orjson.dumps(trade),
                callback=delivery_report,
            )
            last_trade_time = now

        if now - last_quote_time >= quote_interval:
            symbol = random.choice(SYMBOLS)
            quote = generate_quote(symbol)
            producer.produce(
                "raw.quotes",
                key=symbol.encode(),
                value=orjson.dumps(quote),
                callback=delivery_report,
            )
            last_quote_time = now

        producer.poll(0)
        time.sleep(0.001)  # Prevent busy loop


if __name__ == "__main__":
    main()
```

### Historical Seed Script

**File: `scripts/seed_historical.py`**

```python
"""
Seeds 6 months of historical trade data into ClickHouse.
Run once after infrastructure is up: kubectl exec deploy/backend -- python /workspace/scripts/seed_historical.py
"""
import random
import math
from datetime import datetime, timedelta, timezone
import clickhouse_connect

CH_HOST = "clickhouse.flowforge.svc.cluster.local"
CH_PORT = 8123

SYMBOLS = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "META", "JPM", "BAC", "GS"]
BASE_PRICES = {
    "AAPL": 185.0, "MSFT": 420.0, "GOOGL": 155.0, "AMZN": 190.0,
    "NVDA": 880.0, "TSLA": 245.0, "META": 510.0, "JPM": 195.0,
    "BAC": 35.0, "GS": 420.0,
}

DAYS_BACK = 180
TRADES_PER_DAY_PER_SYMBOL = 500  # ~500k total trades
BATCH_SIZE = 10_000


def generate_historical_trades():
    """Generate 6 months of historical trades."""
    client = clickhouse_connect.get_client(host=CH_HOST, port=CH_PORT)

    start_date = datetime.now(timezone.utc) - timedelta(days=DAYS_BACK)
    batch = []
    total = 0

    for day_offset in range(DAYS_BACK):
        day = start_date + timedelta(days=day_offset)
        if day.weekday() >= 5:  # Skip weekends
            continue

        for symbol in SYMBOLS:
            price = BASE_PRICES[symbol]
            vol = random.uniform(0.15, 0.45)

            for i in range(TRADES_PER_DAY_PER_SYMBOL):
                # Random time during trading hours (9:30 - 16:00 ET)
                hour = random.uniform(9.5, 16.0)
                trade_time = day.replace(
                    hour=int(hour),
                    minute=int((hour % 1) * 60),
                    second=random.randint(0, 59),
                    microsecond=random.randint(0, 999999),
                )

                # Price walk
                dt = 1.0 / TRADES_PER_DAY_PER_SYMBOL
                shock = vol * math.sqrt(dt / 252) * random.gauss(0, 1)
                price *= (1 + shock)
                price = max(price * 0.8, min(price, price * 1.2))

                qty = random.choice([10, 25, 50, 100, 200, 500])
                batch.append([
                    f"hist-{day_offset}-{symbol}-{i}",
                    trade_time,
                    symbol,
                    random.choice(["BUY", "SELL"]),
                    qty,
                    round(price, 2),
                    round(qty * price, 2),
                ])

                if len(batch) >= BATCH_SIZE:
                    client.insert(
                        "flowforge.raw_trades",
                        batch,
                        column_names=["trade_id", "event_time", "symbol", "side", "quantity", "price", "notional"],
                    )
                    total += len(batch)
                    print(f"Inserted {total} trades...")
                    batch = []

    if batch:
        client.insert(
            "flowforge.raw_trades",
            batch,
            column_names=["trade_id", "event_time", "symbol", "side", "quantity", "price", "notional"],
        )
        total += len(batch)

    print(f"Done. Total trades seeded: {total}")


if __name__ == "__main__":
    generate_historical_trades()
```

---

## 19. AGENTS.md and Memory Files

### Root AGENTS.md

**File: `AGENTS.md`**

```markdown
# FlowForge

Visual analytics platform for fintech trading markets. Alteryx-style no-code canvas + embedded BI.

See @docs/PLANNING.md for full product plan.
See @docs/ARCHITECTURE.md for pipeline architecture.
See @docs/DECISIONS.md for technical decision log.
See @PLAN.md for complete implementation specification (this is the authoritative source).

## Project Structure

- `backend/` — FastAPI application. See @backend/AGENTS.md
- `frontend/` — React SPA. See @frontend/AGENTS.md
- `pipeline/` — Data pipeline (Redpanda, Bytewax, dbt, Airflow)
- `k8s/` — Kubernetes manifests (base + overlays)
- `scripts/` — Seed data, health checks, setup

## Core Commands

- `tilt up` — Start all services on local k3d cluster
- `kubectl exec deploy/backend -n flowforge -- pytest` — Run backend tests
- `kubectl exec deploy/frontend -n flowforge -- npm test` — Run frontend tests

## Critical Invariants (NEVER violate these)

- Every PostgreSQL table MUST have a `tenant_id` column. Every query MUST filter on it.
- The workflow compiler targets SQL, not DataFrames. Polars is fallback only.
- Chart components live in `frontend/src/shared/components/charts/`. NEVER duplicate into feature folders.
- All inter-service communication uses K8s DNS: `service.flowforge.svc.cluster.local`
- Schema propagation runs client-side (TypeScript) for instant feedback, server-side (Python) for validation.
- Dashboard widgets ARE canvas output nodes. They are references, not copies.
- ClickHouse client uses HTTP protocol (port 8123) via clickhouse-connect. Not native protocol.
```

### Backend AGENTS.md

**File: `backend/AGENTS.md`**

```markdown
# Backend

FastAPI + async SQLAlchemy + ClickHouse (HTTP) + Materialize (asyncpg) + Redis.

## Rules

- Every route that touches user data MUST use `Depends(get_current_user)` and `Depends(get_tenant)`.
- The query router (`services/query_router.py`) is the ONLY component that queries ClickHouse/Materialize/Redis. Routes never query backing stores directly.
- The workflow compiler outputs SQL strings. It never executes queries — it returns SQL to the query router.
- Use Pydantic models for all request/response schemas. No raw dicts.
- All models inherit from `TenantMixin`. No exceptions.

## Commands

- `uvicorn app.main:app --host 0.0.0.0 --reload` — Dev server on :8000
- `pytest` — Run tests
- `alembic upgrade head` — Run migrations
- `alembic revision --autogenerate -m "description"` — Create migration
```

### Frontend AGENTS.md

**File: `frontend/AGENTS.md`**

```markdown
# Frontend

React 18 + TypeScript + React Flow v12 + Zustand + TanStack Query + Tailwind + ECharts.

## Rules

- All chart components live in `src/shared/components/charts/`. NEVER create chart components inside feature folders.
- Canvas node components go in `src/features/canvas/nodes/`, config panels in `src/features/canvas/panels/`.
- Use Tailwind utility classes. No CSS modules, no styled-components, no inline styles.
- Schema propagation logic lives in `src/shared/schema/propagation.ts`.
- State management: Zustand for canvas state, TanStack Query for server state. No Redux.

## Commands

- `npm run dev` — Vite dev server on :5173
- `npm run typecheck` — tsc --noEmit
- `npm run test` — Vitest
- `npm run lint` — ESLint
```

### Symlinks

Create symlinks so Claude Code can read AGENTS.md:

```bash
# Run from project root
ln -sf AGENTS.md CLAUDE.md
cd backend && ln -sf AGENTS.md CLAUDE.md && cd ..
cd frontend && ln -sf AGENTS.md CLAUDE.md && cd ..
```

---

## 20. Development Workflow

### First-Time Setup

```bash
# 1. Clone the repo (inside WSL2, NOT on Windows filesystem)
cd ~/projects
git clone <repo-url> flowforge
cd flowforge

# 2. Install CLI tools
chmod +x scripts/install-tools.sh
./scripts/install-tools.sh

# 3. Create the k3d cluster
chmod +x scripts/setup-cluster.sh
./scripts/setup-cluster.sh

# 4. Start everything
tilt up

# 5. Wait for all services to be green in Tilt UI (http://localhost:10350)

# 6. Initialize Materialize (click "init-materialize" in Tilt UI, or run manually)
kubectl create -f k8s/base/pipeline/init-materialize-job.yaml -n flowforge

# 7. Seed historical data (click "seed-historical" in Tilt UI, or run manually)
kubectl exec deploy/backend -n flowforge -- python /workspace/scripts/seed_historical.py

# 8. Verify connectivity
kubectl exec deploy/backend -n flowforge -- bash /workspace/scripts/check-connectivity.sh
```

### Daily Development

```bash
cd ~/projects/flowforge
tilt up

# Edit code → Tilt auto-syncs → service auto-reloads
# Backend: edit backend/app/ → uvicorn reloads (2-3s)
# Frontend: edit frontend/src/ → Vite HMR (sub-second)
# Bytewax: edit pipeline/bytewax/flows/ → container restarts (~5s)

# Check logs
tilt logs backend
tilt logs bytewax-vwap

# Or use k9s for full cluster visibility
k9s -n flowforge

# Done for the day
tilt down
```

### Useful Commands

```bash
# Direct database access
psql -h localhost -p 5432 -U flowforge flowforge                    # PostgreSQL
psql -h localhost -p 6875 -U materialize                             # Materialize
curl "http://localhost:8123/?query=SELECT+count()+FROM+flowforge.raw_trades"  # ClickHouse
redis-cli -h localhost                                                # Redis

# Redpanda
rpk topic list --brokers localhost:9092
rpk topic consume raw.trades --brokers localhost:9092 --num 5

# Scale a service
kubectl scale deploy/backend -n flowforge --replicas=3

# View pod resource usage
kubectl top pods -n flowforge

# Full cluster reset
k3d cluster delete flowforge
./scripts/setup-cluster.sh
tilt up
```

---

## 21. Testing Strategy

Testing is a first-class concern. Every backend service, every frontend feature, and every cross-cutting concern (multi-tenancy, auth, schema propagation) has defined testing patterns. CI enforces all tests pass before merge.

### Test Pyramid

| Layer | Scope | Tool | Target |
|-------|-------|------|--------|
| Unit | Single function / class | pytest / vitest | Services, schema engine, formula parser, compiler, React hooks, Zustand stores |
| Integration | Route → service → mock store | pytest + httpx | API routes with mocked external stores + real PostgreSQL |
| Component | Single React component | vitest + Testing Library | Node components, config panels, chart components |
| E2E | Full user flow (browser) | Playwright | Canvas build → preview → pin to dashboard → embed |

### Coverage Targets

| Layer | Minimum | Enforced in CI |
|-------|---------|----------------|
| Backend | 80% line coverage | Yes — `pytest --cov=app --cov-fail-under=80` |
| Frontend | 70% line coverage | Yes — `vitest --coverage --coverage.thresholds.lines=70` |
| E2E | Critical paths only | No minimum — smoke tests for P0 flows |

---

### Backend Testing

#### Structure

```
backend/tests/
├── conftest.py                    # Shared fixtures (see below)
├── api/                           # Route handler integration tests
│   ├── test_workflows.py
│   ├── test_dashboards.py
│   ├── test_widgets.py
│   ├── test_preview.py
│   ├── test_embed_auth.py
│   └── test_health.py
└── services/                      # Service unit tests
    ├── test_workflow_compiler.py
    ├── test_schema_engine.py
    ├── test_query_router.py
    ├── test_formula_parser.py
    └── test_tenant_isolation.py
```

#### Pytest Configuration

In `pyproject.toml`:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
addopts = "-v --tb=short --strict-markers"
markers = [
    "slow: marks tests that take > 1s",
]
```

#### Core Fixtures (`conftest.py`)

```python
import uuid
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.main import create_app
from app.core.database import get_db
from app.api.deps import get_current_tenant_id

TENANT_A = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
TENANT_B = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a transactional DB session that rolls back after each test."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    # Create tables from metadata
    async with engine.begin() as conn:
        from app.models.base import Base
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest.fixture
def tenant_a_client(db_session: AsyncSession):
    """HTTP client authenticated as tenant A."""
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_tenant_id] = lambda: TENANT_A
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture
def tenant_b_client(db_session: AsyncSession):
    """HTTP client authenticated as tenant B."""
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_tenant_id] = lambda: TENANT_B
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
```

#### Test Naming Convention

```
test_<action>_<condition>_<expected>
```

Examples:
- `test_create_workflow_valid_returns_201`
- `test_compile_workflow_missing_source_raises_validation_error`
- `test_query_router_live_table_dispatches_to_materialize`
- `test_list_workflows_filters_by_tenant`

#### Mocking Rules

| When testing | Mock at | Never require |
|---|---|---|
| API routes | Service boundary (inject mock service) | Running external stores |
| Services | Client boundary (mock ClickHouse/Materialize/Redis clients) | Network calls |
| Compiler | Nothing — pure function, test input→output | Any I/O |
| Schema engine | Nothing — pure function | Any I/O |

- Use **factory functions** (not deep fixture chains) for test data:

```python
def make_workflow(*, tenant_id: uuid.UUID = TENANT_A, name: str = "test") -> Workflow:
    return Workflow(id=uuid.uuid4(), tenant_id=tenant_id, name=name, graph_json={})
```

#### Key Test Areas

| Area | What to test | Example assertion |
|---|---|---|
| Workflow compiler | Query merging — adjacent nodes produce single queries | `Filter → Select → Sort` on same table = 1 SQL query |
| Schema engine | Transform functions — output schema for each node type | `Select(["price", "qty"])` on 5-col input → 2-col output |
| Formula parser | Expression parsing — arithmetic, functions, column refs | `[price] * [qty]` → valid SQLGlot AST |
| Query router | Freshness routing — dispatch to correct store | `live_positions` → Materialize, `marts.fct_trades` → ClickHouse |
| API routes | Status codes, validation, response shapes | `POST /api/v1/workflows` with missing `name` → 422 |
| Preview | Cache hit/miss, row limits, execution constraints | Same query twice → second returns `cache_hit: true` |

#### Multi-Tenancy Tests (Required)

Every tenant-scoped route MUST have tests verifying:

1. **List isolation**: `GET /workflows` for tenant A returns only tenant A's workflows
2. **Get isolation**: `GET /workflows/{id}` returns 404 (not 403) for cross-tenant IDs
3. **Create scoping**: `POST /workflows` sets `tenant_id` from auth, not request body
4. **Update isolation**: `PATCH /workflows/{id}` returns 404 for cross-tenant IDs
5. **Delete isolation**: `DELETE /workflows/{id}` returns 404 for cross-tenant IDs
6. **Cross-tenant references**: Widget referencing a workflow from another tenant → 400/404
7. **Cache isolation**: Tenant A's cached preview result NOT returned for tenant B

---

### Frontend Testing

#### Structure

Tests live in `src/__tests__/`, mirroring the `src/` directory:

```
frontend/src/__tests__/
├── setup.ts                       # Global test setup (mocks, cleanup)
├── helpers/
│   ├── render.tsx                 # Custom render with providers (QueryClient, Router, Auth)
│   └── factories.ts              # Test data factories (workflows, nodes, schemas)
├── shared/
│   ├── schema/
│   │   └── propagation.test.ts   # Schema propagation engine unit tests
│   └── components/
│       └── charts/
│           └── BarChart.test.tsx  # Chart component render tests
└── features/
    ├── canvas/
    │   ├── Canvas.test.tsx        # Canvas integration test
    │   ├── nodes/
    │   │   └── FilterNode.test.tsx
    │   └── hooks/
    │       └── useWorkflow.test.ts
    └── dashboards/
        └── Dashboard.test.tsx
```

#### Vitest Configuration

In `vite.config.ts`:

```typescript
/// <reference types="vitest" />
import { defineConfig } from "vite";

export default defineConfig({
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/__tests__/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    coverage: {
      provider: "v8",
      include: ["src/**/*.{ts,tsx}"],
      exclude: ["src/__tests__/**", "src/main.tsx"],
      thresholds: { lines: 70 },
    },
  },
});
```

#### Custom Render Helper

All component tests use a custom `render()` that wraps components with required providers:

```tsx
// src/__tests__/helpers/render.tsx
import { render, type RenderOptions } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });
}

export function renderWithProviders(
  ui: React.ReactElement,
  options?: RenderOptions & { route?: string },
) {
  const queryClient = createTestQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[options?.route ?? "/"]}>
        {ui}
      </MemoryRouter>
    </QueryClientProvider>,
    options,
  );
}
```

#### Mocking Patterns

| Dependency | How to mock |
|---|---|
| **API calls (TanStack Query)** | `msw` (Mock Service Worker) for network-level mocking — intercept `fetch()` calls with realistic responses |
| **Keycloak auth** | Mock `shared/auth/useAuth` to return `{ user, tenantId, token, isAuthenticated: true }` |
| **Zustand stores** | Test with real stores — they're lightweight. Reset between tests in `setup.ts` |
| **React Flow** | Mock `@xyflow/react` for unit tests of individual nodes. Use real React Flow for canvas integration tests |
| **WebSocket** | Mock `shared/websocket/useWebSocket` — return a controllable mock that can emit events |
| **ECharts** | Mock `echarts-for-react` for snapshot tests. Use real ECharts for visual regression (optional) |

#### Test Categories

**1. Schema Propagation (Unit — highest priority)**

The TypeScript schema engine in `shared/schema/propagation.ts` must produce identical results to the Python engine. These are pure-function tests:

```typescript
describe("propagation", () => {
  it("Filter passes schema through unchanged", () => {
    const input = [{ name: "price", type: "Float64" }, { name: "symbol", type: "String" }];
    const output = propagate("filter", input, { conditions: [/*...*/] });
    expect(output).toEqual(input);
  });

  it("Select narrows schema to selected columns", () => {
    const input = [{ name: "price", type: "Float64" }, { name: "qty", type: "Int64" }, { name: "symbol", type: "String" }];
    const output = propagate("select", input, { columns: ["price", "qty"] });
    expect(output).toEqual([{ name: "price", type: "Float64" }, { name: "qty", type: "Int64" }]);
  });

  it("GroupBy produces group keys + aggregated columns", () => {
    // ...
  });
});
```

**2. Canvas Node Components (Component)**

Test that nodes render, accept configuration, and display schema-driven dropdowns:

```typescript
describe("FilterNode", () => {
  it("renders column dropdown from input schema", () => {
    renderWithProviders(<FilterNode data={{ schema: mockSchema }} />);
    expect(screen.getByRole("combobox")).toBeInTheDocument();
  });

  it("calls onConfigChange when filter condition changes", async () => {
    // ...
  });
});
```

**3. Hooks (Unit)**

Test custom hooks that manage workflow state, data preview, and execution:

```typescript
describe("useWorkflow", () => {
  it("saves workflow via mutation and invalidates query cache", async () => {
    // ...
  });
});
```

**4. Chart Components (Component)**

Test that shared chart components render without error and accept the standard `data` + `config` props:

```typescript
describe("BarChart", () => {
  it("renders with valid data", () => {
    renderWithProviders(<BarChart data={mockBarData} config={mockBarConfig} />);
    expect(screen.getByTestId("bar-chart")).toBeInTheDocument();
  });

  it("shows empty state when data is empty", () => {
    renderWithProviders(<BarChart data={[]} config={mockBarConfig} />);
    expect(screen.getByText(/no data/i)).toBeInTheDocument();
  });
});
```

**5. Dashboard (Integration)**

Test the dashboard grid renders widgets from workflow output nodes:

```typescript
describe("Dashboard", () => {
  it("renders widgets from pinned workflow outputs", async () => {
    server.use(
      http.get("/api/v1/dashboards/:id", () => HttpResponse.json(mockDashboard)),
      http.post("/api/v1/preview", () => HttpResponse.json(mockPreviewResult)),
    );
    renderWithProviders(<Dashboard />, { route: "/dashboards/123" });
    await waitFor(() => expect(screen.getByTestId("widget-grid")).toBeInTheDocument());
  });
});
```

#### Dev Dependencies

```json
{
  "devDependencies": {
    "vitest": "^3.0.0",
    "@testing-library/react": "^16.0.0",
    "@testing-library/jest-dom": "^6.0.0",
    "@testing-library/user-event": "^14.0.0",
    "msw": "^2.0.0",
    "jsdom": "^25.0.0",
    "@vitest/coverage-v8": "^3.0.0"
  }
}
```

---

### E2E Testing (Playwright)

E2E tests cover critical user flows that span frontend and backend. They run against a full local stack (k3d).

#### Structure

```
e2e/
├── playwright.config.ts
├── fixtures/
│   └── auth.ts                    # Keycloak login helper
└── tests/
    ├── canvas-build.spec.ts       # Build a workflow end-to-end
    ├── preview.spec.ts            # Preview data on canvas nodes
    ├── dashboard-pin.spec.ts      # Pin output to dashboard, verify render
    ├── embed.spec.ts              # Embed widget via API key, verify render
    └── tenant-isolation.spec.ts   # Verify cross-tenant data is invisible
```

#### Scope

E2E tests are limited to **P0 critical paths**:

1. **Canvas build**: Create workflow → add DataSource → add Filter → connect → preview shows data
2. **Save/load**: Save workflow → reload page → workflow restored
3. **Dashboard pin**: Pin canvas output → navigate to dashboards → widget renders
4. **Embed**: Generate API key → open embed URL → widget renders without Keycloak
5. **Tenant isolation**: Log in as tenant A → create workflow → log in as tenant B → workflow not visible

E2E tests are NOT run in PR CI (too slow). They run on a nightly schedule or manually before releases.

#### Configuration

```typescript
// e2e/playwright.config.ts
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  timeout: 30_000,
  retries: 1,
  use: {
    baseURL: "http://localhost:5173",
    trace: "on-first-retry",
  },
  projects: [{ name: "chromium", use: { browserName: "chromium" } }],
});
```

---

### Schema Propagation Cross-Validation

The TypeScript and Python schema engines MUST produce identical output for the same input. This is enforced by a shared test fixture:

```
tests/fixtures/schema_propagation_cases.json
```

This JSON file contains test cases in the format:

```json
[
  {
    "node_type": "filter",
    "input_schema": [{"name": "price", "type": "Float64"}, {"name": "symbol", "type": "String"}],
    "config": {"conditions": [{"column": "price", "op": ">", "value": 100}]},
    "expected_output_schema": [{"name": "price", "type": "Float64"}, {"name": "symbol", "type": "String"}]
  },
  {
    "node_type": "select",
    "input_schema": [{"name": "price", "type": "Float64"}, {"name": "qty", "type": "Int64"}, {"name": "symbol", "type": "String"}],
    "config": {"columns": ["price", "qty"]},
    "expected_output_schema": [{"name": "price", "type": "Float64"}, {"name": "qty", "type": "Int64"}]
  }
]
```

Both `backend/tests/services/test_schema_engine.py` and `frontend/src/__tests__/shared/schema/propagation.test.ts` load this file and run every case, ensuring parity. Adding a test case to the JSON file tests both engines simultaneously.

---

### CI Integration

See `.github/workflows/ci.yml` for the full workflow. Summary:

| Job | Steps | Gate |
|-----|-------|------|
| `backend` | `ruff check` → `ruff format --check` → `mypy` → `pytest --cov --cov-fail-under=80` | Must pass for merge |
| `frontend` | `eslint` → `tsc --noEmit` → `prettier --check` → `vitest run --coverage` | Must pass for merge |
| `e2e` (nightly) | Start local stack → `npx playwright test` | Advisory only |

### Test Data Factories

Both backend and frontend use factory functions (not fixtures/seeds) for test data:

**Backend** (`tests/conftest.py`):
```python
def make_workflow(**overrides) -> Workflow: ...
def make_dashboard(**overrides) -> Dashboard: ...
def make_widget(*, dashboard: Dashboard, workflow: Workflow, **overrides) -> Widget: ...
```

**Frontend** (`src/__tests__/helpers/factories.ts`):
```typescript
export function makeWorkflow(overrides?: Partial<Workflow>): Workflow { ... }
export function makeNode(type: NodeType, overrides?: Partial<CanvasNode>): CanvasNode { ... }
export function makeSchema(columns: Array<{ name: string; type: string }>): Schema { ... }
```

Factories return valid, realistic objects with sensible defaults. Override only what the test cares about.

---

## 22. Implementation Phases

### Phase 0 — Scaffolding (Weeks 1-2)

**Goal:** Empty shell that starts, connects to all services, and proves the infrastructure works.

**Deliverables:**
- All files in repository structure created (even if stubbed)
- k3d cluster setup working
- Tilt bringing up all services
- Backend: health endpoint returning `{"status": "ok", "services": {"postgres": true, "clickhouse": true, ...}}`
- Frontend: Vite app with React Router showing empty pages for /canvas, /dashboards, /embed/:id
- Data generator: publishing to Redpanda topics
- Materialize: sources and views created
- ClickHouse: tables and MVs created
- Seed script: inserting historical data
- Connectivity check: all green

**Success criteria:** `tilt up` → all resources green → `curl localhost:8000/health` returns all services connected → `curl localhost:5173` returns React app.

### Phase 1 — Core Canvas (Weeks 3-6)

**Goal:** Non-technical user builds Filter → Sort → Table View in under 5 minutes without docs.

**Deliverables:**
- Schema registry discovering and caching table metadata
- Schema propagation (TypeScript + Python)
- 5 canvas nodes: Data Source, Filter, Select, Sort, Table View
- Workflow compiler producing SQL for these 5 nodes
- Preview endpoint with 3-layer execution model (debounce + cache + constraints)
- Query router dispatching to ClickHouse
- Save/load workflows (PostgreSQL)
- Tenant isolation working end-to-end

### Phase 2 — Analytical Nodes (Weeks 7-10)

**Goal:** Users can build meaningful analytical workflows.

**Deliverables:**
- Additional nodes: Group By, Join, Union, Formula, Rename, Unique, Sample
- Formula builder (restricted expression language → SQL compilation)
- Query merging optimization in compiler
- Cross-source joins via Polars fallback

### Phase 3 — Visualization + Dashboards (Weeks 11-15)

**Goal:** 4-widget dashboard loads in under 500ms.

**Deliverables:**
- Visualization nodes: Bar Chart, Line Chart, Candlestick, Scatter Plot, KPI Card, Pivot Table
- Dashboard CRUD
- Widget pinning from canvas
- Dashboard grid layout
- Global filters
- Shared chart components rendering in canvas preview + dashboard + embed

### Phase 4 — Live Data + Embed (Weeks 16-19)

**Goal:** Widgets update within 1 second of new Materialize data.

**Deliverables:**
- WebSocket live data push
- Materialize query integration in query router
- Redis point lookups in query router
- Embed mode with API key auth
- Auto-refresh for dashboard widgets

### Phase 5 — Polish (Weeks 20-22)

**Goal:** New user goes from template to customized dashboard in under 15 minutes.

**Deliverables:**
- Workflow templates
- Undo/redo on canvas
- RBAC enforcement (admin/analyst/viewer)
- Audit logging
- Workflow versioning
