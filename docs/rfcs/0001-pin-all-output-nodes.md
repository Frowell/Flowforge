# RFC 0001: Pin All Output Nodes to Dashboards

**Status:** Accepted
**Date:** 2026-02-10
**Author:** Frontend team

## Summary

Enable pinning table_output and kpi_output nodes to dashboards, not just chart_output nodes.

## Motivation

Currently only chart_output nodes have a "Pin to Dashboard" button. Table outputs are useful for pipeline debugging dashboards (showing raw data grids), and KPI outputs are natural dashboard widgets (single-metric cards). The backend already supports all output types — `WidgetDataService` handles table_output by setting `chart_type: "table"`, and `ChartRenderer` dispatches to `DataGrid` for tables and `KPICard` for KPI widgets. The gap is purely in the frontend config panels.

## Proposal

Add the pin-to-dashboard button (and `PinToDialog`) to:

1. **TableOutputPanel** (new) — a config panel for table_output nodes with title, rows-per-page, and pin button
2. **KPIPanel** (existing) — append the same pin button block at the bottom

No backend changes required. The Widget API accepts any `source_node_id` without type filtering, and the rendering pipeline already dispatches correctly.

## Scope

- Frontend only: 3 files modified, 1 file created
- No new dependencies
- No API changes
- No database migrations

## Risks

Low. The backend path is already exercised by chart_output pinning. The only new code is UI — a config panel and two instances of the same pin button pattern already used in ChartConfigPanel.
