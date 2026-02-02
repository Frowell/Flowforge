import type { NodeProps } from "@xyflow/react";
import BaseNode from "./BaseNode";
import type { WorkflowNodeData } from "../stores/workflowStore";

export default function PivotNode({ data, selected }: NodeProps) {
  const nodeData = data as unknown as WorkflowNodeData;
  const pivotCol = (nodeData.config?.pivot_column as string) ?? "";
  const valueCol = (nodeData.config?.value_column as string) ?? "";

  return (
    <BaseNode label={nodeData.label || "Pivot"} color="bg-purple-400" selected={selected}>
      {pivotCol ? `${pivotCol} → ${valueCol}` : "Not configured"}
    </BaseNode>
  );
}
