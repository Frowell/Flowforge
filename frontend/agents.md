# Frontend — Agent Rules

> Parent rules: [`/workspace/agents.md`](../agents.md) | Architecture: [`/workspace/planning.md`](../planning.md)

## Directory Structure

Feature-based organization:

```
frontend/src/
├── features/
│   ├── canvas/          # Author mode — React Flow workspace
│   │   ├── components/  # Canvas.tsx, NodePalette, ConfigPanel, DataPreview, ExecutionStatus
│   │   ├── nodes/       # Custom node components (one per node type)
│   │   ├── panels/      # Config panel components (one per node type)
│   │   ├── hooks/       # useWorkflow, useSchemaEngine, useDataPreview, useExecution
│   │   └── stores/      # workflowStore.ts (Zustand)
│   ├── dashboards/      # Viewer mode — widget grid + global filters
│   │   ├── components/  # DashboardGrid, WidgetCard, GlobalFilters, PinToDialog
│   │   ├── hooks/       # useDashboard, useWidgetData, useGlobalFilters
│   │   └── stores/      # dashboardStore.ts (Zustand)
│   └── embed/           # Headless mode — single chromeless widget
│       ├── EmbedRoot.tsx
│       └── EmbedWidget.tsx
├── shared/
│   ├── components/
│   │   ├── charts/      # BarChart, LineChart, Candlestick, ScatterPlot, KPICard, PivotTable
│   │   ├── DataGrid.tsx
│   │   └── FormulaEditor.tsx
│   ├── query-engine/    # HTTP/WS client + types
│   ├── schema/          # registry, propagation, types
│   ├── auth/
│   └── websocket/       # Connection manager
├── App.tsx
├── main.tsx
└── index.css
```

## Critical Rule: Shared Charts

ALL chart components live in `shared/components/charts/`. Never create chart components inside feature directories. Canvas preview, dashboard widget, and embed iframe all import from the same place.

## State Management Split

| What | Where | Why |
|---|---|---|
| UI state (selection, panel open, layout) | Zustand stores | Synchronous, local, no server round-trip |
| Server data (workflows, schemas, results) | TanStack Query | Caching, refetching, stale-while-revalidate |

Never store server-fetched data in Zustand. Never use TanStack Query for purely local UI state.

## React Flow

- Import from `@xyflow/react` (v12+), **never** from `reactflow`.
- Custom nodes live in `features/canvas/nodes/`.
- Full canvas state (nodes, edges, viewport) serializes to `graph_json` JSONB column in PostgreSQL.
- Use React Flow's built-in state management for node/edge positions; sync to Zustand for app-level concerns (selected node, execution state).

## Schema Propagation

- Synchronous TypeScript engine in `shared/schema/propagation.ts`.
- Must match the Python engine in `backend/app/services/schema_engine.py` — same logic, same results.
- Target: < 10ms for a 50-node graph.
- Runs on every connection change to provide instant feedback (dropdown population, type error highlighting).

## Styling

- **Tailwind CSS only** — no CSS modules, styled-components, or inline `style` objects.
- Use `canvas-*` design tokens for canvas-specific styling.
- Use a `cn()` utility (clsx + tailwind-merge) for conditional class composition.
- Dark theme is the default.

## API Client

- Single fetch wrapper in `shared/query-engine/client.ts`.
- All API calls go through TanStack Query hooks — never call `fetch()` directly in components.
- Base URL from environment config, all endpoints prefixed with `/api/v1/`.

## Authentication & Multi-Tenancy

- **Keycloak SSO** via `keycloak-js` adapter in `shared/auth/keycloak.ts`.
- Canvas and dashboard routes require Keycloak authentication. The API client automatically injects Bearer tokens.
- Embed routes use API key auth (URL params), not Keycloak.
- Keycloak handles identity provider selection (Google, GitHub, SAML, corporate SSO, etc.) — the frontend does not manage provider-specific logic.

### Tenant Context

- The Keycloak JWT contains a `tenant_id` claim. The `getCurrentUser()` function in `shared/auth/keycloak.ts` exposes `tenantId` alongside `id`, `email`, `name`, and `roles`.
- The frontend does NOT send `tenant_id` as a separate header or query parameter. The backend extracts it from the JWT `Authorization: Bearer` token on every request.
- The frontend never displays data from multiple tenants. Tenant switching (if supported) requires re-authentication through Keycloak.
- All TanStack Query cache keys are implicitly tenant-scoped because the backend only returns data for the authenticated tenant. No explicit tenant key prefix is needed in query keys.

## TypeScript

- Strict mode enabled — no implicit `any`.
- Use `@/` import alias for all project imports.
- Prefer `interface` for object shapes, `type` for unions and intersections.
- No untyped `any` — use `unknown` and narrow with type guards when needed.

## Chart Library

All charts use **Recharts**. Available chart types:

- `BarChart.tsx` — standard bar/column charts
- `LineChart.tsx` — time-series line charts
- `CandlestickChart.tsx` — OHLC candlestick charts (fintech-specific)
- `ScatterPlot.tsx` — scatter/bubble plots
- `KPICard.tsx` — single-value KPI display
- `PivotTable.tsx` — pivot/crosstab tables

All chart components accept `data` + `config` props and are responsive (fill container). Never set fixed pixel dimensions.

## Route Structure

```
/canvas                     → Canvas.tsx (React Flow workspace)
/canvas/:workflow_id        → Canvas.tsx (load specific workflow)
/dashboards                 → Dashboard list
/dashboards/:dashboard_id   → Dashboard.tsx (widget grid)
/embed/:widget_id           → EmbedView.tsx (chromeless single widget)
```

Canvas and Dashboards use Keycloak OIDC authentication. Embed uses API key authentication.

## Key Dependencies

| Package | Purpose |
|---------|---------|
| `react`, `react-dom` | UI framework |
| `react-router-dom` | Client-side routing |
| `@xyflow/react` (v12+) | Canvas node graph (NEVER import from `reactflow`) |
| `zustand` | Client-side UI state |
| `@tanstack/react-query` (v5) | Server state + caching |
| `recharts` | Chart rendering |
| `react-grid-layout` | Dashboard widget grid |
| `keycloak-js` | OIDC authentication adapter |
| `tailwindcss` | Styling (utility-first, no CSS modules) |
| `vite` | Build tooling + HMR dev server |
| `vitest` | Unit testing |

## Widget Lifecycle

1. User builds workflow on canvas: DataSource → Filter → Sort → TableView
2. User pins an output node to a dashboard (creates a `Widget` record)
3. Widget record stores: `{ workflow_id, output_node_id, dashboard_id, layout, config_overrides }`
4. Dashboard renders widget by executing the workflow subgraph up to the pinned node
5. Widget auto-refreshes on interval or via WebSocket for live data

Widgets are references to canvas output nodes — NOT copies. If the workflow changes, the widget output changes.
