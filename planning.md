# FlowForge — Product Planning

## Scope

This plan covers the **analytics canvas** (Alteryx clone) and the **embedded BI layer** (dashboards + embeddable widgets). The data pipeline (Redpanda, Bytewax, dbt, Airflow, ClickHouse ingestion) is a separate workstream. This application integrates with the pipeline through a well-defined query interface and schema registry — it does not own data ingestion or transformation orchestration.

### What This Application Does

- Provides a visual, no-code canvas for building analytical workflows on top of shaped data
- Compiles canvas workflows into queries against the serving layer (ClickHouse, Materialize, Redis)
- Renders live dashboards composed of pinned canvas outputs
- Exposes embeddable widgets for integration into customer-facing portals

### What This Application Does NOT Do

- Ingest raw data from market feeds
- Orchestrate dbt runs or Airflow DAGs
- Manage streaming dataflow lifecycles (Bytewax, Materialize view creation)
- Own the schema of analytical tables — it reads from whatever the pipeline produces

---

## Product Surface

One application, three modes, same backend.

**Canvas (`/canvas`)** — Author mode. Power users drag nodes onto a React Flow workspace, configure transforms through schema-aware GUI forms, preview intermediate results, and wire up output visualizations. Workflows operate on data that already exists in the serving layer. The canvas is a "last mile" tool — ad-hoc filtering, aggregation, pivoting, and charting on top of pipeline-produced tables.

**Dashboards (`/dashboards`)** — Viewer mode. Consumers see a grid of live widgets pinned from canvas output nodes. They can filter, drill down, and rearrange layouts without touching the canvas. A dashboard widget is the same object as a canvas output node, just rendered in a different container.

**Embed (`/embed/:widget_id`)** — Headless mode. A single widget rendered chromeless for iframe embedding. API key authentication instead of session auth. Same rendering code as dashboards.

---

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
              │             │                  │
              └─────────────┴──────────────────┘
                            │
                   DATA PIPELINE
                   (separate workstream)
                   Owns ingestion, transformation,
                   and shaping. Populates the
                   serving layer that this
                   application reads from.
```

### Pipeline Integration Contract

This application treats the serving layer as read-only. The contract with the pipeline is:

**What the pipeline provides:**
- ClickHouse tables (marts, rollups) with documented schemas
- Materialize views for real-time data (positions, P&L, quotes)
- Redis keys for point lookups (latest quotes, current state)
- A schema catalog (table names, column names, column types, descriptions) queryable via ClickHouse `system.columns` and Materialize `mz_catalog`

**What this application expects:**
- Table schemas don't change without notice (enforced by dbt contracts on the pipeline side)
- Materialized views are queryable via PG wire protocol
- Redis keys follow a documented naming convention
- New tables/views appear in the schema catalog automatically

**What this application does NOT depend on:**
- How data gets into ClickHouse (Bytewax, dbt, direct insert — doesn't matter)
- Redpanda topic structure
- Airflow DAG definitions
- dbt model internals

---

## Schema Engine

The schema propagation engine is the architectural core. It makes the no-code canvas actually work by giving every configuration panel contextual awareness of what data is available.

### How It Works

1. **Discovery:** On startup and periodically, the schema registry queries the serving layer catalogs (ClickHouse `system.columns`, Materialize `mz_catalog`, Redis key patterns) to build a map of available tables, columns, and types.

2. **Propagation:** When a user places a node on the canvas and connects it to upstream nodes, the schema engine computes the output schema of each node based on its type, configuration, and input schemas. This runs client-side in TypeScript for instant feedback.

3. **Validation:** Before execution, the backend re-validates the full DAG schema server-side. Mismatched types, missing columns, and broken connections are flagged before any query runs.

4. **Panel population:** Configuration panels use propagated schemas to populate dropdowns. A Filter node shows only the columns available from its upstream connection. Operator choices change based on column type (numeric gets `>/<`, string gets `contains/starts with`, datetime gets `before/after`).

### Schema Transform Contract

Every node type declares how it transforms schemas:

```
Node Type       Input Schema → Output Schema
─────────       ──────────────────────────────────────────
Data Source     (none) → table schema from catalog
Filter          passthrough (same columns, fewer rows)
Select          subset of input columns
Rename          input columns with name substitutions
Sort            passthrough (same columns, reordered rows)
Join            merged schemas from both inputs
Group By        group keys + aggregate output columns
Pivot           group keys + pivoted value columns
Formula         input columns + new calculated column
Unique          passthrough (deduplicated rows)
Sample          passthrough (fewer rows)
Chart Output    (terminal, no output schema)
Table Output    (terminal, no output schema)
```

---

## Canvas Node Types

### Phase 1 — Core (MVP)

| Node | Category | Config Panel | Compiles To |
|---|---|---|---|
| **Data Source** | Input | Table picker from schema catalog, optional column selection | `SELECT` from ClickHouse/Materialize |
| **Filter** | Transform | Column dropdown, operator picker (type-aware), value input, AND/OR conditions | `WHERE` clause |
| **Select** | Transform | Checkbox list of columns, drag to reorder | `SELECT` column list |
| **Sort** | Transform | Column dropdown, ASC/DESC toggle, multi-column | `ORDER BY` clause |
| **Table View** | Output | Pagination, column visibility, sort-on-click | Rendered `<DataGrid>` component |

### Phase 2 — Analytical

| Node | Category | Config Panel | Compiles To |
|---|---|---|---|
| **Group By** | Aggregate | Dimension column picker, metric column + aggregation function (SUM, AVG, COUNT, MIN, MAX, etc.) | `GROUP BY` + aggregate functions |
| **Join** | Combine | Join type (inner/left/right/full), key column mapping from each input | `JOIN ... ON` |
| **Union** | Combine | Column alignment mapping between inputs | `UNION ALL` |
| **Formula** | Calculate | Expression editor with column refs `[col]`, function palette, output type preview | Computed column expression |
| **Rename** | Transform | Column name mapping (old → new) | `SELECT col AS new_name` |
| **Unique** | Transform | Column subset for deduplication | `DISTINCT ON` or `GROUP BY` |
| **Sample** | Transform | Row count or percentage, random seed option | `LIMIT` or `SAMPLE` |

### Phase 3 — Visualization

| Node | Category | Config Panel | Compiles To |
|---|---|---|---|
| **Bar Chart** | Output | X-axis column, Y-axis column(s), color grouping, orientation | Chart.js / Recharts config |
| **Line Chart** | Output | X-axis (time), Y-axis series, line style | Chart.js / Recharts config |
| **Candlestick** | Output | Open/high/low/close column mapping, time axis | Lightweight Charts config |
| **Scatter Plot** | Output | X/Y axis columns, size column, color column | Chart.js / Recharts config |
| **KPI Card** | Output | Metric column, aggregation, comparison period, threshold coloring | Single-value display |
| **Pivot Table** | Output | Row dimensions, column dimensions, value + aggregation | Pivoted grid renderer |

### Node Behavior Rules

- Every node has exactly one output port except Join/Union which have two input ports
- Terminal nodes (outputs) have no output port
- Connections validate schema compatibility on connect (red highlight if incompatible)
- Every non-terminal node supports a data preview (first 100 rows of its output)
- Nodes show execution status during workflow run (pending → running → complete/error)
- Config panels are read-only when the workflow is executing

---

## Query Router

The backend decides which backing store to query based on the data source and freshness requirements of the workflow.

```
Query Type                    Target              Latency Target
──────────────────────────    ─────────────────   ──────────────
Live data (positions, P&L)    Materialize         < 10ms
Point lookup (latest quote)   Redis               < 1ms
Ad-hoc analytical query       ClickHouse          < 500ms
Historical time-range query   ClickHouse rollups   < 500ms
Metadata / catalog            PostgreSQL          < 50ms
```

The query router is the ONLY component that knows about the backing stores. Canvas nodes don't know if they're querying ClickHouse or Materialize — they express intent ("I need the positions table with realtime freshness") and the router dispatches.

---

## Workflow Compilation

When a user runs a workflow or pins an output to a dashboard, the backend compiles the canvas DAG into executable queries.

### Compilation Steps

1. **Topological sort** the node graph to determine execution order
2. **Schema validate** every connection in the DAG
3. **Merge adjacent nodes** into single queries where possible (Filter → Select → Sort on the same table = one `SELECT ... WHERE ... ORDER BY` query, not three round-trips)
4. **Determine target** for each query segment based on source table freshness
5. **Execute** compiled queries, streaming results to the frontend via WebSocket for live outputs or returning via REST for static outputs

### Query Merging Example

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

---

## Dashboard System

### Widget Lifecycle

1. User builds a workflow on the canvas with a chart output node
2. User clicks "Pin to Dashboard" on the output node
3. System creates a widget record referencing the workflow and output node
4. Widget appears on the selected dashboard in the layout grid
5. Widget queries are executed on dashboard load and refreshed on interval or via WebSocket
6. Widget can be resized, repositioned, and removed from the dashboard without affecting the source workflow

### Dashboard Data Model

```
workflow
  id, name, description, graph_json (React Flow serialized state),
  created_by, created_at, updated_at

dashboard
  id, name, description, created_by, created_at, updated_at

widget
  id, dashboard_id, source_workflow_id, source_node_id,
  layout (x, y, w, h), config_overrides (filters, refresh interval),
  created_at

dashboard_filter
  id, dashboard_id, filter_type (date_range, dropdown, text),
  target_column, config, position
```

A widget is a pointer to a canvas output node. Changing the workflow updates the widget. Deleting the workflow orphans the widget (shows an error state, not a silent disappearance).

### Global Filters

Dashboards support global filters that propagate to all widgets. A date range filter, for example, injects a `WHERE event_time BETWEEN $start AND $end` into every widget's compiled query. This works because the schema registry knows which columns are temporal — the filter UI only offers columns that exist across all widgets on the dashboard.

### Embed Mode

`/embed/:widget_id?api_key=sk_live_...` renders a single widget with:
- No navigation shell, sidebar, or header
- API key authentication (validated server-side, scoped to specific widgets)
- Optional URL parameters for filter overrides (`?symbol=AAPL&range=1d`)
- Responsive sizing to fill the iframe container
- Same chart rendering code as dashboards

---

## Formula Builder

The low-code escape hatch. A restricted expression language that covers common analytical calculations without requiring Python or SQL knowledge.

### Expression Grammar

```
expression  = term (('+' | '-') term)*
term        = factor (('*' | '/') factor)*
factor      = NUMBER | STRING | COLUMN_REF | function_call | '(' expression ')'
COLUMN_REF  = '[' column_name ']'
function    = FUNC_NAME '(' expression (',' expression)* ')'

Available functions:
  Math:     ABS, ROUND, CEIL, FLOOR, MOD, POWER, SQRT, LOG
  Text:     UPPER, LOWER, TRIM, LEFT, RIGHT, LENGTH, CONCAT, REPLACE, CONTAINS
  Date:     YEAR, MONTH, DAY, HOUR, MINUTE, DATE_DIFF, DATE_ADD, NOW
  Logic:    IF(condition, then, else), CASE, COALESCE, NULLIF
  Agg:      SUM, AVG, COUNT, MIN, MAX, MEDIAN, STDDEV (only inside Group By)
  Window:   LAG, LEAD, ROW_NUMBER, RANK, RUNNING_TOTAL (only with Sort defined)
```

### Compilation

Expressions are parsed into an AST client-side for validation and syntax highlighting, then compiled to ClickHouse SQL or Materialize SQL server-side:

```
User writes:     ([revenue] - [cost]) / [revenue] * 100
Compiles to:     (revenue - cost) / revenue * 100

User writes:     IF([quantity] > 1000, "large", "small")
Compiles to:     CASE WHEN quantity > 1000 THEN 'large' ELSE 'small' END

User writes:     ROUND([price] * [quantity], 2)
Compiles to:     round(price * quantity, 2)
```

---

## Frontend Structure

```
frontend/src/
├── features/
│   ├── canvas/
│   │   ├── components/
│   │   │   ├── Canvas.tsx              # React Flow instance + controls
│   │   │   ├── NodePalette.tsx         # Draggable node type sidebar
│   │   │   ├── ConfigPanel.tsx         # Right-side node config
│   │   │   ├── DataPreview.tsx         # Node output preview grid
│   │   │   └── ExecutionStatus.tsx     # Run progress overlay
│   │   ├── nodes/
│   │   │   ├── DataSourceNode.tsx
│   │   │   ├── FilterNode.tsx
│   │   │   ├── JoinNode.tsx
│   │   │   ├── GroupByNode.tsx
│   │   │   ├── FormulaNode.tsx
│   │   │   ├── ChartOutputNode.tsx
│   │   │   └── TableOutputNode.tsx
│   │   ├── panels/
│   │   │   ├── DataSourcePanel.tsx
│   │   │   ├── FilterPanel.tsx
│   │   │   ├── JoinPanel.tsx
│   │   │   ├── GroupByPanel.tsx
│   │   │   ├── FormulaPanel.tsx
│   │   │   └── ChartConfigPanel.tsx
│   │   ├── hooks/
│   │   │   ├── useWorkflow.ts          # Workflow CRUD
│   │   │   ├── useSchemaEngine.ts      # Client-side schema propagation
│   │   │   ├── useDataPreview.ts       # Fetch preview for selected node
│   │   │   └── useExecution.ts         # Run workflow, track status via WS
│   │   └── stores/
│   │       └── workflowStore.ts        # Zustand: nodes, edges, selection
│   │
│   ├── dashboards/
│   │   ├── components/
│   │   │   ├── DashboardGrid.tsx       # react-grid-layout widget container
│   │   │   ├── WidgetCard.tsx          # Individual widget wrapper
│   │   │   ├── GlobalFilters.tsx       # Date range, dropdowns
│   │   │   ├── DashboardPicker.tsx     # Dashboard list + CRUD
│   │   │   └── PinToDialog.tsx         # Pin canvas output → dashboard
│   │   ├── hooks/
│   │   │   ├── useDashboard.ts
│   │   │   ├── useWidgetData.ts
│   │   │   └── useGlobalFilters.ts
│   │   └── stores/
│   │       └── dashboardStore.ts
│   │
│   └── embed/
│       ├── EmbedRoot.tsx               # Minimal shell, API key auth
│       └── EmbedWidget.tsx             # Single widget renderer
│
├── shared/
│   ├── components/
│   │   ├── charts/
│   │   │   ├── BarChart.tsx
│   │   │   ├── LineChart.tsx
│   │   │   ├── CandlestickChart.tsx
│   │   │   ├── ScatterPlot.tsx
│   │   │   ├── KPICard.tsx
│   │   │   └── PivotTable.tsx
│   │   ├── DataGrid.tsx                # TanStack Table
│   │   └── FormulaEditor.tsx           # Expression input + highlighting
│   ├── query-engine/
│   │   ├── client.ts
│   │   └── types.ts
│   ├── schema/
│   │   ├── registry.ts
│   │   ├── propagation.ts
│   │   └── types.ts
│   ├── auth/
│   │   └── keycloak.ts
│   └── websocket/
│       └── manager.ts
│
├── App.tsx
├── main.tsx
└── index.css
```

### Backend Structure

```
backend/app/
├── api/
│   ├── routes/
│   │   ├── health.py                  # /health, /health/live, /health/ready
│   │   ├── metrics.py                 # Prometheus scrape endpoint (GET /metrics)
│   │   ├── workflows.py               # CRUD: create, read, update, delete, list
│   │   ├── executions.py              # Run workflow, get status, cancel
│   │   ├── dashboards.py              # CRUD: dashboards + widget layout
│   │   ├── widgets.py                 # Pin/unpin, config overrides
│   │   ├── embed.py                   # API key validation, widget data
│   │   ├── schema.py                  # Catalog: available tables, columns, types
│   │   └── ws.py                      # WebSocket: live results, execution status
│   └── deps.py                        # Dependency injection
├── core/
│   ├── config.py
│   ├── database.py                    # Async SQLAlchemy (PostgreSQL — app metadata)
│   ├── clickhouse.py                  # ClickHouse async client
│   ├── redis.py                       # Redis async client
│   ├── auth.py                        # Keycloak token validation
│   ├── logging_config.py              # structlog configuration (JSON/console)
│   ├── metrics.py                     # Prometheus metrics registry (flowforge_*)
│   └── middleware.py                  # ObservabilityMiddleware (request IDs, HTTP metrics)
├── models/
│   ├── workflow.py
│   ├── dashboard.py
│   └── user.py
├── schemas/
│   ├── workflow.py
│   ├── dashboard.py
│   ├── preview.py
│   ├── query.py
│   └── schema.py
├── services/
│   ├── schema_registry.py             # Discovers schemas from CH/Materialize
│   ├── schema_engine.py               # DAG schema propagation + validation
│   ├── query_router.py                # Dispatches to CH/Materialize/Redis
│   ├── workflow_compiler.py           # Canvas DAG → merged SQL queries
│   ├── formula_parser.py              # Expression AST → SQL compilation
│   ├── preview_service.py             # Content-addressed preview cache + execution
│   ├── widget_data_service.py         # Widget data fetch with caching
│   ├── rate_limiter.py                # Redis fixed-window rate limiter (embed)
│   └── websocket_manager.py           # Connection tracking, pub/sub
└── tests/
    ├── conftest.py
    ├── test_logging_config.py
    └── test_metrics.py
```

---

## Implementation Phases

### Phase 0: Foundation (Weeks 1–2)

Devcontainer, project scaffolding, and the empty shell.

- [x] Devcontainer with PostgreSQL, Redis (dev instances)
- [x] Add ClickHouse and Materialize to devcontainer
- [x] Seed ClickHouse with sample market data (trades, quotes, positions, instruments) for development
- [x] FastAPI backend skeleton: health check, CORS, async SQLAlchemy, ClickHouse client
- [x] PostgreSQL schema: workflows, dashboards, widgets, users (ORM models complete)
- [ ] Generate initial Alembic migration from ORM models (`alembic revision --autogenerate`)
- [x] React SPA shell with routing (`/canvas`, `/dashboards`, `/embed/:id`)
- [x] React Flow canvas rendering with empty workspace and basic node drag-and-drop
- [x] CI: lint, type-check, test on push (pre-commit hooks + Makefile exist, GitHub Actions missing)

**Deliverable:** Empty canvas loads, API responds, ClickHouse has queryable sample data.

### Phase 1: Schema Engine + Core Nodes (Weeks 3–6)

The schema propagation engine and the first five node types. Every subsequent phase builds on this.

- [ ] Schema registry: query ClickHouse `system.columns` and Materialize `mz_catalog`, cache results
- [ ] Schema propagation engine: TypeScript (client-side, instant feedback) + Python (server-side, authoritative)
- [ ] Node type registry: declared input/output schemas per node type
- [ ] Configuration panel framework: right sidebar, panels swap based on selected node, schema-aware dropdowns
- [ ] **Data Source node:** table picker from catalog, column selection, row limit
- [ ] **Filter node:** column dropdown (from upstream schema), type-aware operator picker, value input, AND/OR groups, live match count preview
- [ ] **Select node:** checkbox column list, drag-to-reorder
- [ ] **Sort node:** column dropdown, ASC/DESC, multi-column priority
- [ ] **Table View output node:** paginated grid (TanStack Table), column resize, sort-on-click
- [ ] Data preview on any node: click node → see first 100 rows of output
- [ ] Workflow save/load: serialize React Flow state to PostgreSQL, list/open saved workflows
- [ ] Workflow compiler: merge adjacent Filter/Select/Sort into single ClickHouse query

**Deliverable:** User builds a 5-node workflow (Source → Filter → Select → Sort → Table), configures each via GUI with schema-aware dropdowns, previews at each step, saves and reloads.

### Phase 2: Analytical Nodes + Formula Builder (Weeks 7–10)

The nodes that make this more than a SQL GUI.

- [ ] **Group By node:** dimension picker, metric + aggregation function selector (SUM/AVG/COUNT/MIN/MAX), multiple metrics
- [ ] **Join node:** join type selector (inner/left/right/full), key column mapping from each input, schema merge preview
- [ ] **Union node:** column alignment mapping, type coercion warnings
- [ ] **Formula node:** expression editor with column reference autocomplete, function palette sidebar, output type inference, syntax validation
- [ ] **Rename node:** column name mapping (old → new)
- [ ] **Unique node:** column subset picker for deduplication key
- [ ] **Sample node:** row count or percentage, random seed toggle
- [ ] Formula parser: expression AST → ClickHouse SQL compilation, error messages with position highlighting
- [ ] Compiler update: handle multi-source DAGs (joins), subquery generation for complex graphs

**Deliverable:** User joins two tables, groups by a dimension, adds a calculated field via formula, filters the result, and views it in a table. Formula builder handles arithmetic, conditionals, and common functions.

### Phase 3: Visualization + Dashboards (Weeks 11–15)

Chart outputs and the full dashboard lifecycle.

- [ ] **Bar Chart output node:** X/Y axis column mapping, color grouping, horizontal/vertical, stacked option
- [ ] **Line Chart output node:** time axis, multi-series, line style, area fill option
- [ ] **Candlestick output node:** OHLC column mapping, time axis, volume subplot
- [ ] **Scatter Plot output node:** X/Y axis, size column, color column, trend line toggle
- [ ] **KPI Card output node:** metric column, aggregation, comparison value, threshold coloring (red/yellow/green)
- [ ] **Pivot Table output node:** row/column dimension pickers, value + aggregation
- [ ] Shared chart component library: same components render in canvas preview, dashboard widgets, and embeds
- [ ] "Pin to Dashboard" dialog on any output node: pick or create target dashboard
- [ ] Dashboard grid layout: drag/resize widgets (react-grid-layout), save layout to PostgreSQL
- [ ] Dashboard list view: create, rename, delete, open dashboards
- [ ] Global dashboard filters: date range picker, dropdown filters, propagated to all widget queries
- [ ] Drill-down: click chart element → filtered detail view in a modal or expanded panel
- [ ] Dashboard save/load/share via URL

**Deliverable:** User builds a workflow with 3 chart outputs, pins them to a dashboard, adds a date range filter. A colleague opens the dashboard URL and sees live data.

### Phase 4: Live Data + Embed (Weeks 16–19)

WebSocket integration and the embeddable widget system.

- [ ] WebSocket infrastructure: connection manager, subscription lifecycle, reconnection handling
- [ ] Live query mode: Materialize-backed Data Source nodes push updates via WebSocket (charts redraw on new data)
- [ ] Redis integration: query router dispatches point lookups to Redis for sub-ms latest-state queries
- [ ] Auto-refresh on dashboard widgets: configurable interval (5s, 30s, 1m, 5m) or live (WebSocket)
- [ ] Embed mode: `/embed/:widget_id` route with chromeless rendering
- [ ] API key management: create/revoke keys scoped to specific widgets or dashboards
- [ ] Embed URL parameters: `?symbol=AAPL&range=1d` override widget filters
- [ ] Embed responsive sizing: widget fills iframe container

**Deliverable:** Dashboard widgets update in real time as new data flows into Materialize. An embedded widget renders in a customer's portal via iframe with API key auth.

### Phase 5: Templates + Polish (Weeks 20–22)

Reduce time-to-value and production readiness.

- [ ] Template workflows:
  - Real-Time Position Monitor (positions source → group by symbol → KPI cards + bar chart)
  - VWAP Analysis (trades source → formula [price × qty] → group by time window → candlestick)
  - Sector Exposure Breakdown (positions join instruments → group by sector → pie/bar chart)
  - Trade Blotter (trades source → filter by date → sort by time → table view)
  - P&L Dashboard (positions source → formula [unrealized P&L] → KPI card + line chart over time)
- [ ] Template picker in canvas: start from blank or from template
- [ ] Workflow versioning: save versions, revert to previous
- [ ] Undo/redo on canvas (Zustand middleware)
- [ ] Keyboard shortcuts: delete node, copy/paste, select all, run workflow
- [ ] Role-based access: admin (everything), analyst (canvas + dashboards), viewer (dashboards only)
- [ ] Audit logging: who created/modified/ran what, queryable in admin panel
- [ ] Error states: orphaned widgets, failed queries, disconnected WebSocket, stale schema

**Deliverable:** New user picks a template, customizes it, and has a live dashboard in under 15 minutes. Access control enforced per role.

---

## Key Technical Decisions

**Query merging is critical for performance.** A naive implementation sends one query per node. A 7-node linear workflow would mean 7 round-trips to ClickHouse. The compiler must merge adjacent compatible nodes into single queries. This is the difference between 50ms and 500ms execution.

**Schema propagation runs client-side first.** The TypeScript schema engine provides instant feedback as users connect nodes — dropdowns populate immediately, type errors highlight on connect, not on run. The Python server-side engine is authoritative and validates before execution.

**Charts render with the same component everywhere.** A `<BarChart>` in a canvas data preview, a dashboard widget, and an embedded iframe is literally the same React component with different container styling. One implementation, one set of bugs, one place to fix.

**The workflow compiler targets SQL, not DataFrames.** Canvas workflows compile to ClickHouse SQL (or Materialize SQL for live data). The database does the heavy lifting — the backend is a thin translation layer, not a compute engine. This means the application scales with ClickHouse, not with backend hardware.

**Dashboards are projections of canvas workflows, not independent objects.** A widget doesn't store its own query — it points to a workflow output node. Changing the workflow changes the widget. This eliminates sync problems between the canvas and dashboards.

---

## Success Criteria

**Phase 1:** A non-technical user builds a Filter → Sort → Table workflow on sample data, using only the GUI, in under 5 minutes without documentation.

**Phase 3:** A trading desk has a 4-widget dashboard (candlestick, exposure bar chart, P&L KPI, trade blotter table) displaying data from ClickHouse with < 500ms load time.

**Phase 4:** Dashboard widgets update within 1 second of new data appearing in Materialize. Embedded widget renders correctly in a third-party portal iframe.

**Phase 5:** New user starts from a template and has a customized live dashboard in under 15 minutes.
