/**
 * Sort config panel — multi-rule sort with column dropdown + direction toggle.
 *
 * Each rule picks a column from the upstream schema and sets ASC/DESC.
 */

import { useCallback } from "react";
import { useNodeInputSchema } from "../hooks/useSchemaEngine";
import { useWorkflowStore } from "../stores/workflowStore";

interface SortRule {
  column: string;
  direction: "asc" | "desc";
}

interface Props {
  nodeId: string;
}

export default function SortPanel({ nodeId }: Props) {
  const inputSchema = useNodeInputSchema(nodeId);
  const updateNodeConfig = useWorkflowStore((s) => s.updateNodeConfig);
  const node = useWorkflowStore((s) => s.nodes.find((n) => n.id === nodeId));
  const config = node?.data.config ?? {};

  const sortBy = (config.sort_by as SortRule[] | undefined) ?? [];

  const updateRules = useCallback(
    (rules: SortRule[]) => {
      updateNodeConfig(nodeId, { sort_by: rules });
    },
    [nodeId, updateNodeConfig],
  );

  const addRule = useCallback(() => {
    const firstAvailable = inputSchema.find(
      (col) => !sortBy.some((r) => r.column === col.name),
    );
    if (firstAvailable) {
      updateRules([...sortBy, { column: firstAvailable.name, direction: "asc" }]);
    }
  }, [inputSchema, sortBy, updateRules]);

  const removeRule = useCallback(
    (index: number) => {
      updateRules(sortBy.filter((_, i) => i !== index));
    },
    [sortBy, updateRules],
  );

  const updateRule = useCallback(
    (index: number, updates: Partial<SortRule>) => {
      updateRules(sortBy.map((r, i) => (i === index ? { ...r, ...updates } : r)));
    },
    [sortBy, updateRules],
  );

  return (
    <div className="space-y-3">
      {sortBy.map((rule, index) => (
        <div key={index} className="flex items-center gap-2">
          <select
            value={rule.column}
            onChange={(e) => updateRule(index, { column: e.target.value })}
            className="flex-1 bg-canvas-bg border border-white/10 rounded px-2 py-1.5 text-sm text-white"
          >
            {inputSchema.map((col) => (
              <option key={col.name} value={col.name}>
                {col.name}
              </option>
            ))}
          </select>

          <button
            onClick={() =>
              updateRule(index, {
                direction: rule.direction === "asc" ? "desc" : "asc",
              })
            }
            className="px-2 py-1.5 bg-canvas-bg border border-white/10 rounded text-xs text-white/70 hover:text-white min-w-[52px]"
          >
            {rule.direction === "asc" ? "ASC" : "DESC"}
          </button>

          <button
            onClick={() => removeRule(index)}
            className="px-1.5 py-1.5 text-white/30 hover:text-red-400"
          >
            &times;
          </button>
        </div>
      ))}

      {inputSchema.length > 0 && sortBy.length < inputSchema.length && (
        <button
          onClick={addRule}
          className="w-full py-1.5 border border-dashed border-white/10 rounded text-xs text-white/40 hover:text-white/60 hover:border-white/20"
        >
          + Add sort rule
        </button>
      )}

      {inputSchema.length === 0 && (
        <div className="text-xs text-white/30">Connect an upstream node to configure sorting.</div>
      )}
    </div>
  );
}
