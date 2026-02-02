/**
 * WidgetCard — wraps a shared chart component with title bar, refresh, error states.
 *
 * The chart inside is imported from shared/components/charts/, never duplicated.
 */

import { cn } from "@/shared/lib/cn";
import { useWidgetData } from "../hooks/useWidgetData";
import type { WidgetResponse } from "@/shared/query-engine/types";

interface WidgetCardProps {
  widget: WidgetResponse;
  className?: string;
}

export default function WidgetCard({ widget, className }: WidgetCardProps) {
  const { data, isLoading, error } = useWidgetData(widget.id);

  return (
    <div className={cn("bg-canvas-node rounded-lg border border-canvas-border flex flex-col overflow-hidden", className)}>
      {/* Title bar */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-canvas-border">
        <span className="text-xs font-medium text-white truncate">
          {widget.title ?? "Widget"}
        </span>
        <button className="text-white/30 hover:text-white text-xs">Refresh</button>
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
          <div className="w-full h-full">
            {/* TODO: Render appropriate shared chart component based on widget config */}
            <div className="text-white/30 text-xs text-center py-4">
              {data.total_rows} rows loaded
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
