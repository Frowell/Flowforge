/**
 * Workflow list + CRUD — shown when no workflow is selected.
 */

import { useNavigate } from "react-router-dom";
import { useWorkflowList, useSaveWorkflow, useDeleteWorkflow } from "../hooks/useWorkflow";
import { useWorkflowStore } from "../stores/workflowStore";

export default function WorkflowPicker() {
  const { data, isLoading } = useWorkflowList();
  const saveWorkflow = useSaveWorkflow();
  const deleteWorkflow = useDeleteWorkflow();
  const clearStore = useWorkflowStore((s) => s.clear);
  const navigate = useNavigate();

  const handleCreate = () => {
    clearStore();
    saveWorkflow.mutate(
      { name: "Untitled Workflow" },
      { onSuccess: (w) => navigate(`/canvas/${w.id}`) },
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
          onClick={handleCreate}
          disabled={saveWorkflow.isPending}
          className="px-3 py-1 text-xs bg-canvas-accent text-white rounded hover:opacity-80 disabled:opacity-50"
        >
          {saveWorkflow.isPending ? "Creating..." : "New Workflow"}
        </button>
      </div>

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
