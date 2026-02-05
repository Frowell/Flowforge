import type { NodeProps } from "@xyflow/react";
import BaseNode from "./BaseNode";
import type { WorkflowNodeData } from "../stores/workflowStore";

export default function DataSourceNode({ data, selected }: NodeProps) {
  const nodeData = data as unknown as WorkflowNodeData;
  const table = (nodeData.config?.table as string) ?? "No table selected";

  return (
    <BaseNode
      label={nodeData.label || "Data Source"}
      color="bg-blue-400"
      selected={selected}
      inputPorts={0}
    >
      {table}
    </BaseNode>
  );
}
