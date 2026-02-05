/**
 * Hook to fetch all widgets for a dashboard.
 */

import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/shared/query-engine/client";
import type { WidgetResponse } from "@/shared/query-engine/types";

export const DASHBOARD_WIDGETS_KEY = ["dashboardWidgets"] as const;

export function useDashboardWidgets(dashboardId: string | undefined) {
  return useQuery({
    queryKey: [...DASHBOARD_WIDGETS_KEY, dashboardId],
    queryFn: () => apiClient.get<WidgetResponse[]>(`/api/v1/dashboards/${dashboardId}/widgets`),
    enabled: !!dashboardId,
  });
}
