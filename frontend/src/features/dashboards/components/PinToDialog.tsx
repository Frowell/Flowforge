/**
 * Pin to Dashboard dialog — shown from canvas when pinning an output node.
 */

import { useState } from "react";
import { useDashboardList } from "../hooks/useDashboard";

interface PinToDialogProps {
  workflowId: string;
  nodeId: string;
  onClose: () => void;
  onPin: (dashboardId: string) => void;
}

export default function PinToDialog({ workflowId, nodeId, onClose, onPin }: PinToDialogProps) {
  const { data } = useDashboardList();
  const [selectedDashboardId, setSelectedDashboardId] = useState<string>("");

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-canvas-node border border-canvas-border rounded-lg p-6 w-96">
        <h2 className="text-sm font-semibold text-white mb-4">Pin to Dashboard</h2>

        <select
          value={selectedDashboardId}
          onChange={(e) => setSelectedDashboardId(e.target.value)}
          className="w-full bg-canvas-bg border border-white/10 rounded px-2 py-1.5 text-sm text-white mb-4"
        >
          <option value="">Select a dashboard...</option>
          {data?.items.map((d) => (
            <option key={d.id} value={d.id}>{d.name}</option>
          ))}
        </select>

        <div className="flex gap-2 justify-end">
          <button onClick={onClose} className="px-3 py-1.5 text-xs text-white/60 hover:text-white">
            Cancel
          </button>
          <button
            onClick={() => selectedDashboardId && onPin(selectedDashboardId)}
            disabled={!selectedDashboardId}
            className="px-3 py-1.5 text-xs bg-canvas-accent text-white rounded hover:opacity-80 disabled:opacity-40"
          >
            Pin Widget
          </button>
        </div>
      </div>
    </div>
  );
}
