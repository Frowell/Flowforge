/**
 * Unique config panel — select columns for dedup key.
 * If none selected, DISTINCT on all columns.
 */

import { useNodeInputSchema } from "../hooks/useSchemaEngine";
import { useWorkflowStore } from "../stores/workflowStore";

interface Props {
  nodeId: string;
}

export default function UniquePanel({ nodeId }: Props) {
  const inputSchema = useNodeInputSchema(nodeId);
  const updateNodeConfig = useWorkflowStore((s) => s.updateNodeConfig);
  const node = useWorkflowStore((s) => s.nodes.find((n) => n.id === nodeId));
  const config = node?.data.config ?? {};
  const selectedColumns = (config.columns as string[]) ?? [];

  return (
    <div className="space-y-3">
      <p className="text-xs text-white/50">
        {selectedColumns.length === 0
          ? "DISTINCT on all columns. Select specific columns to deduplicate by a subset."
          : `Deduplicating by ${selectedColumns.length} column(s).`}
      </p>

      <div>
        <label className="text-xs text-white/50 block mb-1">Dedup Columns</label>
        <div className="space-y-1">
          {inputSchema.map((col) => (
            <label key={col.name} className="flex items-center gap-2 text-sm text-white/70">
              <input
                type="checkbox"
                checked={selectedColumns.includes(col.name)}
                onChange={(e) => {
                  const next = e.target.checked
                    ? [...selectedColumns, col.name]
                    : selectedColumns.filter((c) => c !== col.name);
                  updateNodeConfig(nodeId, { columns: next });
                }}
                className="rounded"
              />
              {col.name}
              <span className="text-white/30 text-xs">({col.dtype})</span>
            </label>
          ))}
        </div>
      </div>
    </div>
  );
}
