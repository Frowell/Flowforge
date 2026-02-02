/**
 * Embed widget renderer — fetches data via API key auth and renders the chart.
 *
 * Uses the same chart components from shared/components/charts/.
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
  const { data, isLoading, error } = useQuery({
    queryKey: ["embed", widgetId, filterParams],
    queryFn: async (): Promise<WidgetDataResponse> => {
      const params = new URLSearchParams({ api_key: apiKey, ...filterParams });
      const response = await fetch(`/api/v1/embed/${widgetId}?${params}`, {
        headers: { Accept: "application/json" },
      });
      if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: response.statusText }));
        throw new Error(err.detail ?? "Failed to load widget");
      }
      return response.json();
    },
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
    <div className="h-full w-full p-4">
      <ChartRenderer
        chartType={chartType}
        config={data.chart_config ?? {}}
        data={data.rows as ChartDataPoint[]}
        interactive={false}
      />
    </div>
  );
}
