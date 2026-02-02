import type { NodeProps } from "@xyflow/react";
import BaseNode from "./BaseNode";
import type { WorkflowNodeData } from "../stores/workflowStore";

export default function FormulaNode({ data, selected }: NodeProps) {
  const nodeData = data as unknown as WorkflowNodeData;
  const expression = nodeData.config?.expression as string | undefined;

  return (
    <BaseNode label={nodeData.label || "Formula"} color="bg-amber-400" selected={selected}>
      {expression ? expression.slice(0, 30) + (expression.length > 30 ? "..." : "") : "No expression"}
    </BaseNode>
  );
}
