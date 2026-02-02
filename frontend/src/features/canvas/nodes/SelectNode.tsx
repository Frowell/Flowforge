import type { NodeProps } from "@xyflow/react";
import BaseNode from "./BaseNode";
import type { WorkflowNodeData } from "../stores/workflowStore";

export default function SelectNode({ data, selected }: NodeProps) {
  const nodeData = data as unknown as WorkflowNodeData;
  const columns = (nodeData.config?.columns as string[]) ?? [];

  return (
    <BaseNode label={nodeData.label || "Select"} color="bg-cyan-400" selected={selected}>
      {columns.length > 0 ? `${columns.length} columns` : "All columns"}
    </BaseNode>
  );
}
