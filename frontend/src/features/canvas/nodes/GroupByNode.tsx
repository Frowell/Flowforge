import type { NodeProps } from "@xyflow/react";
import BaseNode from "./BaseNode";
import type { WorkflowNodeData } from "../stores/workflowStore";

export default function GroupByNode({ data, selected }: NodeProps) {
  const nodeData = data as unknown as WorkflowNodeData;
  const groupCols = (nodeData.config?.group_columns as string[]) ?? [];

  return (
    <BaseNode label={nodeData.label || "Group By"} color="bg-purple-400" selected={selected}>
      {groupCols.length > 0 ? groupCols.join(", ") : "Not configured"}
    </BaseNode>
  );
}
