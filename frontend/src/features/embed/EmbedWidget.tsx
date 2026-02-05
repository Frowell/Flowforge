/**
 * Embed widget renderer — fetches data via API key auth and renders the chart.
 *
 * Uses the same chart components from shared/components/charts/.
 * Supports auto-refresh via `refresh` URL parameter and filter overrides
 * via additional URL query params.
 */

import { useQuery } from "@tanstack/react-query";
import ChartRenderer from "@/shared/components/charts/ChartRenderer";
import type { WidgetDataResponse } from "@/shared/query-engine/types";
import type { ChartDataPoint } from "@/shared/components/charts/types";

interface EmbedWidgetProps {
  widgetId: string;
  apiKey: string;
  filterParams: Record<string, string>;
}

export default function EmbedWidget({ widgetId, apiKey, filterParams }: EmbedWidgetProps) {
  // Parse refresh interval from filter params (not sent to backend)
  const refreshParam = filterParams.refresh;
  const refetchInterval =
    refreshParam && Number(refreshParam) > 0 ? Number(refreshParam) : undefined;

  // Exclude reserved params from the backend request
  const queryFilters: Record<string, string> = {};
  for (const [key, value] of Object.entries(filterParams)) {
    if (key !== "refresh" && key !== "api_key" && key !== "widget_id") {
      queryFilters[key] = value;
    }
  }

  const { data, isLoading, error } = useQuery({
    queryKey: ["embed", widgetId, queryFilters],
    queryFn: async (): Promise<WidgetDataResponse> => {
      const params = new URLSearchParams({ api_key: apiKey, ...queryFilters });
      const response = await fetch(`/api/v1/embed/${widgetId}?${params}`, {
        headers: { Accept: "application/json" },
      });
      if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: response.statusText }));
        throw new Error(err.detail ?? "Failed to load widget");
      }
      return response.json();
    },
    refetchInterval,
  });

  if (isLoading) {
    return (
      <div className="h-full w-full flex items-center justify-center">
        <div className="text-white/30 text-sm">Loading...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="h-full w-full flex items-center justify-center">
        <div className="text-red-400 text-sm">
          {error instanceof Error ? error.message : "Failed to load widget"}
        </div>
      </div>
    );
  }

  if (!data) return null;

  const chartType = (data.chart_config?.chart_type as string) ?? "bar";

  return (
    <div className="h-full w-full p-2 sm:p-4 flex flex-col min-h-0">
      <div className="flex-1 min-h-0">
        <ChartRenderer
          chartType={chartType}
          config={data.chart_config ?? {}}
          data={data.rows as ChartDataPoint[]}
          interactive={false}
        />
      </div>
    </div>
  );
}
