/**
 * Join config panel — join type + schema-aware key column dropdowns.
 */

import { useNodeInputSchemas } from "../hooks/useSchemaEngine";
import { useWorkflowStore } from "../stores/workflowStore";

interface Props {
  nodeId: string;
}

const JOIN_TYPES = ["inner", "left", "right", "full"] as const;

export default function JoinPanel({ nodeId }: Props) {
  const updateNodeConfig = useWorkflowStore((s) => s.updateNodeConfig);
  const node = useWorkflowStore((s) => s.nodes.find((n) => n.id === nodeId));
  const config = node?.data.config ?? {};
  const inputSchemas = useNodeInputSchemas(nodeId);
  const leftSchema = inputSchemas[0] ?? [];
  const rightSchema = inputSchemas[1] ?? [];

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
            <option key={jt} value={jt}>
              {jt.toUpperCase()}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label className="text-xs text-white/50 block mb-1">Left Key Column</label>
        {leftSchema.length > 0 ? (
          <select
            value={(config.left_key as string) ?? ""}
            onChange={(e) => updateNodeConfig(nodeId, { left_key: e.target.value })}
            className="w-full bg-canvas-bg border border-white/10 rounded px-2 py-1.5 text-sm text-white"
          >
            <option value="">Select column...</option>
            {leftSchema.map((col) => (
              <option key={col.name} value={col.name}>
                {col.name} ({col.dtype})
              </option>
            ))}
          </select>
        ) : (
          <input
            type="text"
            value={(config.left_key as string) ?? ""}
            onChange={(e) => updateNodeConfig(nodeId, { left_key: e.target.value })}
            className="w-full bg-canvas-bg border border-white/10 rounded px-2 py-1.5 text-sm text-white"
            placeholder="Connect left input..."
          />
        )}
      </div>

      <div>
        <label className="text-xs text-white/50 block mb-1">Right Key Column</label>
        {rightSchema.length > 0 ? (
          <select
            value={(config.right_key as string) ?? ""}
            onChange={(e) => updateNodeConfig(nodeId, { right_key: e.target.value })}
            className="w-full bg-canvas-bg border border-white/10 rounded px-2 py-1.5 text-sm text-white"
          >
            <option value="">Select column...</option>
            {rightSchema.map((col) => (
              <option key={col.name} value={col.name}>
                {col.name} ({col.dtype})
              </option>
            ))}
          </select>
        ) : (
          <input
            type="text"
            value={(config.right_key as string) ?? ""}
            onChange={(e) => updateNodeConfig(nodeId, { right_key: e.target.value })}
            className="w-full bg-canvas-bg border border-white/10 rounded px-2 py-1.5 text-sm text-white"
            placeholder="Connect right input..."
          />
        )}
      </div>
    </div>
  );
}
