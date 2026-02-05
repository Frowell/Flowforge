/**
 * Select config panel — schema-aware column picker.
 *
 * Reads upstream schema and lets the user check/uncheck columns to include.
 */

import { useCallback } from "react";
import { useNodeInputSchema } from "../hooks/useSchemaEngine";
import { useWorkflowStore } from "../stores/workflowStore";

interface Props {
  nodeId: string;
}

export default function SelectPanel({ nodeId }: Props) {
  const inputSchema = useNodeInputSchema(nodeId);
  const updateNodeConfig = useWorkflowStore((s) => s.updateNodeConfig);
  const node = useWorkflowStore((s) => s.nodes.find((n) => n.id === nodeId));
  const config = node?.data.config ?? {};

  const selectedColumns = (config.columns as string[] | undefined) ?? [];

  const toggleColumn = useCallback(
    (colName: string) => {
      const current = selectedColumns;
      const next = current.includes(colName)
        ? current.filter((c) => c !== colName)
        : [...current, colName];
      updateNodeConfig(nodeId, { columns: next });
    },
    [nodeId, selectedColumns, updateNodeConfig],
  );

  const selectAll = useCallback(() => {
    updateNodeConfig(nodeId, { columns: inputSchema.map((c) => c.name) });
  }, [nodeId, inputSchema, updateNodeConfig]);

  const selectNone = useCallback(() => {
    updateNodeConfig(nodeId, { columns: [] });
  }, [nodeId, updateNodeConfig]);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-xs text-white/50">
          {selectedColumns.length} of {inputSchema.length} columns
        </span>
        <div className="flex gap-2">
          <button
            onClick={selectAll}
            className="text-xs text-accent-primary hover:text-accent-primary/80"
          >
            All
          </button>
          <button onClick={selectNone} className="text-xs text-white/40 hover:text-white/60">
            None
          </button>
        </div>
      </div>

      <div className="space-y-1">
        {inputSchema.map((col) => (
          <label
            key={col.name}
            className="flex items-center gap-2 px-2 py-1.5 rounded hover:bg-white/5 cursor-pointer"
          >
            <input
              type="checkbox"
              checked={selectedColumns.includes(col.name)}
              onChange={() => toggleColumn(col.name)}
              className="rounded border-white/20 bg-canvas-bg text-accent-primary focus:ring-accent-primary/50"
            />
            <span className="text-sm text-white/80 flex-1">{col.name}</span>
            <span className="text-xs text-white/30">{col.dtype}</span>
          </label>
        ))}
      </div>

      {inputSchema.length === 0 && (
        <div className="text-xs text-white/30">Connect an upstream node to see columns.</div>
      )}
    </div>
  );
}
