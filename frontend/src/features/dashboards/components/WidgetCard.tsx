/**
 * WidgetCard — wraps a shared chart component with title bar, refresh, error states.
 *
 * The chart inside is imported from shared/components/charts/, never duplicated.
 */

import { useEffect, useRef } from "react";
import { cn } from "@/shared/lib/cn";
import ChartRenderer from "@/shared/components/charts/ChartRenderer";
import { useToastStore } from "@/shared/components/Toast";
import { useWidgetData } from "../hooks/useWidgetData";
import WidgetSettingsMenu from "./WidgetSettingsMenu";
import type { WidgetResponse } from "@/shared/query-engine/types";
import type { ChartDataPoint } from "@/shared/components/charts/types";
import { APIError } from "@/shared/query-engine/client";

interface WidgetCardProps {
  widget: WidgetResponse;
  className?: string;
  onUnpin?: (widgetId: string) => void;
}

function isOrphanedError(error: unknown): boolean {
  if (error instanceof APIError) {
    if (error.status === 404) return true;
    if (error.message.toLowerCase().includes("workflow_not_found")) return true;
  }
  return false;
}

function isTransientError(error: unknown): boolean {
  if (error instanceof APIError) {
    return error.status >= 500 || error.status === 0;
  }
  if (error instanceof TypeError) {
    // Network errors
    return true;
  }
  return false;
}

export default function WidgetCard({ widget, className, onUnpin }: WidgetCardProps) {
  // auto_refresh_interval: null=manual, -1=live (WebSocket), >0=polling interval in ms
  const ari = widget.auto_refresh_interval;
  const refreshInterval: number | "live" | undefined =
    ari === -1 ? "live" : ari != null && ari > 0 ? ari : undefined;

  const { data, isLoading, error, refetch, isFetching } = useWidgetData(widget.id, {
    refreshInterval,
  });

  const chartType = (data?.chart_config?.chart_type as string) ?? "bar";
  const chartConfig = data?.chart_config ?? {};
  const isLive = refreshInterval === "live" || typeof refreshInterval === "number";
  const addToast = useToastStore((s) => s.addToast);
  const prevErrorRef = useRef<unknown>(null);

  // Show toast for transient errors (in addition to inline display)
  useEffect(() => {
    if (error && isTransientError(error) && error !== prevErrorRef.current) {
      const msg = error instanceof Error ? error.message : "Network error";
      addToast(`Widget "${widget.title ?? "Widget"}": ${msg}`, "error");
    }
    prevErrorRef.current = error;
  }, [error, addToast, widget.title]);

  return (
    <div
      className={cn(
        "bg-canvas-node rounded-lg border border-canvas-border flex flex-col overflow-hidden",
        className,
      )}
    >
      {/* Title bar — also serves as drag handle in edit mode */}
      <div className="widget-drag-handle flex items-center justify-between px-3 py-2 border-b border-canvas-border cursor-move">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-xs font-medium text-white truncate">
            {widget.title ?? "Widget"}
          </span>
          {isLive && (
            <span className="flex items-center gap-1 shrink-0">
              <span
                className={cn(
                  "inline-block w-1.5 h-1.5 rounded-full",
                  isFetching ? "bg-yellow-400 animate-pulse" : "bg-emerald-400",
                )}
              />
              <span className="text-[10px] text-white/50 uppercase tracking-wider">
                {refreshInterval === "live" ? "Live" : "Auto"}
              </span>
            </span>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <WidgetSettingsMenu widgetId={widget.id} currentInterval={widget.auto_refresh_interval} />
          <button onClick={() => refetch()} className="text-white/30 hover:text-white text-xs">
            Refresh
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 p-2 min-h-[150px]">
        {/* Loading state */}
        {isLoading && <div className="w-full h-full animate-pulse bg-white/5 rounded" />}

        {/* Orphaned widget — source workflow deleted */}
        {error && isOrphanedError(error) && (
          <div className="w-full h-full flex flex-col items-center justify-center gap-3">
            <div className="text-red-400/80 text-xs text-center">Source workflow was deleted</div>
            <p className="text-white/30 text-[10px] text-center">
              The workflow this widget references no longer exists.
            </p>
            {onUnpin && (
              <button
                onClick={() => onUnpin(widget.id)}
                className="px-3 py-1 text-xs rounded bg-red-500/20 text-red-300 hover:bg-red-500/30 transition-colors"
              >
                Unpin widget
              </button>
            )}
          </div>
        )}

        {/* Transient error — retry available */}
        {error && !isOrphanedError(error) && isTransientError(error) && (
          <div className="w-full h-full flex flex-col items-center justify-center gap-3">
            <div className="text-yellow-400/80 text-xs text-center">Failed to load data</div>
            <p className="text-white/30 text-[10px] text-center">
              {error instanceof Error ? error.message : "Network error"}
            </p>
            <button
              onClick={() => refetch()}
              className="px-3 py-1 text-xs rounded bg-white/10 text-white/60 hover:bg-white/20 transition-colors"
            >
              Retry
            </button>
          </div>
        )}

        {/* Other errors */}
        {error && !isOrphanedError(error) && !isTransientError(error) && (
          <div className="w-full h-full flex items-center justify-center">
            <div className="text-red-400 text-xs text-center">
              {error instanceof Error ? error.message : "Failed to load widget data"}
            </div>
          </div>
        )}

        {/* Stale data indicator while refetching */}
        {data && isFetching && !isLoading && (
          <div className="absolute top-10 right-2 text-[10px] text-white/20">Updating...</div>
        )}

        {data && !isLoading && !error && (
          <ChartRenderer
            chartType={chartType}
            config={chartConfig}
            data={data.rows as ChartDataPoint[]}
            columns={data.columns}
            interactive
          />
        )}
      </div>
    </div>
  );
}
