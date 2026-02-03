/**
 * Limit config panel — inputs for limit and offset.
 */

import { useWorkflowStore } from "../stores/workflowStore";

interface Props {
  nodeId: string;
}

export default function LimitPanel({ nodeId }: Props) {
  const updateNodeConfig = useWorkflowStore((s) => s.updateNodeConfig);
  const node = useWorkflowStore((s) => s.nodes.find((n) => n.id === nodeId));
  const config = node?.data.config ?? {};
  const limit = (config.limit as number) ?? 100;
  const offset = (config.offset as number) ?? 0;

  return (
    <div className="space-y-3">
      <p className="text-xs text-white/50">
        Returns the first N rows, optionally skipping some rows.
      </p>

      <div>
        <label className="text-xs text-white/50 block mb-1">Limit (rows)</label>
        <input
          type="number"
          min={1}
          max={1000000}
          value={limit}
          onChange={(e) => {
            const val = parseInt(e.target.value, 10);
            if (!isNaN(val) && val > 0) {
              updateNodeConfig(nodeId, { limit: val });
            }
          }}
          className="w-full bg-canvas-bg border border-white/10 rounded px-2 py-1.5 text-sm text-white"
        />
      </div>

      <div>
        <label className="text-xs text-white/50 block mb-1">Offset (skip rows)</label>
        <input
          type="number"
          min={0}
          max={1000000}
          value={offset}
          onChange={(e) => {
            const val = parseInt(e.target.value, 10);
            if (!isNaN(val) && val >= 0) {
              updateNodeConfig(nodeId, { offset: val });
            }
          }}
          className="w-full bg-canvas-bg border border-white/10 rounded px-2 py-1.5 text-sm text-white"
        />
      </div>
    </div>
  );
}
