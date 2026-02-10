# 0008: All Output Node Types Are Pinnable to Dashboards

**Status:** Accepted
**Date:** 2026-02-10
**Deciders:** Frontend team

## Context

Only chart_output nodes had a "Pin to Dashboard" button in the canvas config panel. Table outputs and KPI outputs could not be pinned, even though the entire backend pipeline (Widget API, WidgetDataService, ChartRenderer) already supports rendering all three output types as dashboard widgets. This meant users could not create data-grid widgets or KPI-card widgets on dashboards.

## Decision

All terminal output node types (chart_output, table_output, kpi_output) are pinnable to dashboards. Widget rendering is dispatch-based via `ChartRenderer`, which already handles `"table"` (renders `DataGrid`) and `"kpi"` (renders `KPICard`) cases alongside chart types. The fix is frontend-only: add the pin-to-dashboard UI to `TableOutputPanel` and `KPIPanel`.

## Alternatives Considered

**Only allow chart outputs on dashboards**: Simpler, but artificially limits dashboard utility. Users frequently need raw data tables for debugging and KPI cards for executive summaries.

**Create separate "dashboard widget" creation flow**: A dedicated widget builder outside the canvas. Rejected because it contradicts ADR 0006 — dashboards are projections of workflows, not independent query definitions.

## Consequences

- **Positive**: Users can pin any output node to a dashboard, enabling data-grid and KPI-card widgets.
- **Positive**: No backend changes — leverages existing dispatch-based rendering.
- **Positive**: Consistent UX — every output node has the same pin affordance.
- **Negative**: None significant. The backend path was already exercised; this just exposes it in the UI.
