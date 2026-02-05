/**
 * Pivot config panel — row columns, pivot column, value column, aggregation.
 */

import { useNodeInputSchema } from "../hooks/useSchemaEngine";
import { useWorkflowStore } from "../stores/workflowStore";

interface Props {
  nodeId: string;
}

const AGG_FUNCTIONS = ["SUM", "AVG", "COUNT", "MIN", "MAX"] as const;
const NUMERIC_DTYPES = new Set(["int64", "float64"]);

export default function PivotPanel({ nodeId }: Props) {
  const inputSchema = useNodeInputSchema(nodeId);
  const updateNodeConfig = useWorkflowStore((s) => s.updateNodeConfig);
  const node = useWorkflowStore((s) => s.nodes.find((n) => n.id === nodeId));
  const config = node?.data.config ?? {};
  const rowColumns = (config.row_columns as string[]) ?? [];
  const pivotColumn = (config.pivot_column as string) ?? "";
  const valueColumn = (config.value_column as string) ?? "";
  const aggregation = (config.aggregation as string) ?? "SUM";

  const selectedRowSet = new Set(rowColumns);
  const availableForPivot = inputSchema.filter((c) => !selectedRowSet.has(c.name));
  const availableForValue = availableForPivot.filter((c) => NUMERIC_DTYPES.has(c.dtype));

  return (
    <div className="space-y-3">
      <div>
        <label className="text-xs text-white/50 block mb-1">Row Columns</label>
        <div className="space-y-1">
          {inputSchema.map((col) => (
            <label key={col.name} className="flex items-center gap-2 text-sm text-white/70">
              <input
                type="checkbox"
                checked={rowColumns.includes(col.name)}
                onChange={(e) => {
                  const next = e.target.checked
                    ? [...rowColumns, col.name]
                    : rowColumns.filter((c) => c !== col.name);
                  updateNodeConfig(nodeId, { row_columns: next });
                }}
                className="rounded"
              />
              {col.name}
            </label>
          ))}
        </div>
      </div>

      <div>
        <label className="text-xs text-white/50 block mb-1">Pivot Column</label>
        <select
          value={pivotColumn}
          onChange={(e) => updateNodeConfig(nodeId, { pivot_column: e.target.value })}
          className="w-full bg-canvas-bg border border-white/10 rounded px-2 py-1.5 text-sm text-white"
        >
          <option value="">Select column...</option>
          {availableForPivot.map((col) => (
            <option key={col.name} value={col.name}>
              {col.name}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label className="text-xs text-white/50 block mb-1">Value Column</label>
        <select
          value={valueColumn}
          onChange={(e) => updateNodeConfig(nodeId, { value_column: e.target.value })}
          className="w-full bg-canvas-bg border border-white/10 rounded px-2 py-1.5 text-sm text-white"
        >
          <option value="">Select column...</option>
          {availableForValue.map((col) => (
            <option key={col.name} value={col.name}>
              {col.name}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label className="text-xs text-white/50 block mb-1">Aggregation</label>
        <select
          value={aggregation}
          onChange={(e) => updateNodeConfig(nodeId, { aggregation: e.target.value })}
          className="w-full bg-canvas-bg border border-white/10 rounded px-2 py-1.5 text-sm text-white"
        >
          {AGG_FUNCTIONS.map((fn) => (
            <option key={fn} value={fn}>
              {fn}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}
