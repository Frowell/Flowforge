import type { NodeProps } from "@xyflow/react";
import BaseNode from "./BaseNode";
import type { WorkflowNodeData } from "../stores/workflowStore";

export default function JoinNode({ data, selected }: NodeProps) {
  const nodeData = data as unknown as WorkflowNodeData;
  const joinType = (nodeData.config?.join_type as string) ?? "inner";

  return (
    <BaseNode label={nodeData.label || "Join"} color="bg-purple-400" selected={selected} inputPorts={2}>
      {joinType.toUpperCase()} JOIN
    </BaseNode>
  );
}
