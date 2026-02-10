/**
 * Widget data hook — fetches query results for a dashboard widget.
 *
 * The backend compiles the source workflow subgraph, applies filter overrides,
 * and executes via the query router. Frontend does NOT compile queries.
 *
 * Supports auto-refresh via interval or live data via WebSocket.
 * Includes drill-down filters in query params for cache invalidation.
 * Supports pagination via offset/limit params.
 *
 * Live mode pushes row data via WebSocket and merges directly into the
 * TanStack Query cache (setQueryData) instead of invalidate-and-refetch.
 * A 30-second refetchInterval backstop corrects any drift.
 */

import { useEffect, useCallback } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/shared/query-engine/client";
import type {
  WidgetDataResponse,
  TableRowsMessage,
} from "@/shared/query-engine/types";
import { wsManager } from "@/shared/websocket/manager";
import { useDashboardStore } from "../stores/dashboardStore";

interface UseWidgetDataOptions {
  refreshInterval?: number | "live";
  offset?: number;
  limit?: number;
}

interface FilterValue {
  column: string;
  type: string;
  value: unknown;
}

/**
 * Client-side filter matching for pushed rows.
 * Supports "equals" and "in" filter types (covers symbol/side filters).
 * Returns true if the row passes all filters.
 */
function applyClientFilters(
  row: Record<string, unknown>,
  filters: FilterValue[],
): boolean {
  for (const filter of filters) {
    const cellValue = row[filter.column];
    if (filter.type === "equals" || filter.type === "drilldown") {
      if (cellValue !== filter.value) return false;
    } else if (filter.type === "in") {
      if (!Array.isArray(filter.value) || !filter.value.includes(cellValue))
        return false;
    }
    // Other filter types (range, date_range, text) are too complex for
    // client-side matching — the 30s backstop refetch will correct.
  }
  return true;
}

export function useWidgetData(widgetId: string, options?: UseWidgetDataOptions) {
  const activeFilters = useDashboardStore((s) => s.activeFilters);
  const drillDownFilters = useDashboardStore((s) => s.drillDownFilters);
  const queryClient = useQueryClient();
  const refreshInterval = options?.refreshInterval;
  const offset = options?.offset ?? 0;
  const limit = options?.limit ?? 1000;

  const params: Record<string, string> = {};

  // Combine active filters and drill-down filters
  const allFilters: FilterValue[] = [
    ...activeFilters,
    ...drillDownFilters.map((f) => ({
      column: f.column,
      type: "drilldown",
      value: f.value,
    })),
  ];

  if (allFilters.length > 0) {
    params.filters = JSON.stringify(allFilters);
  }

  params.offset = String(offset);
  params.limit = String(limit);

  const queryKey = ["widgetData", widgetId, activeFilters, drillDownFilters, offset, limit];

  // Merge pushed rows into cache instead of refetching
  const handleTableRows = useCallback(
    (data: unknown) => {
      // Only merge when viewing page 0 — other pages stay stable
      if (offset !== 0) return;

      const msg = data as TableRowsMessage;
      const msgColNames = msg.columns.map((c) => c.name).sort().join(",");

      queryClient.setQueryData<WidgetDataResponse>(queryKey, (prev) => {
        if (!prev) return prev;

        // Only merge if pushed columns match the widget's schema —
        // prevents raw_quotes rows merging into a raw_trades widget, etc.
        const prevColNames = prev.columns.map((c) => c.name).sort().join(",");
        if (msgColNames !== prevColNames) return prev;

        // Filter new rows client-side
        const matchingRows = allFilters.length > 0
          ? msg.rows.filter((row) => applyClientFilters(row, allFilters))
          : msg.rows;

        if (matchingRows.length === 0) return prev;

        // Prepend new rows and purge beyond limit to cap at 1k rows
        const merged = [...matchingRows, ...prev.rows].slice(0, limit);
        return {
          ...prev,
          rows: merged,
          total_rows: Math.min(prev.total_rows + matchingRows.length, limit),
        };
      });
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [widgetId, offset, limit, queryClient, JSON.stringify(allFilters)],
  );

  // Subscribe to live data channel when refreshInterval is "live"
  useEffect(() => {
    if (refreshInterval !== "live") return;

    // Ensure WebSocket is connected before subscribing
    wsManager.connect();

    const channel = `widget:${widgetId}`;
    wsManager.subscribeChannel(channel);

    const unsubscribeLive = wsManager.subscribe("live_data", (data) => {
      const msg = data as { widget_id?: string };
      if (msg.widget_id === widgetId) {
        queryClient.invalidateQueries({ queryKey: ["widgetData", widgetId] });
      }
    });

    // Listen for table_rows broadcasts with pushed row data
    const unsubscribeTableRows = wsManager.subscribe(
      "table_rows",
      handleTableRows,
    );

    return () => {
      wsManager.unsubscribeChannel(channel);
      unsubscribeLive();
      unsubscribeTableRows();
    };
  }, [widgetId, refreshInterval, queryClient, handleTableRows]);

  // Determine refetch interval:
  // - numeric → user-specified polling interval
  // - "live" → 30s backstop to correct any drift from approximate client-side filtering
  // - undefined → no refetch
  let computedRefetchInterval: number | undefined;
  if (typeof refreshInterval === "number") {
    computedRefetchInterval = refreshInterval;
  } else if (refreshInterval === "live") {
    computedRefetchInterval = 30_000;
  }

  return useQuery({
    queryKey,
    queryFn: () => apiClient.get<WidgetDataResponse>(`/api/v1/widgets/${widgetId}/data`, params),
    staleTime: 30_000,
    refetchInterval: computedRefetchInterval,
  });
}
