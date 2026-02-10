/**
 * Global filters hook — manages dashboard-level filter state.
 *
 * Computes available columns by intersecting columns from all widget data
 * responses in the TanStack Query cache.
 */

import { useMemo } from "react";
import { useParams } from "react-router-dom";
import { useQueries } from "@tanstack/react-query";
import { apiClient } from "@/shared/query-engine/client";
import type { WidgetDataResponse } from "@/shared/query-engine/types";
import { useDashboardStore } from "../stores/dashboardStore";
import { useDashboardWidgets } from "./useDashboardWidgets";

export interface AvailableColumn {
  name: string;
  dtype: string;
  suggestedFilterType: "date_range" | "text";
}

export function useGlobalFilters() {
  const activeFilters = useDashboardStore((s) => s.activeFilters);
  const setFilter = useDashboardStore((s) => s.setFilter);
  const clearFilters = useDashboardStore((s) => s.clearFilters);

  const { dashboardId } = useParams<{ dashboardId: string }>();
  const { data: widgets } = useDashboardWidgets(dashboardId);
  const widgetIds = useMemo(() => (widgets ?? []).map((w) => w.id), [widgets]);

  // Read widget data from cache — don't trigger new fetches
  const widgetQueries = useQueries({
    queries: widgetIds.map((id) => ({
      queryKey: ["widgetData", id],
      queryFn: () => apiClient.get<WidgetDataResponse>(`/api/v1/widgets/${id}/data`),
      staleTime: 30_000,
      enabled: false,
    })),
  });

  const availableColumns = useMemo<AvailableColumn[]>(() => {
    const loaded = widgetQueries.filter((q) => q.data?.columns).map((q) => q.data!.columns);

    const firstCols = loaded[0];
    if (!firstCols) return [];

    // Intersection: columns present in ALL widget responses
    const first = new Set(firstCols.map((c) => c.name));
    for (const cols of loaded.slice(1)) {
      const names = new Set(cols.map((c) => c.name));
      for (const name of first) {
        if (!names.has(name)) first.delete(name);
      }
    }

    return firstCols
      .filter((c) => first.has(c.name))
      .map((c) => ({
        name: c.name,
        dtype: c.dtype,
        suggestedFilterType: c.dtype === "datetime" ? ("date_range" as const) : ("text" as const),
      }));
  }, [widgetQueries]);

  return {
    activeFilters,
    setFilter,
    clearFilters,
    availableColumns,
  };
}
