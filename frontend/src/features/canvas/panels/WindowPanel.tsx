/**
 * Window function config panel — function type, partition, order, output column.
 */

import { useWorkflowStore } from "../stores/workflowStore";
import { useNodeInputSchema } from "../hooks/useSchemaEngine";

interface Props {
  nodeId: string;
}

const WINDOW_FUNCTIONS = [
  { value: "ROW_NUMBER", label: "Row Number" },
  { value: "RANK", label: "Rank" },
  { value: "DENSE_RANK", label: "Dense Rank" },
  { value: "LAG", label: "Lag (previous row)" },
  { value: "LEAD", label: "Lead (next row)" },
  { value: "SUM", label: "Running Sum" },
  { value: "AVG", label: "Running Average" },
  { value: "COUNT", label: "Running Count" },
  { value: "MIN", label: "Running Min" },
  { value: "MAX", label: "Running Max" },
  { value: "FIRST_VALUE", label: "First Value" },
  { value: "LAST_VALUE", label: "Last Value" },
];

export default function WindowPanel({ nodeId }: Props) {
  const updateNodeConfig = useWorkflowStore((s) => s.updateNodeConfig);
  const node = useWorkflowStore((s) => s.nodes.find((n) => n.id === nodeId));
  const inputSchema = useNodeInputSchema(nodeId);
  const config = node?.data.config ?? {};

  const func = (config.function as string) ?? "";
  const sourceColumn = (config.source_column as string) ?? "";
  const partitionBy = (config.partition_by as string[]) ?? [];
  const orderBy = (config.order_by as string) ?? "";
  const orderDir = (config.order_direction as string) ?? "ASC";
  const outputColumn = (config.output_column as string) ?? "window_result";

  const needsSourceColumn = ["LAG", "LEAD", "SUM", "AVG", "MIN", "MAX", "FIRST_VALUE", "LAST_VALUE"].includes(func);

  return (
    <div className="space-y-3">
      <p className="text-xs text-white/50">
        Apply a window function across partitions of data.
      </p>

      <div>
        <label className="text-xs text-white/50 block mb-1">Function</label>
        <select
          value={func}
          onChange={(e) => updateNodeConfig(nodeId, { function: e.target.value })}
          className="w-full bg-canvas-bg border border-white/10 rounded px-2 py-1.5 text-sm text-white"
        >
          <option value="">Select function...</option>
          {WINDOW_FUNCTIONS.map((f) => (
            <option key={f.value} value={f.value}>
              {f.label}
            </option>
          ))}
        </select>
      </div>

      {needsSourceColumn && (
        <div>
          <label className="text-xs text-white/50 block mb-1">Source Column</label>
          <select
            value={sourceColumn}
            onChange={(e) => updateNodeConfig(nodeId, { source_column: e.target.value })}
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
      )}

      <div>
        <label className="text-xs text-white/50 block mb-1">Partition By (optional)</label>
        <select
          multiple
          value={partitionBy}
          onChange={(e) => {
            const selected = Array.from(e.target.selectedOptions, (opt) => opt.value);
            updateNodeConfig(nodeId, { partition_by: selected });
          }}
          className="w-full bg-canvas-bg border border-white/10 rounded px-2 py-1.5 text-sm text-white min-h-[80px]"
        >
          {inputSchema.map((col) => (
            <option key={col.name} value={col.name}>
              {col.name}
            </option>
          ))}
        </select>
        <p className="text-xs text-white/30 mt-1">Ctrl/Cmd+click to select multiple</p>
      </div>

      <div>
        <label className="text-xs text-white/50 block mb-1">Order By</label>
        <select
          value={orderBy}
          onChange={(e) => updateNodeConfig(nodeId, { order_by: e.target.value })}
          className="w-full bg-canvas-bg border border-white/10 rounded px-2 py-1.5 text-sm text-white"
        >
          <option value="">Select column...</option>
          {inputSchema.map((col) => (
            <option key={col.name} value={col.name}>
              {col.name}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label className="text-xs text-white/50 block mb-1">Order Direction</label>
        <select
          value={orderDir}
          onChange={(e) => updateNodeConfig(nodeId, { order_direction: e.target.value })}
          className="w-full bg-canvas-bg border border-white/10 rounded px-2 py-1.5 text-sm text-white"
        >
          <option value="ASC">Ascending</option>
          <option value="DESC">Descending</option>
        </select>
      </div>

      <div>
        <label className="text-xs text-white/50 block mb-1">Output Column Name</label>
        <input
          type="text"
          value={outputColumn}
          onChange={(e) => updateNodeConfig(nodeId, { output_column: e.target.value })}
          placeholder="window_result"
          className="w-full bg-canvas-bg border border-white/10 rounded px-2 py-1.5 text-sm text-white"
        />
      </div>
    </div>
  );
}
