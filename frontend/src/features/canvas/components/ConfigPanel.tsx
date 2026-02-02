/**
 * Right-side config panel — swaps content based on selected node type.
 *
 * Config panels are schema-aware: all dropdowns derive from upstream outputSchema.
 */

import { useWorkflowStore } from "../stores/workflowStore";
import { useNodeInputSchema } from "../hooks/useSchemaEngine";

import DataSourcePanel from "../panels/DataSourcePanel";
import FilterPanel from "../panels/FilterPanel";
import JoinPanel from "../panels/JoinPanel";
import GroupByPanel from "../panels/GroupByPanel";
import FormulaPanel from "../panels/FormulaPanel";
import ChartConfigPanel from "../panels/ChartConfigPanel";
import PivotPanel from "../panels/PivotPanel";

interface ConfigPanelProps {
  nodeId: string;
}

const PANEL_MAP: Record<string, React.FC<{ nodeId: string }>> = {
  data_source: DataSourcePanel,
  filter: FilterPanel,
  join: JoinPanel,
  group_by: GroupByPanel,
  pivot: PivotPanel,
  formula: FormulaPanel,
  chart_output: ChartConfigPanel,
};

export default function ConfigPanel({ nodeId }: ConfigPanelProps) {
  const node = useWorkflowStore((s) => s.nodes.find((n) => n.id === nodeId));
  const inputSchema = useNodeInputSchema(nodeId);

  if (!node) return null;

  const PanelComponent = PANEL_MAP[node.data.nodeType];

  return (
    <div className="w-72 bg-canvas-node border-l border-canvas-border p-4 overflow-y-auto shrink-0">
      <h2 className="text-sm font-semibold text-white mb-1">{node.data.label}</h2>
      <p className="text-xs text-white/40 mb-4">{node.data.nodeType}</p>

      {inputSchema.length > 0 && (
        <div className="mb-4">
          <h3 className="text-xs text-white/50 uppercase mb-1">Input Schema</h3>
          <div className="text-xs text-white/30 space-y-0.5">
            {inputSchema.map((col) => (
              <div key={col.name}>
                {col.name} <span className="text-white/20">({col.dtype})</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {PanelComponent ? (
        <PanelComponent nodeId={nodeId} />
      ) : (
        <div className="text-xs text-white/30">No configuration panel for this node type.</div>
      )}
    </div>
  );
}
