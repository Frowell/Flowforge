/**
 * Join config panel — join type + key column mapping from each input.
 */

import { useWorkflowStore } from "../stores/workflowStore";

interface Props {
  nodeId: string;
}

const JOIN_TYPES = ["inner", "left", "right", "full"] as const;

export default function JoinPanel({ nodeId }: Props) {
  const updateNodeConfig = useWorkflowStore((s) => s.updateNodeConfig);
  const node = useWorkflowStore((s) => s.nodes.find((n) => n.id === nodeId));
  const config = node?.data.config ?? {};

  // TODO: Get input schemas from both input ports to populate key column dropdowns

  return (
    <div className="space-y-3">
      <div>
        <label className="text-xs text-white/50 block mb-1">Join Type</label>
        <select
          value={(config.join_type as string) ?? "inner"}
          onChange={(e) => updateNodeConfig(nodeId, { join_type: e.target.value })}
          className="w-full bg-canvas-bg border border-white/10 rounded px-2 py-1.5 text-sm text-white"
        >
          {JOIN_TYPES.map((jt) => (
            <option key={jt} value={jt}>{jt.toUpperCase()}</option>
          ))}
        </select>
      </div>

      <div>
        <label className="text-xs text-white/50 block mb-1">Left Key Column</label>
        <input
          type="text"
          value={(config.left_key as string) ?? ""}
          onChange={(e) => updateNodeConfig(nodeId, { left_key: e.target.value })}
          className="w-full bg-canvas-bg border border-white/10 rounded px-2 py-1.5 text-sm text-white"
          placeholder="Column name..."
        />
      </div>

      <div>
        <label className="text-xs text-white/50 block mb-1">Right Key Column</label>
        <input
          type="text"
          value={(config.right_key as string) ?? ""}
          onChange={(e) => updateNodeConfig(nodeId, { right_key: e.target.value })}
          className="w-full bg-canvas-bg border border-white/10 rounded px-2 py-1.5 text-sm text-white"
          placeholder="Column name..."
        />
      </div>
    </div>
  );
}
