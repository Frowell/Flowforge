import type { NodeProps } from "@xyflow/react";
import BaseNode from "./BaseNode";
import type { WorkflowNodeData } from "../stores/workflowStore";

export default function TableOutputNode({ data, selected }: NodeProps) {
  const nodeData = data as unknown as WorkflowNodeData;

  return (
    <BaseNode
      label={nodeData.label || "Table View"}
      color="bg-green-400"
      selected={selected}
      outputPorts={0}
    >
      Paginated grid
    </BaseNode>
  );
}
