/**
 * Group By config panel — dimension picker + aggregation function selector.
 */

import { useNodeInputSchema } from "../hooks/useSchemaEngine";
import { useWorkflowStore } from "../stores/workflowStore";

interface Props {
  nodeId: string;
}

const AGG_FUNCTIONS = ["SUM", "AVG", "COUNT", "MIN", "MAX"] as const;

export default function GroupByPanel({ nodeId }: Props) {
  const inputSchema = useNodeInputSchema(nodeId);
  const updateNodeConfig = useWorkflowStore((s) => s.updateNodeConfig);
  const node = useWorkflowStore((s) => s.nodes.find((n) => n.id === nodeId));
  const config = node?.data.config ?? {};
  const groupColumns = (config.group_columns as string[]) ?? [];

  return (
    <div className="space-y-3">
      <div>
        <label className="text-xs text-white/50 block mb-1">Group Columns</label>
        <div className="space-y-1">
          {inputSchema.map((col) => (
            <label key={col.name} className="flex items-center gap-2 text-sm text-white/70">
              <input
                type="checkbox"
                checked={groupColumns.includes(col.name)}
                onChange={(e) => {
                  const next = e.target.checked
                    ? [...groupColumns, col.name]
                    : groupColumns.filter((c) => c !== col.name);
                  updateNodeConfig(nodeId, { group_columns: next });
                }}
                className="rounded"
              />
              {col.name}
            </label>
          ))}
        </div>
      </div>

      <div>
        <label className="text-xs text-white/50 block mb-1">Aggregation</label>
        <div className="flex gap-2">
          <select
            value={(config.agg_column as string) ?? ""}
            onChange={(e) => updateNodeConfig(nodeId, { agg_column: e.target.value })}
            className="flex-1 bg-canvas-bg border border-white/10 rounded px-2 py-1.5 text-sm text-white"
          >
            <option value="">Column...</option>
            {inputSchema
              .filter((c) => !groupColumns.includes(c.name))
              .map((col) => (
                <option key={col.name} value={col.name}>{col.name}</option>
              ))}
          </select>
          <select
            value={(config.agg_function as string) ?? "SUM"}
            onChange={(e) => updateNodeConfig(nodeId, { agg_function: e.target.value })}
            className="w-24 bg-canvas-bg border border-white/10 rounded px-2 py-1.5 text-sm text-white"
          >
            {AGG_FUNCTIONS.map((fn) => (
              <option key={fn} value={fn}>{fn}</option>
            ))}
          </select>
        </div>
      </div>
    </div>
  );
}
