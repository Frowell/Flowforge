/**
 * Table output config panel — title, rows per page, and pin to dashboard.
 */

import { useState } from "react";
import { useParams } from "react-router-dom";

import { useWorkflowStore } from "../stores/workflowStore";
import PinToDialog from "@/features/dashboards/components/PinToDialog";

interface Props {
  nodeId: string;
}

const ROWS_PER_PAGE_OPTIONS = [10, 25, 50, 100] as const;

export default function TableOutputPanel({ nodeId }: Props) {
  const { workflowId } = useParams<{ workflowId: string }>();
  const updateNodeConfig = useWorkflowStore((s) => s.updateNodeConfig);
  const node = useWorkflowStore((s) => s.nodes.find((n) => n.id === nodeId));
  const config = node?.data.config ?? {};
  const [showPinDialog, setShowPinDialog] = useState(false);

  const title = (config.title as string) ?? "";
  const rowsPerPage = (config.rows_per_page as number) ?? 25;

  return (
    <div className="space-y-3">
      <p className="text-xs text-white/50">Display query results as a sortable data table.</p>

      <div>
        <label className="text-xs text-white/50 block mb-1">Title</label>
        <input
          type="text"
          value={title}
          onChange={(e) => updateNodeConfig(nodeId, { title: e.target.value })}
          placeholder="Table title..."
          className="w-full bg-canvas-bg border border-white/10 rounded px-2 py-1.5 text-sm text-white"
        />
      </div>

      <div>
        <label className="text-xs text-white/50 block mb-1">Rows per Page</label>
        <select
          value={rowsPerPage}
          onChange={(e) => updateNodeConfig(nodeId, { rows_per_page: Number(e.target.value) })}
          className="w-full bg-canvas-bg border border-white/10 rounded px-2 py-1.5 text-sm text-white"
        >
          {ROWS_PER_PAGE_OPTIONS.map((n) => (
            <option key={n} value={n}>
              {n} rows
            </option>
          ))}
        </select>
      </div>

      {/* Pin to Dashboard */}
      {workflowId && (
        <div className="pt-2 border-t border-canvas-border">
          <button
            onClick={() => setShowPinDialog(true)}
            className="w-full px-3 py-2 text-xs bg-canvas-accent text-white rounded hover:opacity-80"
          >
            Pin to Dashboard
          </button>
        </div>
      )}

      {showPinDialog && workflowId && (
        <PinToDialog
          workflowId={workflowId}
          nodeId={nodeId}
          onClose={() => setShowPinDialog(false)}
          onPin={() => setShowPinDialog(false)}
        />
      )}
    </div>
  );
}
