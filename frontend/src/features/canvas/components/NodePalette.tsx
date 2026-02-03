/**
 * Draggable node type sidebar.
 *
 * Lists available node types grouped by category.
 * Drag onto canvas to create a new node.
 */

import { cn } from "@/shared/lib/cn";

interface NodeTypeDefinition {
  type: string;
  label: string;
  category: "input" | "transform" | "combine" | "calculate" | "output";
}

const NODE_TYPES: NodeTypeDefinition[] = [
  { type: "data_source", label: "Data Source", category: "input" },
  { type: "filter", label: "Filter", category: "transform" },
  { type: "select", label: "Select", category: "transform" },
  { type: "sort", label: "Sort", category: "transform" },
  { type: "rename", label: "Rename", category: "transform" },
  { type: "unique", label: "Unique", category: "transform" },
  { type: "sample", label: "Sample", category: "transform" },
  { type: "limit", label: "Limit", category: "transform" },
  { type: "pivot", label: "Pivot", category: "transform" },
  { type: "join", label: "Join", category: "combine" },
  { type: "union", label: "Union", category: "combine" },
  { type: "group_by", label: "Group By", category: "combine" },
  { type: "formula", label: "Formula", category: "calculate" },
  { type: "window", label: "Window", category: "calculate" },
  { type: "table_output", label: "Table View", category: "output" },
  { type: "chart_output", label: "Chart", category: "output" },
  { type: "kpi_output", label: "KPI Card", category: "output" },
];

const CATEGORY_COLORS: Record<string, string> = {
  input: "border-blue-400",
  transform: "border-cyan-400",
  combine: "border-purple-400",
  calculate: "border-amber-400",
  output: "border-green-400",
};

export default function NodePalette() {
  const onDragStart = (event: React.DragEvent, nodeType: string) => {
    event.dataTransfer.setData("application/reactflow", nodeType);
    event.dataTransfer.effectAllowed = "move";
  };

  const grouped = NODE_TYPES.reduce(
    (acc, nt) => {
      (acc[nt.category] ??= []).push(nt);
      return acc;
    },
    {} as Record<string, NodeTypeDefinition[]>,
  );

  return (
    <div className="w-48 bg-canvas-node border-r border-canvas-border p-3 overflow-y-auto shrink-0">
      <h2 className="text-xs font-semibold text-white/50 uppercase tracking-wider mb-3">Nodes</h2>
      {Object.entries(grouped).map(([category, types]) => (
        <div key={category} className="mb-4">
          <h3 className="text-xs text-white/30 uppercase mb-1">{category}</h3>
          {types.map((nt) => (
            <div
              key={nt.type}
              draggable
              onDragStart={(e) => onDragStart(e, nt.type)}
              className={cn(
                "px-2 py-1.5 mb-1 text-sm text-white/80 bg-canvas-bg border-l-2 rounded-r cursor-grab hover:bg-white/5",
                CATEGORY_COLORS[category],
              )}
            >
              {nt.label}
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
