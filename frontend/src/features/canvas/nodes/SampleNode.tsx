import type { NodeProps } from "@xyflow/react";
import BaseNode from "./BaseNode";
import type { WorkflowNodeData } from "../stores/workflowStore";

export default function SampleNode({ data, selected }: NodeProps) {
  const nodeData = data as unknown as WorkflowNodeData;
  const count = nodeData.config?.count as number | undefined;

  return (
    <BaseNode label={nodeData.label || "Sample"} color="bg-cyan-400" selected={selected}>
      {count ? `${count} rows` : "Not configured"}
    </BaseNode>
  );
}
