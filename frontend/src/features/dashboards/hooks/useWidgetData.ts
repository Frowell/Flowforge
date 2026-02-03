/**
 * Widget data hook — fetches query results for a dashboard widget.
 *
 * The backend compiles the source workflow subgraph, applies filter overrides,
 * and executes via the query router. Frontend does NOT compile queries.
 *
 * Supports auto-refresh via interval or live data via WebSocket.
 */

import { useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/shared/query-engine/client";
import type { WidgetDataResponse } from "@/shared/query-engine/types";
import { wsManager } from "@/shared/websocket/manager";
import { useDashboardStore } from "../stores/dashboardStore";

interface UseWidgetDataOptions {
  refreshInterval?: number | "live";
}

export function useWidgetData(widgetId: string, options?: UseWidgetDataOptions) {
  const activeFilters = useDashboardStore((s) => s.activeFilters);
  const queryClient = useQueryClient();
  const refreshInterval = options?.refreshInterval;

  const params: Record<string, string> = {};
  if (activeFilters.length > 0) {
    params.filters = JSON.stringify(activeFilters);
  }

  // Subscribe to live data channel when refreshInterval is "live"
  useEffect(() => {
    if (refreshInterval !== "live") return;

    const channel = `widget:${widgetId}`;
    wsManager.subscribeChannel(channel);

    const unsubscribe = wsManager.subscribe("live_data", (data) => {
      const msg = data as { widget_id?: string };
      if (msg.widget_id === widgetId) {
        queryClient.invalidateQueries({ queryKey: ["widgetData", widgetId] });
      }
    });

    return () => {
      wsManager.unsubscribeChannel(channel);
      unsubscribe();
    };
  }, [widgetId, refreshInterval, queryClient]);

  return useQuery({
    queryKey: ["widgetData", widgetId, activeFilters],
    queryFn: () =>
      apiClient.get<WidgetDataResponse>(`/widgets/${widgetId}/data`, params),
    staleTime: 30_000,
    refetchInterval:
      typeof refreshInterval === "number" ? refreshInterval : undefined,
  });
}
