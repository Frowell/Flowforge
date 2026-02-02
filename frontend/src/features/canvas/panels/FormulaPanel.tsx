/**
 * Formula config panel — expression editor with column reference autocomplete.
 */

import { useNodeInputSchema } from "../hooks/useSchemaEngine";
import { useWorkflowStore } from "../stores/workflowStore";
import FormulaEditor from "@/shared/components/FormulaEditor";

interface Props {
  nodeId: string;
}

export default function FormulaPanel({ nodeId }: Props) {
  const inputSchema = useNodeInputSchema(nodeId);
  const updateNodeConfig = useWorkflowStore((s) => s.updateNodeConfig);
  const node = useWorkflowStore((s) => s.nodes.find((n) => n.id === nodeId));
  const config = node?.data.config ?? {};

  return (
    <div className="space-y-3">
      <div>
        <label className="text-xs text-white/50 block mb-1">Expression</label>
        <FormulaEditor
          value={(config.expression as string) ?? ""}
          onChange={(expression) => updateNodeConfig(nodeId, { expression })}
          availableColumns={inputSchema}
        />
      </div>

      <div>
        <label className="text-xs text-white/50 block mb-1">Output Column Name</label>
        <input
          type="text"
          value={(config.output_column as string) ?? "calculated"}
          onChange={(e) => updateNodeConfig(nodeId, { output_column: e.target.value })}
          className="w-full bg-canvas-bg border border-white/10 rounded px-2 py-1.5 text-sm text-white"
        />
      </div>

      <div>
        <label className="text-xs text-white/50 block mb-1">Output Type</label>
        <select
          value={(config.output_dtype as string) ?? "float64"}
          onChange={(e) => updateNodeConfig(nodeId, { output_dtype: e.target.value })}
          className="w-full bg-canvas-bg border border-white/10 rounded px-2 py-1.5 text-sm text-white"
        >
          <option value="float64">Float</option>
          <option value="int64">Integer</option>
          <option value="string">String</option>
          <option value="bool">Boolean</option>
          <option value="datetime">DateTime</option>
        </select>
      </div>
    </div>
  );
}
