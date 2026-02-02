/**
 * Dashboard grid page — react-grid-layout widget container.
 */

import { useParams } from "react-router-dom";
import { cn } from "@/shared/lib/cn";
import { useDashboard } from "../hooks/useDashboard";
import GlobalFilters from "./GlobalFilters";
import DashboardPicker from "./DashboardPicker";

export default function DashboardGrid() {
  const { dashboardId } = useParams<{ dashboardId: string }>();
  const { data: dashboard, isLoading } = useDashboard(dashboardId);

  if (!dashboardId) {
    return <DashboardPicker />;
  }

  if (isLoading) {
    return (
      <div className="h-screen w-screen flex items-center justify-center bg-canvas-bg">
        <div className="text-white/50 text-sm">Loading dashboard...</div>
      </div>
    );
  }

  return (
    <div className="h-screen w-screen flex flex-col bg-canvas-bg">
      <header className="h-12 bg-canvas-node border-b border-canvas-border flex items-center px-4 shrink-0 justify-between">
        <h1 className="text-sm font-semibold text-white">{dashboard?.name ?? "Dashboard"}</h1>
        <GlobalFilters />
      </header>

      <div className="flex-1 p-4 overflow-auto">
        {/* TODO: Render widgets with react-grid-layout */}
        <div className="text-white/30 text-sm text-center py-12">
          No widgets yet. Pin output nodes from the canvas to add widgets.
        </div>
      </div>
    </div>
  );
}
