import type { NodeProps } from "@xyflow/react";
import BaseNode from "./BaseNode";
import type { WorkflowNodeData } from "../stores/workflowStore";

export default function LimitNode({ data, selected }: NodeProps) {
  const nodeData = data as unknown as WorkflowNodeData;
  const limit = nodeData.config?.limit as number | undefined;
  const offset = nodeData.config?.offset as number | undefined;

  let display = "Not configured";
  if (limit !== undefined) {
    display = offset ? `Top ${limit} (skip ${offset})` : `Top ${limit}`;
  }

  return (
    <BaseNode label={nodeData.label || "Limit"} color="bg-cyan-400" selected={selected}>
      {display}
    </BaseNode>
  );
}
