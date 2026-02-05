/**
 * Dashboard grid page — react-grid-layout widget container.
 *
 * Supports drill-down filters, URL state sync, and copy-link sharing.
 */

import { useCallback, useEffect, useMemo, useRef } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { Responsive, WidthProvider } from "react-grid-layout";
import "react-grid-layout/css/styles.css";
import "react-resizable/css/styles.css";

import { useDashboard } from "../hooks/useDashboard";
import { useDashboardWidgets } from "../hooks/useDashboardWidgets";
import { useUpdateWidget } from "../hooks/useWidget";
import { useDashboardStore } from "../stores/dashboardStore";
import { useToastStore } from "@/shared/components/Toast";
import GlobalFilters from "./GlobalFilters";
import DashboardPicker from "./DashboardPicker";
import DrillDownBar from "./DrillDownBar";
import WidgetCard from "./WidgetCard";

const ResponsiveGridLayout = WidthProvider(Responsive);

export default function DashboardGrid() {
  const { dashboardId } = useParams<{ dashboardId: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const { data: dashboard, isLoading: dashLoading } = useDashboard(dashboardId);
  const { data: widgets, isLoading: widgetsLoading } = useDashboardWidgets(dashboardId);
  const isEditing = useDashboardStore((s) => s.isEditing);
  const setEditing = useDashboardStore((s) => s.setEditing);
  const drillDownFilters = useDashboardStore((s) => s.drillDownFilters);
  const addDrillDownFilter = useDashboardStore((s) => s.addDrillDownFilter);
  const clearDrillDownFilters = useDashboardStore((s) => s.clearDrillDownFilters);
  const addToast = useToastStore((s) => s.addToast);
  const updateWidget = useUpdateWidget();

  const debounceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const initializedFromUrl = useRef(false);

  // On mount: parse drill-down filters from URL
  useEffect(() => {
    if (initializedFromUrl.current) return;
    initializedFromUrl.current = true;

    const drilldownParam = searchParams.get("drilldown");
    if (drilldownParam) {
      try {
        const parsed = JSON.parse(drilldownParam);
        if (Array.isArray(parsed)) {
          clearDrillDownFilters();
          for (const f of parsed) {
            if (f.widgetId && f.column && f.value !== undefined) {
              addDrillDownFilter(f);
            }
          }
        }
      } catch {
        // Ignore malformed URL params
      }
    }
  }, [searchParams, addDrillDownFilter, clearDrillDownFilters]);

  // Sync drill-down filters to URL
  useEffect(() => {
    if (!initializedFromUrl.current) return;

    const newParams = new URLSearchParams(searchParams);
    if (drillDownFilters.length > 0) {
      newParams.set("drilldown", JSON.stringify(drillDownFilters));
    } else {
      newParams.delete("drilldown");
    }

    const currentStr = searchParams.toString();
    const newStr = newParams.toString();
    if (currentStr !== newStr) {
      setSearchParams(newParams, { replace: true });
    }
  }, [drillDownFilters, searchParams, setSearchParams]);

  const handleDrillDown = useCallback(
    (widgetId: string, filters: Record<string, unknown>) => {
      for (const [column, value] of Object.entries(filters)) {
        addDrillDownFilter({ widgetId, column, value });
      }
    },
    [addDrillDownFilter],
  );

  const handleCopyLink = useCallback(() => {
    navigator.clipboard.writeText(window.location.href).then(() => {
      addToast("Dashboard link copied to clipboard", "success");
    });
  }, [addToast]);

  const layout = useMemo(
    () =>
      (widgets ?? []).map((w) => ({
        i: w.id,
        x: w.layout?.x ?? 0,
        y: w.layout?.y ?? 0,
        w: w.layout?.w ?? 6,
        h: w.layout?.h ?? 4,
      })),
    [widgets],
  );

  const handleLayoutChange = useCallback(
    (newLayout: Array<{ i: string; x: number; y: number; w: number; h: number }>) => {
      if (!isEditing) return;
      if (debounceTimer.current) clearTimeout(debounceTimer.current);
      debounceTimer.current = setTimeout(() => {
        for (const item of newLayout) {
          const widget = widgets?.find((w) => w.id === item.i);
          if (!widget) continue;
          const prev = widget.layout;
          if (prev.x !== item.x || prev.y !== item.y || prev.w !== item.w || prev.h !== item.h) {
            updateWidget.mutate({
              widgetId: item.i,
              layout: { x: item.x, y: item.y, w: item.w, h: item.h },
            });
          }
        }
      }, 500);
    },
    [isEditing, widgets, updateWidget],
  );

  if (!dashboardId) {
    return <DashboardPicker />;
  }

  if (dashLoading || widgetsLoading) {
    return (
      <div className="h-[calc(100vh-3rem)] w-screen flex items-center justify-center bg-canvas-bg">
        <div className="text-white/50 text-sm">Loading dashboard...</div>
      </div>
    );
  }

  const hasWidgets = widgets && widgets.length > 0;

  return (
    <div className="h-[calc(100vh-3rem)] w-screen flex flex-col bg-canvas-bg">
      <div className="h-10 bg-canvas-bg border-b border-canvas-border flex items-center px-4 shrink-0 justify-between">
        <h1 className="text-sm font-medium text-white/80">{dashboard?.name ?? "Dashboard"}</h1>
        <div className="flex items-center gap-3">
          <GlobalFilters />
          <button
            onClick={handleCopyLink}
            className="text-xs px-2 py-1 rounded text-white/40 hover:text-white border border-white/10"
          >
            Copy link
          </button>
          <button
            onClick={() => setEditing(!isEditing)}
            className={`text-xs px-2 py-1 rounded ${
              isEditing
                ? "bg-canvas-accent text-white"
                : "text-white/40 hover:text-white border border-white/10"
            }`}
          >
            {isEditing ? "Done Editing" : "Edit Layout"}
          </button>
        </div>
      </div>

      <DrillDownBar />

      <div className="flex-1 p-4 overflow-auto">
        {!hasWidgets && (
          <div className="text-white/30 text-sm text-center py-12">
            No widgets yet. Pin output nodes from the canvas to add widgets.
          </div>
        )}
        {hasWidgets && (
          <ResponsiveGridLayout
            layouts={{ lg: layout }}
            breakpoints={{ lg: 1200, md: 996, sm: 768, xs: 480 }}
            cols={{ lg: 12, md: 10, sm: 6, xs: 4 }}
            rowHeight={80}
            isDraggable={isEditing}
            isResizable={isEditing}
            onLayoutChange={handleLayoutChange}
            draggableHandle=".widget-drag-handle"
          >
            {widgets!.map((widget) => (
              <div key={widget.id}>
                <WidgetCard
                  widget={widget}
                  className="h-full"
                  onDrillDown={(filters) => handleDrillDown(widget.id, filters)}
                />
              </div>
            ))}
          </ResponsiveGridLayout>
        )}
      </div>
    </div>
  );
}
