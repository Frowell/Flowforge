# Dashboards Feature — Agent Rules

> Parent rules: [`/workspace/frontend/agents.md`](../../../agents.md) | Architecture: [`/workspace/planning.md`](../../../../../planning.md)

## Core Concept

A dashboard is a grid of widgets. A widget is a **pointer** to a workflow output node — it does NOT store its own query.

```
Widget = {
  source_workflow_id,   // which workflow
  source_node_id,       // which output node in that workflow
  layout: {x, y, w, h}, // grid position
  config_overrides       // filter overrides, refresh interval
}
```

## Data Flow

1. Frontend requests widget data from the backend.
2. Backend compiles the relevant subgraph of the source workflow.
3. Backend applies any filter overrides (from dashboard global filters or widget config).
4. Backend executes the compiled query via the query router.
5. Backend returns results to the frontend.
6. **Frontend does NOT compile queries** — it only renders results.

## Global Filters

- Dashboard-level filters inject `WHERE` clauses into ALL widget queries.
- The filter UI only offers columns that are present in **ALL** widget schemas (intersection of available columns).
- Filter types: date range, dropdown, text search.
- Filter state lives in the dashboard Zustand store; filter application happens server-side.

## Layout

- Use `react-grid-layout` for the widget grid.
- Widget positions stored as `{x, y, w, h}` in the widget's `layout` JSONB column in PostgreSQL.
- Users can drag, resize, and rearrange widgets. Layout changes persist on save.

## WidgetCard Component

`WidgetCard` wraps the shared chart component and adds:

- Title bar with widget name
- Refresh button
- Error state display (e.g., source workflow deleted → explicit error, not silent disappearance)
- Loading skeleton during data fetch
- The chart itself — imported from `shared/components/charts/`, never duplicated here

## Multi-Tenancy

- The dashboard list only shows dashboards belonging to the authenticated user's tenant. The backend filters by `tenant_id` — the frontend simply renders the result set.
- When pinning a widget (selecting a source workflow), the workflow picker only shows workflows from the same tenant. Again, the backend enforces this — the frontend just renders the options.
- The frontend never needs to pass `tenant_id` explicitly. Tenant isolation is fully backend-enforced via the JWT bearer token.

## Live Data Updates

For dashboards with Materialize-backed sources, live data flows via WebSocket:

1. Dashboard opens WebSocket: `ws://localhost:8000/ws/dashboard/{dashboard_id}`
2. Backend subscribes to tenant-scoped Redis pub/sub channel
3. When Materialize data changes, backend publishes to the channel
4. WebSocket handler pushes update notification to connected clients
5. Frontend receives notification and re-fetches the affected widget's data via TanStack Query invalidation

Auto-refresh also available on a configurable interval for non-live sources.

## Global Filter Schema Awareness

The filter UI auto-populates based on column types from the schema registry:

- **Temporal columns** (DateTime types) → date range picker
- **Categorical columns** (String/Enum types) → dropdown with distinct values
- **Numeric columns** → range slider or min/max input

Filters only show columns present in ALL widget schemas (intersection), ensuring every filter applies to every widget.
