/**
 * Sample config panel — number input for row count.
 */

import { useWorkflowStore } from "../stores/workflowStore";

interface Props {
  nodeId: string;
}

export default function SamplePanel({ nodeId }: Props) {
  const updateNodeConfig = useWorkflowStore((s) => s.updateNodeConfig);
  const node = useWorkflowStore((s) => s.nodes.find((n) => n.id === nodeId));
  const config = node?.data.config ?? {};
  const count = (config.count as number) ?? 100;

  return (
    <div className="space-y-3">
      <p className="text-xs text-white/50">Limits the output to a fixed number of rows.</p>

      <div>
        <label className="text-xs text-white/50 block mb-1">Row Count</label>
        <input
          type="number"
          min={1}
          max={100000}
          value={count}
          onChange={(e) => {
            const val = parseInt(e.target.value, 10);
            if (!isNaN(val) && val > 0) {
              updateNodeConfig(nodeId, { count: val });
            }
          }}
          className="w-full bg-canvas-bg border border-white/10 rounded px-2 py-1.5 text-sm text-white"
        />
      </div>
    </div>
  );
}
