/**
 * Widget data hook — fetches query results for a dashboard widget.
 *
 * The backend compiles the source workflow subgraph, applies filter overrides,
 * and executes via the query router. Frontend does NOT compile queries.
 */

import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/shared/query-engine/client";
import type { WidgetDataResponse } from "@/shared/query-engine/types";
import { useDashboardStore } from "../stores/dashboardStore";

export function useWidgetData(widgetId: string) {
  const activeFilters = useDashboardStore((s) => s.activeFilters);

  const params: Record<string, string> = {};
  if (activeFilters.length > 0) {
    params.filters = JSON.stringify(activeFilters);
  }

  return useQuery({
    queryKey: ["widgetData", widgetId, activeFilters],
    queryFn: () =>
      apiClient.get<WidgetDataResponse>(`/widgets/${widgetId}/data`, params),
    staleTime: 30_000,
  });
}
