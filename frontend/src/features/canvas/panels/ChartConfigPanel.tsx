/**
 * Chart output config panel — chart type selection and axis mapping.
 */

import { useNodeInputSchema } from "../hooks/useSchemaEngine";
import { useWorkflowStore } from "../stores/workflowStore";

interface Props {
  nodeId: string;
}

const CHART_TYPES = ["bar", "line", "scatter", "candlestick", "kpi", "pivot"] as const;

export default function ChartConfigPanel({ nodeId }: Props) {
  const inputSchema = useNodeInputSchema(nodeId);
  const updateNodeConfig = useWorkflowStore((s) => s.updateNodeConfig);
  const node = useWorkflowStore((s) => s.nodes.find((n) => n.id === nodeId));
  const config = node?.data.config ?? {};

  return (
    <div className="space-y-3">
      <div>
        <label className="text-xs text-white/50 block mb-1">Chart Type</label>
        <select
          value={(config.chart_type as string) ?? "bar"}
          onChange={(e) => updateNodeConfig(nodeId, { chart_type: e.target.value })}
          className="w-full bg-canvas-bg border border-white/10 rounded px-2 py-1.5 text-sm text-white"
        >
          {CHART_TYPES.map((ct) => (
            <option key={ct} value={ct}>
              {ct.charAt(0).toUpperCase() + ct.slice(1)}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label className="text-xs text-white/50 block mb-1">X Axis</label>
        <select
          value={(config.x_axis as string) ?? ""}
          onChange={(e) => updateNodeConfig(nodeId, { x_axis: e.target.value })}
          className="w-full bg-canvas-bg border border-white/10 rounded px-2 py-1.5 text-sm text-white"
        >
          <option value="">Select column...</option>
          {inputSchema.map((col) => (
            <option key={col.name} value={col.name}>{col.name}</option>
          ))}
        </select>
      </div>

      <div>
        <label className="text-xs text-white/50 block mb-1">Y Axis</label>
        <select
          value={(config.y_axis as string) ?? ""}
          onChange={(e) => updateNodeConfig(nodeId, { y_axis: e.target.value })}
          className="w-full bg-canvas-bg border border-white/10 rounded px-2 py-1.5 text-sm text-white"
        >
          <option value="">Select column...</option>
          {inputSchema.map((col) => (
            <option key={col.name} value={col.name}>{col.name}</option>
          ))}
        </select>
      </div>
    </div>
  );
}
