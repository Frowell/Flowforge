/**
 * Group By config panel — dimension picker + multiple aggregation rows.
 */

import { useNodeInputSchema } from "../hooks/useSchemaEngine";
import { useWorkflowStore } from "../stores/workflowStore";

interface Props {
  nodeId: string;
}

interface Aggregation {
  column: string;
  function: string;
  alias: string;
}

const AGG_FUNCTIONS = ["SUM", "AVG", "COUNT", "MIN", "MAX"] as const;

export default function GroupByPanel({ nodeId }: Props) {
  const inputSchema = useNodeInputSchema(nodeId);
  const updateNodeConfig = useWorkflowStore((s) => s.updateNodeConfig);
  const node = useWorkflowStore((s) => s.nodes.find((n) => n.id === nodeId));
  const config = node?.data.config ?? {};
  const groupColumns = (config.group_columns as string[]) ?? [];

  // Normalize aggregations from config
  const rawAggregations = config.aggregations as Aggregation[] | undefined;
  const aggregations: Aggregation[] = rawAggregations ?? (
    config.agg_column
      ? [{
          column: config.agg_column as string,
          function: (config.agg_function as string) ?? "SUM",
          alias: `${((config.agg_function as string) ?? "sum").toLowerCase()}_${config.agg_column as string}`,
        }]
      : [{ column: "", function: "SUM", alias: "" }]
  );

  const nonGroupColumns = inputSchema.filter((c) => !groupColumns.includes(c.name));

  const updateAggregations = (newAggs: Aggregation[]) => {
    updateNodeConfig(nodeId, { aggregations: newAggs });
  };

  const updateAgg = (index: number, field: keyof Aggregation, value: string) => {
    const newAggs: Aggregation[] = aggregations.map((a, i) => {
      if (i !== index) return a;
      const updated: Aggregation = { column: a.column, function: a.function, alias: a.alias };
      updated[field] = value;
      return updated;
    });
    // Auto-generate alias if column or function changes and alias is empty or auto-generated
    if (field === "column" || field === "function") {
      const agg = newAggs[index]!;
      const prev = aggregations[index]!;
      const autoAlias = `${agg.function.toLowerCase()}_${agg.column}`;
      const oldAutoAlias = `${prev.function.toLowerCase()}_${prev.column}`;
      if (!agg.alias || agg.alias === oldAutoAlias) {
        newAggs[index] = { column: agg.column, function: agg.function, alias: autoAlias };
      }
    }
    updateAggregations(newAggs);
  };

  const addAgg = () => {
    updateAggregations([...aggregations, { column: "", function: "SUM", alias: "" }]);
  };

  const removeAgg = (index: number) => {
    if (aggregations.length <= 1) return;
    updateAggregations(aggregations.filter((_, i) => i !== index));
  };

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
        <label className="text-xs text-white/50 block mb-1">Aggregations</label>
        <div className="space-y-2">
          {aggregations.map((agg, i) => (
            <div key={i} className="space-y-1 p-2 border border-white/5 rounded">
              <div className="flex gap-2">
                <select
                  value={agg.column}
                  onChange={(e) => updateAgg(i, "column", e.target.value)}
                  className="flex-1 bg-canvas-bg border border-white/10 rounded px-2 py-1 text-sm text-white"
                >
                  <option value="">Column...</option>
                  {nonGroupColumns.map((col) => (
                    <option key={col.name} value={col.name}>{col.name}</option>
                  ))}
                </select>
                <select
                  value={agg.function}
                  onChange={(e) => updateAgg(i, "function", e.target.value)}
                  className="w-20 bg-canvas-bg border border-white/10 rounded px-2 py-1 text-sm text-white"
                >
                  {AGG_FUNCTIONS.map((fn) => (
                    <option key={fn} value={fn}>{fn}</option>
                  ))}
                </select>
              </div>
              <div className="flex gap-2 items-center">
                <input
                  type="text"
                  value={agg.alias}
                  onChange={(e) => updateAgg(i, "alias", e.target.value)}
                  placeholder="Alias..."
                  className="flex-1 bg-canvas-bg border border-white/10 rounded px-2 py-1 text-xs text-white"
                />
                {aggregations.length > 1 && (
                  <button
                    onClick={() => removeAgg(i)}
                    className="text-xs text-red-400 hover:text-red-300"
                  >
                    Remove
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
        <button
          onClick={addAgg}
          className="mt-2 text-xs text-blue-400 hover:text-blue-300"
        >
          + Add Aggregation
        </button>
      </div>
    </div>
  );
}
