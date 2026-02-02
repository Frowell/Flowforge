import type { NodeProps } from "@xyflow/react";
import BaseNode from "./BaseNode";
import type { WorkflowNodeData } from "../stores/workflowStore";

export default function UniqueNode({ data, selected }: NodeProps) {
  const nodeData = data as unknown as WorkflowNodeData;

  return (
    <BaseNode label={nodeData.label || "Unique"} color="bg-cyan-400" selected={selected}>
      Deduplicate rows
    </BaseNode>
  );
}
