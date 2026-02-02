/**
 * Global filters hook — manages dashboard-level filter state.
 *
 * Only offers columns present in ALL widget schemas (intersection).
 */

import { useDashboardStore } from "../stores/dashboardStore";

export function useGlobalFilters() {
  const activeFilters = useDashboardStore((s) => s.activeFilters);
  const setFilter = useDashboardStore((s) => s.setFilter);
  const clearFilters = useDashboardStore((s) => s.clearFilters);

  // TODO: Compute intersection of available columns across all widget schemas
  // to determine which columns can be offered as global filters

  return {
    activeFilters,
    setFilter,
    clearFilters,
  };
}
