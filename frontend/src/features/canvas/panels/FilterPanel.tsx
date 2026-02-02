/**
 * Filter config panel — schema-aware column/operator/value selection.
 *
 * Derives all dropdowns from upstream outputSchema. Never hardcodes column lists.
 */

import { useNodeInputSchema } from "../hooks/useSchemaEngine";
import { useWorkflowStore } from "../stores/workflowStore";

interface Props {
  nodeId: string;
}

const OPERATORS_BY_TYPE: Record<string, string[]> = {
  string: ["=", "!=", "contains", "starts with", "ends with"],
  int64: ["=", "!=", ">", "<", ">=", "<=", "between"],
  float64: ["=", "!=", ">", "<", ">=", "<=", "between"],
  datetime: ["=", "!=", "before", "after", "between"],
  bool: ["=", "!="],
};

export default function FilterPanel({ nodeId }: Props) {
  const inputSchema = useNodeInputSchema(nodeId);
  const updateNodeConfig = useWorkflowStore((s) => s.updateNodeConfig);
  const node = useWorkflowStore((s) => s.nodes.find((n) => n.id === nodeId));
  const config = node?.data.config ?? {};

  const selectedColumn = config.column as string | undefined;
  const selectedColumnSchema = inputSchema.find((c) => c.name === selectedColumn);
  const operators = selectedColumnSchema
    ? OPERATORS_BY_TYPE[selectedColumnSchema.dtype] ?? ["=", "!="]
    : [];

  return (
    <div className="space-y-3">
      <div>
        <label className="text-xs text-white/50 block mb-1">Column</label>
        <select
          value={selectedColumn ?? ""}
          onChange={(e) => updateNodeConfig(nodeId, { column: e.target.value, operator: "=", value: "" })}
          className="w-full bg-canvas-bg border border-white/10 rounded px-2 py-1.5 text-sm text-white"
        >
          <option value="">Select column...</option>
          {inputSchema.map((col) => (
            <option key={col.name} value={col.name}>
              {col.name} ({col.dtype})
            </option>
          ))}
        </select>
      </div>

      {selectedColumn && (
        <div>
          <label className="text-xs text-white/50 block mb-1">Operator</label>
          <select
            value={(config.operator as string) ?? "="}
            onChange={(e) => updateNodeConfig(nodeId, { operator: e.target.value })}
            className="w-full bg-canvas-bg border border-white/10 rounded px-2 py-1.5 text-sm text-white"
          >
            {operators.map((op) => (
              <option key={op} value={op}>{op}</option>
            ))}
          </select>
        </div>
      )}

      {selectedColumn && (
        <div>
          <label className="text-xs text-white/50 block mb-1">Value</label>
          <input
            type="text"
            value={(config.value as string) ?? ""}
            onChange={(e) => updateNodeConfig(nodeId, { value: e.target.value })}
            className="w-full bg-canvas-bg border border-white/10 rounded px-2 py-1.5 text-sm text-white"
            placeholder="Filter value..."
          />
        </div>
      )}
    </div>
  );
}
