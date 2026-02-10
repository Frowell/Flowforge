/**
 * Workflow list + CRUD — shown when no workflow is selected.
 */

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useWorkflowList, useSaveWorkflow, useDeleteWorkflow } from "../hooks/useWorkflow";
import { useWorkflowStore } from "../stores/workflowStore";

export default function WorkflowPicker() {
  const { data, isLoading } = useWorkflowList();
  const saveWorkflow = useSaveWorkflow();
  const deleteWorkflow = useDeleteWorkflow();
  const clearStore = useWorkflowStore((s) => s.clear);
  const navigate = useNavigate();
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");

  const handleCreate = () => {
    const name = newName.trim() || "Untitled Workflow";
    clearStore();
    saveWorkflow.mutate(
      { name },
      {
        onSuccess: (w) => {
          setShowCreate(false);
          setNewName("");
          navigate(`/canvas/${w.id}`);
        },
      },
    );
  };

  const handleDelete = (e: React.MouseEvent, workflowId: string) => {
    e.stopPropagation();
    if (confirm("Delete this workflow?")) {
      deleteWorkflow.mutate(workflowId);
    }
  };

  return (
    <div className="h-[calc(100vh-3rem)] w-screen bg-canvas-bg flex flex-col">
      <div className="h-10 bg-canvas-bg border-b border-canvas-border flex items-center px-4 shrink-0 justify-end">
        <button
          onClick={() => setShowCreate(true)}
          className="px-3 py-1 text-xs bg-canvas-accent text-white rounded hover:opacity-80"
        >
          New Workflow
        </button>
      </div>

      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-canvas-node border border-canvas-border rounded-lg p-4 w-80">
            <h3 className="text-sm font-medium text-white mb-3">
              Create Workflow
            </h3>
            <input
              autoFocus
              type="text"
              placeholder="Workflow name"
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
                disabled={saveWorkflow.isPending}
                className="px-3 py-1 text-xs bg-canvas-accent text-white rounded hover:opacity-80 disabled:opacity-50"
              >
                {saveWorkflow.isPending ? "Creating..." : "Create"}
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="flex-1 p-4 overflow-auto">
        {isLoading && <div className="text-white/50 text-sm">Loading...</div>}
        {data?.items.length === 0 && (
          <div className="text-white/30 text-sm text-center py-12">
            No workflows yet. Create one to get started.
          </div>
        )}
        <div className="grid grid-cols-3 gap-4">
          {data?.items.map((w) => (
            <div
              key={w.id}
              onClick={() => navigate(`/canvas/${w.id}`)}
              className="bg-canvas-node border border-canvas-border rounded-lg p-4 text-left hover:border-canvas-accent group relative cursor-pointer"
            >
              <div className="text-sm font-medium text-white">{w.name}</div>
              <div className="text-xs text-white/40 mt-1">{w.description ?? "No description"}</div>
              <div className="text-xs text-white/30 mt-2">
                Updated {new Date(w.updated_at).toLocaleDateString()}
              </div>
              <button
                onClick={(e) => handleDelete(e, w.id)}
                className="absolute top-2 right-2 text-white/20 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity text-xs"
              >
                Delete
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
