import type { NodeProps } from "@xyflow/react";
import BaseNode from "./BaseNode";
import type { WorkflowNodeData } from "../stores/workflowStore";

export default function UnionNode({ data, selected }: NodeProps) {
  const nodeData = data as unknown as WorkflowNodeData;

  return (
    <BaseNode
      label={nodeData.label || "Union"}
      color="bg-purple-400"
      selected={selected}
      inputPorts={2}
    >
      UNION ALL
    </BaseNode>
  );
}
