/**
 * Widget mutation hooks — create, update, delete.
 *
 * Invalidates dashboardWidgets cache on success.
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/shared/query-engine/client";
import type { WidgetResponse } from "@/shared/query-engine/types";
import { DASHBOARD_WIDGETS_KEY } from "./useDashboardWidgets";

interface CreateWidgetParams {
  dashboard_id: string;
  source_workflow_id: string;
  source_node_id: string;
  title?: string;
  layout?: { x: number; y: number; w: number; h: number };
  config_overrides?: Record<string, unknown>;
}

interface UpdateWidgetParams {
  widgetId: string;
  title?: string;
  layout?: { x: number; y: number; w: number; h: number };
  config_overrides?: Record<string, unknown>;
}

export function useCreateWidget() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (params: CreateWidgetParams) =>
      apiClient.post<WidgetResponse>("/api/v1/widgets", params),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: [...DASHBOARD_WIDGETS_KEY, variables.dashboard_id],
      });
    },
  });
}

export function useUpdateWidget() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ widgetId, ...body }: UpdateWidgetParams) =>
      apiClient.patch<WidgetResponse>(`/api/v1/widgets/${widgetId}`, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: DASHBOARD_WIDGETS_KEY });
    },
  });
}

export function useDeleteWidget() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (widgetId: string) => apiClient.delete(`/api/v1/widgets/${widgetId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: DASHBOARD_WIDGETS_KEY });
    },
  });
}
