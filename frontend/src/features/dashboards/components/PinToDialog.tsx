/**
 * Pin to Dashboard dialog — shown from canvas when pinning an output node.
 */

import { useState } from "react";
import { useDashboardList } from "../hooks/useDashboard";
import { useCreateWidget } from "../hooks/useWidget";

interface PinToDialogProps {
  workflowId: string;
  nodeId: string;
  onClose: () => void;
  onPin: (dashboardId: string) => void;
}

export default function PinToDialog({ workflowId, nodeId, onClose, onPin }: PinToDialogProps) {
  const { data } = useDashboardList();
  const createWidget = useCreateWidget();
  const [selectedDashboardId, setSelectedDashboardId] = useState<string>("");
  const [title, setTitle] = useState<string>("");

  const handlePin = () => {
    if (!selectedDashboardId) return;
    createWidget.mutate(
      {
        dashboard_id: selectedDashboardId,
        source_workflow_id: workflowId,
        source_node_id: nodeId,
        title: title || undefined,
      },
      {
        onSuccess: () => {
          onPin(selectedDashboardId);
          onClose();
        },
      },
    );
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-canvas-node border border-canvas-border rounded-lg p-6 w-96">
        <h2 className="text-sm font-semibold text-white mb-4">Pin to Dashboard</h2>

        <div className="space-y-3 mb-4">
          <div>
            <label className="text-xs text-white/50 block mb-1">Widget Title</label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Optional title..."
              className="w-full bg-canvas-bg border border-white/10 rounded px-2 py-1.5 text-sm text-white"
            />
          </div>

          <div>
            <label className="text-xs text-white/50 block mb-1">Dashboard</label>
            <select
              value={selectedDashboardId}
              onChange={(e) => setSelectedDashboardId(e.target.value)}
              className="w-full bg-canvas-bg border border-white/10 rounded px-2 py-1.5 text-sm text-white"
            >
              <option value="">Select a dashboard...</option>
              {data?.items.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </select>
          </div>
        </div>

        {createWidget.error && (
          <div className="text-red-400 text-xs mb-3">
            {createWidget.error instanceof Error
              ? createWidget.error.message
              : "Failed to pin widget"}
          </div>
        )}

        <div className="flex gap-2 justify-end">
          <button onClick={onClose} className="px-3 py-1.5 text-xs text-white/60 hover:text-white">
            Cancel
          </button>
          <button
            onClick={handlePin}
            disabled={!selectedDashboardId || createWidget.isPending}
            className="px-3 py-1.5 text-xs bg-canvas-accent text-white rounded hover:opacity-80 disabled:opacity-40"
          >
            {createWidget.isPending ? "Pinning..." : "Pin Widget"}
          </button>
        </div>
      </div>
    </div>
  );
}
