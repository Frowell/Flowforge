/**
 * Embed widget renderer — fetches data via API key auth and renders the chart.
 *
 * Uses the same chart components from shared/components/charts/.
 */

import { useQuery } from "@tanstack/react-query";
import type { QueryResultResponse } from "@/shared/query-engine/types";

interface EmbedWidgetProps {
  widgetId: string;
  apiKey: string;
  filterParams: Record<string, string>;
}

export default function EmbedWidget({ widgetId, apiKey, filterParams }: EmbedWidgetProps) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["embed", widgetId, filterParams],
    queryFn: async (): Promise<QueryResultResponse> => {
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

  // TODO: Determine chart type from widget config and render the appropriate
  // shared chart component via React.lazy for code splitting
  return (
    <div className="h-full w-full p-4">
      <div className="text-white/30 text-sm text-center">
        Widget loaded — {data?.total_rows ?? 0} rows
      </div>
    </div>
  );
}
