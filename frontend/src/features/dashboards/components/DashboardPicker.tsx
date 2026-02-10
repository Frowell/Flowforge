/**
 * Dashboard list + CRUD — shown when no dashboard is selected.
 */

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useDashboardList, useCreateDashboard } from "../hooks/useDashboard";

export default function DashboardPicker() {
  const { data, isLoading } = useDashboardList();
  const createDashboard = useCreateDashboard();
  const navigate = useNavigate();
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");

  const handleCreate = () => {
    const name = newName.trim() || "New Dashboard";
    createDashboard.mutate(
      { name },
      {
        onSuccess: (d) => {
          setShowCreate(false);
          setNewName("");
          navigate(`/dashboards/${d.id}`);
        },
      },
    );
  };

  return (
    <div className="h-[calc(100vh-3rem)] w-screen bg-canvas-bg flex flex-col">
      <div className="h-10 bg-canvas-bg border-b border-canvas-border flex items-center px-4 shrink-0 justify-end">
        <button
          onClick={() => setShowCreate(true)}
          className="px-3 py-1 text-xs bg-canvas-accent text-white rounded hover:opacity-80"
        >
          New Dashboard
        </button>
      </div>

      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-canvas-node border border-canvas-border rounded-lg p-4 w-80">
            <h3 className="text-sm font-medium text-white mb-3">Create Dashboard</h3>
            <input
              autoFocus
              type="text"
              placeholder="Dashboard name"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleCreate();
                if (e.key === "Escape") setShowCreate(false);
              }}
              className="w-full px-2 py-1.5 text-sm bg-canvas-bg border border-canvas-border rounded text-white placeholder-white/30 focus:outline-none focus:border-canvas-accent"
            />
            <div className="flex justify-end gap-2 mt-3">
              <button
                onClick={() => {
                  setShowCreate(false);
                  setNewName("");
                }}
                className="px-3 py-1 text-xs text-white/60 hover:text-white"
              >
                Cancel
              </button>
              <button
                onClick={handleCreate}
                disabled={createDashboard.isPending}
                className="px-3 py-1 text-xs bg-canvas-accent text-white rounded hover:opacity-80 disabled:opacity-50"
              >
                {createDashboard.isPending ? "Creating..." : "Create"}
              </button>
            </div>
          </div>
        </div>
      )}

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
