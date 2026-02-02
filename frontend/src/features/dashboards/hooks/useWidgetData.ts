/**
 * Widget data hook — fetches query results for a dashboard widget.
 *
 * The backend compiles the source workflow subgraph, applies filter overrides,
 * and executes via the query router. Frontend does NOT compile queries.
 */

import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/shared/query-engine/client";
import type { QueryResultResponse } from "@/shared/query-engine/types";
import { useDashboardStore } from "../stores/dashboardStore";

export function useWidgetData(widgetId: string) {
  const activeFilters = useDashboardStore((s) => s.activeFilters);

  return useQuery({
    queryKey: ["widgetData", widgetId, activeFilters],
    queryFn: () =>
      apiClient.get<QueryResultResponse>(`/api/v1/widgets/${widgetId}/data`, {
        filters: JSON.stringify(activeFilters),
      }),
    staleTime: 30_000,
  });
}
