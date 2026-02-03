import type { NodeProps } from "@xyflow/react";
import BaseNode from "./BaseNode";
import type { WorkflowNodeData } from "../stores/workflowStore";

export default function WindowNode({ data, selected }: NodeProps) {
  const nodeData = data as unknown as WorkflowNodeData;
  const func = nodeData.config?.function as string | undefined;
  const partitionBy = nodeData.config?.partition_by as string[] | undefined;
  const outputColumn = nodeData.config?.output_column as string | undefined;

  let display = "Not configured";
  if (func) {
    const partition = partitionBy?.length ? ` over ${partitionBy.join(", ")}` : "";
    display = `${func}${partition}`;
    if (outputColumn) display += ` → ${outputColumn}`;
  }

  return (
    <BaseNode label={nodeData.label || "Window"} color="bg-amber-400" selected={selected}>
      {display}
    </BaseNode>
  );
}
