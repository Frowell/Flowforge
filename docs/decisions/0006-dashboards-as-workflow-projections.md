# 0006: Dashboards Are Projections of Workflows, Not Independent Queries

**Status:** Accepted
**Date:** 2025-11-01
**Deciders:** Architecture team

## Context

Dashboard widgets need to display data. Two approaches:

1. **Widgets reference workflow output nodes** — a widget points to a specific node in a workflow and executes its subgraph
2. **Widgets have independent query definitions** — each widget has its own SQL/configuration separate from any workflow

## Decision

Dashboards are **projections of workflows**. A widget record stores `{ workflow_id, output_node_id, dashboard_id, layout, config_overrides }`. To render a widget, the system executes the workflow subgraph up to the pinned output node.

Widgets are references to canvas output nodes — not copies. If the workflow changes, the widget output changes. The same chart component renders in all three contexts (canvas preview, dashboard widget, embed iframe).

## Alternatives Considered

**Independent widget queries**: Each widget has its own SQL definition, decoupled from workflows. Simpler mental model but creates two parallel systems for defining data transformations — the canvas and the widget editor. Users would need to learn both.

**Snapshot-on-pin (copy the subgraph)**: When pinning, copy the relevant subgraph into the widget. Decouples the widget from future workflow changes. Rejected because it creates drift — the widget shows stale logic while the workflow has moved on, with no easy way to sync.

**Materialized result sets**: Pre-compute widget data on a schedule and store results. Good for performance but adds a storage and scheduling layer, and live data widgets can't work this way.

## Consequences

- **Positive**: Single source of truth. Change the workflow, all widgets update.
- **Positive**: One chart component library, used everywhere. No per-mode variants.
- **Positive**: Users build logic once on the canvas, then expose it multiple ways.
- **Negative**: Deleting or restructuring a workflow can break widgets. Orphaned widgets need explicit error states.
- **Negative**: Widget rendering depends on workflow compilation — if the compiler has a bug, all widgets for that workflow break simultaneously.
