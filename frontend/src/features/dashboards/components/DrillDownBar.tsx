/**
 * Drill-down filter bar — shows active drill-down filters as removable chips.
 */

import { useDashboardStore } from "../stores/dashboardStore";

export default function DrillDownBar() {
  const drillDownFilters = useDashboardStore((s) => s.drillDownFilters);
  const removeDrillDownFilter = useDashboardStore((s) => s.removeDrillDownFilter);
  const clearDrillDownFilters = useDashboardStore((s) => s.clearDrillDownFilters);

  if (drillDownFilters.length === 0) return null;

  return (
    <div className="flex items-center gap-2 px-4 py-2 bg-canvas-node/50 border-b border-canvas-border">
      <span className="text-xs text-white/40 shrink-0">Drill-down:</span>
      <div className="flex items-center gap-1.5 flex-wrap">
        {drillDownFilters.map((filter) => (
          <span
            key={`${filter.widgetId}-${filter.column}`}
            className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-canvas-accent/20 border border-canvas-accent/30 text-xs text-canvas-accent"
          >
            <span className="text-white/50">{filter.column}:</span>
            <span>{String(filter.value)}</span>
            <button
              onClick={() => removeDrillDownFilter(filter.widgetId, filter.column)}
              className="text-white/40 hover:text-white ml-0.5"
            >
              &times;
            </button>
          </span>
        ))}
      </div>
      <button
        onClick={clearDrillDownFilters}
        className="text-xs text-white/30 hover:text-white ml-auto shrink-0"
      >
        Clear all
      </button>
    </div>
  );
}
