/**
 * Dashboard list + CRUD — shown when no dashboard is selected.
 */

import { useNavigate } from "react-router-dom";
import { useDashboardList, useCreateDashboard } from "../hooks/useDashboard";

export default function DashboardPicker() {
  const { data, isLoading } = useDashboardList();
  const createDashboard = useCreateDashboard();
  const navigate = useNavigate();

  return (
    <div className="h-screen w-screen bg-canvas-bg flex flex-col">
      <header className="h-12 bg-canvas-node border-b border-canvas-border flex items-center px-4 shrink-0 justify-between">
        <h1 className="text-sm font-semibold text-white">Dashboards</h1>
        <button
          onClick={() =>
            createDashboard.mutate(
              { name: "New Dashboard" },
              { onSuccess: (d) => navigate(`/dashboards/${d.id}`) },
            )
          }
          className="px-3 py-1 text-xs bg-canvas-accent text-white rounded hover:opacity-80"
        >
          New Dashboard
        </button>
      </header>

      <div className="flex-1 p-4">
        {isLoading && <div className="text-white/50 text-sm">Loading...</div>}
        {data?.items.length === 0 && (
          <div className="text-white/30 text-sm text-center py-12">
            No dashboards yet. Create one to get started.
          </div>
        )}
        <div className="grid grid-cols-3 gap-4">
          {data?.items.map((d) => (
            <button
              key={d.id}
              onClick={() => navigate(`/dashboards/${d.id}`)}
              className="bg-canvas-node border border-canvas-border rounded-lg p-4 text-left hover:border-canvas-accent"
            >
              <div className="text-sm font-medium text-white">{d.name}</div>
              <div className="text-xs text-white/40 mt-1">{d.description ?? "No description"}</div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
