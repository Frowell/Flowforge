/**
 * KPI Output config panel — value column, title, format, comparison.
 */

import { useWorkflowStore } from "../stores/workflowStore";
import { useNodeInputSchema } from "../hooks/useSchemaEngine";

interface Props {
  nodeId: string;
}

const FORMAT_OPTIONS = [
  { value: "number", label: "Number (1,234)" },
  { value: "decimal", label: "Decimal (1,234.56)" },
  { value: "percent", label: "Percent (12.34%)" },
  { value: "currency", label: "Currency ($1,234)" },
  { value: "compact", label: "Compact (1.2K, 3.4M)" },
];

export default function KPIPanel({ nodeId }: Props) {
  const updateNodeConfig = useWorkflowStore((s) => s.updateNodeConfig);
  const node = useWorkflowStore((s) => s.nodes.find((n) => n.id === nodeId));
  const inputSchema = useNodeInputSchema(nodeId);
  const config = node?.data.config ?? {};

  const valueColumn = (config.value_column as string) ?? "";
  const title = (config.title as string) ?? "";
  const format = (config.format as string) ?? "number";
  const compareColumn = (config.compare_column as string) ?? "";
  const prefix = (config.prefix as string) ?? "";
  const suffix = (config.suffix as string) ?? "";

  const numericColumns = inputSchema.filter((col) => ["int64", "float64"].includes(col.dtype));

  return (
    <div className="space-y-3">
      <p className="text-xs text-white/50">Display a single metric as a KPI card.</p>

      <div>
        <label className="text-xs text-white/50 block mb-1">Value Column</label>
        <select
          value={valueColumn}
          onChange={(e) => updateNodeConfig(nodeId, { value_column: e.target.value })}
          className="w-full bg-canvas-bg border border-white/10 rounded px-2 py-1.5 text-sm text-white"
        >
          <option value="">Select column...</option>
          {numericColumns.map((col) => (
            <option key={col.name} value={col.name}>
              {col.name} ({col.dtype})
            </option>
          ))}
        </select>
      </div>

      <div>
        <label className="text-xs text-white/50 block mb-1">Title</label>
        <input
          type="text"
          value={title}
          onChange={(e) => updateNodeConfig(nodeId, { title: e.target.value })}
          placeholder="Total Revenue"
          className="w-full bg-canvas-bg border border-white/10 rounded px-2 py-1.5 text-sm text-white"
        />
      </div>

      <div>
        <label className="text-xs text-white/50 block mb-1">Format</label>
        <select
          value={format}
          onChange={(e) => updateNodeConfig(nodeId, { format: e.target.value })}
          className="w-full bg-canvas-bg border border-white/10 rounded px-2 py-1.5 text-sm text-white"
        >
          {FORMAT_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      <div className="grid grid-cols-2 gap-2">
        <div>
          <label className="text-xs text-white/50 block mb-1">Prefix</label>
          <input
            type="text"
            value={prefix}
            onChange={(e) => updateNodeConfig(nodeId, { prefix: e.target.value })}
            placeholder="$"
            className="w-full bg-canvas-bg border border-white/10 rounded px-2 py-1.5 text-sm text-white"
          />
        </div>
        <div>
          <label className="text-xs text-white/50 block mb-1">Suffix</label>
          <input
            type="text"
            value={suffix}
            onChange={(e) => updateNodeConfig(nodeId, { suffix: e.target.value })}
            placeholder="%"
            className="w-full bg-canvas-bg border border-white/10 rounded px-2 py-1.5 text-sm text-white"
          />
        </div>
      </div>

      <div>
        <label className="text-xs text-white/50 block mb-1">Comparison Column (optional)</label>
        <select
          value={compareColumn}
          onChange={(e) => updateNodeConfig(nodeId, { compare_column: e.target.value })}
          className="w-full bg-canvas-bg border border-white/10 rounded px-2 py-1.5 text-sm text-white"
        >
          <option value="">None</option>
          {numericColumns
            .filter((c) => c.name !== valueColumn)
            .map((col) => (
              <option key={col.name} value={col.name}>
                {col.name} ({col.dtype})
              </option>
            ))}
        </select>
        <p className="text-xs text-white/30 mt-1">Shows % change vs comparison value</p>
      </div>
    </div>
  );
}
