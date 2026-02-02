import type { NodeProps } from "@xyflow/react";
import BaseNode from "./BaseNode";
import type { WorkflowNodeData } from "../stores/workflowStore";

export default function RenameNode({ data, selected }: NodeProps) {
  const nodeData = data as unknown as WorkflowNodeData;
  const renameMap = (nodeData.config?.rename_map as Record<string, string>) ?? {};
  const count = Object.keys(renameMap).length;

  return (
    <BaseNode label={nodeData.label || "Rename"} color="bg-cyan-400" selected={selected}>
      {count > 0 ? `${count} renamed` : "No renames"}
    </BaseNode>
  );
}
