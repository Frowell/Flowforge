/**
 * WidgetCard — wraps a shared chart component with title bar, refresh, error states.
 *
 * The chart inside is imported from shared/components/charts/, never duplicated.
 */

import { cn } from "@/shared/lib/cn";
import ChartRenderer from "@/shared/components/charts/ChartRenderer";
import { useWidgetData } from "../hooks/useWidgetData";
import type { WidgetResponse } from "@/shared/query-engine/types";
import type { ChartDataPoint } from "@/shared/components/charts/types";

interface WidgetCardProps {
  widget: WidgetResponse;
  className?: string;
}

export default function WidgetCard({ widget, className }: WidgetCardProps) {
  const { data, isLoading, error, refetch } = useWidgetData(widget.id);

  const chartType = (data?.chart_config?.chart_type as string) ?? "bar";
  const chartConfig = data?.chart_config ?? {};

  return (
    <div className={cn("bg-canvas-node rounded-lg border border-canvas-border flex flex-col overflow-hidden", className)}>
      {/* Title bar — also serves as drag handle in edit mode */}
      <div className="widget-drag-handle flex items-center justify-between px-3 py-2 border-b border-canvas-border cursor-move">
        <span className="text-xs font-medium text-white truncate">
          {widget.title ?? "Widget"}
        </span>
        <button
          onClick={() => refetch()}
          className="text-white/30 hover:text-white text-xs"
        >
          Refresh
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 p-2 min-h-[150px]">
        {isLoading && (
          <div className="w-full h-full animate-pulse bg-white/5 rounded" />
        )}

        {error && (
          <div className="w-full h-full flex items-center justify-center">
            <div className="text-red-400 text-xs text-center">
              {error instanceof Error ? error.message : "Failed to load widget data"}
            </div>
          </div>
        )}

        {data && !isLoading && !error && (
          <ChartRenderer
            chartType={chartType}
            config={chartConfig}
            data={data.rows as ChartDataPoint[]}
            interactive
          />
        )}
      </div>
    </div>
  );
}
