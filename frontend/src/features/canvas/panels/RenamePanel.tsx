/**
 * Rename config panel — key-value list mapping original column names to new names.
 *
 * Only shows rows for columns the user wants to rename. "Add rename" picks a column.
 */

import { useCallback, useState } from "react";
import { useNodeInputSchema } from "../hooks/useSchemaEngine";
import { useWorkflowStore } from "../stores/workflowStore";

interface Props {
  nodeId: string;
}

export default function RenamePanel({ nodeId }: Props) {
  const inputSchema = useNodeInputSchema(nodeId);
  const updateNodeConfig = useWorkflowStore((s) => s.updateNodeConfig);
  const node = useWorkflowStore((s) => s.nodes.find((n) => n.id === nodeId));
  const config = node?.data.config ?? {};

  const renameMap = (config.rename_map as Record<string, string> | undefined) ?? {};
  const [showPicker, setShowPicker] = useState(false);

  const availableColumns = inputSchema.filter((col) => !(col.name in renameMap));

  const updateRenames = useCallback(
    (map: Record<string, string>) => {
      updateNodeConfig(nodeId, { rename_map: map });
    },
    [nodeId, updateNodeConfig],
  );

  const addRename = useCallback(
    (colName: string) => {
      updateRenames({ ...renameMap, [colName]: colName });
      setShowPicker(false);
    },
    [renameMap, updateRenames],
  );

  const removeRename = useCallback(
    (colName: string) => {
      const next = { ...renameMap };
      delete next[colName];
      updateRenames(next);
    },
    [renameMap, updateRenames],
  );

  const updateRename = useCallback(
    (originalName: string, newName: string) => {
      updateRenames({ ...renameMap, [originalName]: newName });
    },
    [renameMap, updateRenames],
  );

  const entries = Object.entries(renameMap);

  return (
    <div className="space-y-3">
      {entries.map(([original, renamed]) => (
        <div key={original} className="flex items-center gap-2">
          <span className="text-xs text-white/50 min-w-[60px] truncate" title={original}>
            {original}
          </span>
          <span className="text-white/30">&rarr;</span>
          <input
            type="text"
            value={renamed}
            onChange={(e) => updateRename(original, e.target.value)}
            className="flex-1 bg-canvas-bg border border-white/10 rounded px-2 py-1.5 text-sm text-white"
            placeholder="New name..."
          />
          <button
            onClick={() => removeRename(original)}
            className="px-1.5 py-1.5 text-white/30 hover:text-red-400"
          >
            &times;
          </button>
        </div>
      ))}

      {entries.length === 0 && !showPicker && (
        <div className="text-xs text-white/30 mb-2">No columns renamed yet.</div>
      )}

      {showPicker ? (
        <div className="space-y-1">
          <label className="text-xs text-white/50 block">Pick a column to rename</label>
          <select
            value=""
            onChange={(e) => {
              if (e.target.value) addRename(e.target.value);
            }}
            className="w-full bg-canvas-bg border border-white/10 rounded px-2 py-1.5 text-sm text-white"
          >
            <option value="">Select column...</option>
            {availableColumns.map((col) => (
              <option key={col.name} value={col.name}>
                {col.name} ({col.dtype})
              </option>
            ))}
          </select>
          <button
            onClick={() => setShowPicker(false)}
            className="text-xs text-white/40 hover:text-white/60"
          >
            Cancel
          </button>
        </div>
      ) : (
        availableColumns.length > 0 && (
          <button
            onClick={() => setShowPicker(true)}
            className="w-full py-1.5 border border-dashed border-white/10 rounded text-xs text-white/40 hover:text-white/60 hover:border-white/20"
          >
            + Add rename
          </button>
        )
      )}

      {inputSchema.length === 0 && (
        <div className="text-xs text-white/30">Connect an upstream node to rename columns.</div>
      )}
    </div>
  );
}
