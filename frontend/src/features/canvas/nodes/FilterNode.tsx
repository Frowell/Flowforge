import type { NodeProps } from "@xyflow/react";
import BaseNode from "./BaseNode";
import type { WorkflowNodeData } from "../stores/workflowStore";

export default function FilterNode({ data, selected }: NodeProps) {
  const nodeData = data as unknown as WorkflowNodeData;
  const column = nodeData.config?.column as string | undefined;

  return (
    <BaseNode label={nodeData.label || "Filter"} color="bg-cyan-400" selected={selected}>
      {column ? `${column} ${nodeData.config?.operator ?? "="} ...` : "Not configured"}
    </BaseNode>
  );
}
