import type { NodeProps } from "@xyflow/react";
import BaseNode from "./BaseNode";
import type { WorkflowNodeData } from "../stores/workflowStore";

export default function SortNode({ data, selected }: NodeProps) {
  const nodeData = data as unknown as WorkflowNodeData;
  const column = nodeData.config?.column as string | undefined;
  const direction = (nodeData.config?.direction as string) ?? "ASC";

  return (
    <BaseNode label={nodeData.label || "Sort"} color="bg-cyan-400" selected={selected}>
      {column ? `${column} ${direction}` : "Not configured"}
    </BaseNode>
  );
}
