/**
 * Data Source config panel — table picker from schema catalog.
 */

import { useCatalog } from "@/shared/schema/registry";
import { useWorkflowStore } from "../stores/workflowStore";

interface Props {
  nodeId: string;
}

export default function DataSourcePanel({ nodeId }: Props) {
  const { data: catalog, isLoading } = useCatalog();
  const updateNodeConfig = useWorkflowStore((s) => s.updateNodeConfig);
  const node = useWorkflowStore((s) => s.nodes.find((n) => n.id === nodeId));
  const selectedTable = node?.data.config?.table as string | undefined;

  return (
    <div className="space-y-3">
      <div>
        <label className="text-xs text-white/50 block mb-1">Table</label>
        {isLoading ? (
          <div className="text-xs text-white/30">Loading catalog...</div>
        ) : (
          <select
            value={selectedTable ?? ""}
            onChange={(e) => {
              const table = catalog?.tables.find((t) => t.name === e.target.value);
              updateNodeConfig(nodeId, {
                table: e.target.value,
                columns: table?.columns ?? [],
              });
            }}
            className="w-full bg-canvas-bg border border-white/10 rounded px-2 py-1.5 text-sm text-white"
          >
            <option value="">Select a table...</option>
            {catalog?.tables.map((t) => (
              <option key={t.name} value={t.name}>
                {t.name} ({t.source})
              </option>
            ))}
          </select>
        )}
      </div>
    </div>
  );
}
