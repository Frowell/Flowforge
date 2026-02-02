/**
 * Dashboard CRUD hook.
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/shared/query-engine/client";
import type { DashboardResponse, PaginatedResponse } from "@/shared/query-engine/types";

const DASHBOARDS_KEY = ["dashboards"] as const;

export function useDashboardList(page = 1, pageSize = 20) {
  return useQuery({
    queryKey: [...DASHBOARDS_KEY, page, pageSize],
    queryFn: () =>
      apiClient.get<PaginatedResponse<DashboardResponse>>(
        `/api/v1/dashboards?page=${page}&page_size=${pageSize}`,
      ),
  });
}

export function useDashboard(dashboardId: string | undefined) {
  return useQuery({
    queryKey: [...DASHBOARDS_KEY, dashboardId],
    queryFn: () => apiClient.get<DashboardResponse>(`/api/v1/dashboards/${dashboardId}`),
    enabled: !!dashboardId,
  });
}

export function useCreateDashboard() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { name: string; description?: string }) =>
      apiClient.post<DashboardResponse>("/api/v1/dashboards", data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: DASHBOARDS_KEY }),
  });
}
