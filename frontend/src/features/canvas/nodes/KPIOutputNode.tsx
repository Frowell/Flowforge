import type { NodeProps } from "@xyflow/react";
import BaseNode from "./BaseNode";
import type { WorkflowNodeData } from "../stores/workflowStore";

export default function KPIOutputNode({ data, selected }: NodeProps) {
  const nodeData = data as unknown as WorkflowNodeData;
  const valueColumn = nodeData.config?.value_column as string | undefined;
  const title = nodeData.config?.title as string | undefined;
  const format = nodeData.config?.format as string | undefined;

  let display = "Not configured";
  if (valueColumn) {
    display = title || valueColumn;
    if (format) display += ` (${format})`;
  }

  return (
    <BaseNode label={nodeData.label || "KPI"} color="bg-green-400" selected={selected} outputPorts={0}>
      {display}
    </BaseNode>
  );
}
