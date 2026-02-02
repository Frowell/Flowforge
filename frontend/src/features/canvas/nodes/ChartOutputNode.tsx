import type { NodeProps } from "@xyflow/react";
import BaseNode from "./BaseNode";
import type { WorkflowNodeData } from "../stores/workflowStore";

export default function ChartOutputNode({ data, selected }: NodeProps) {
  const nodeData = data as unknown as WorkflowNodeData;
  const chartType = (nodeData.config?.chart_type as string) ?? "bar";

  return (
    <BaseNode label={nodeData.label || "Chart"} color="bg-green-400" selected={selected} outputPorts={0}>
      {chartType.charAt(0).toUpperCase() + chartType.slice(1)} chart
    </BaseNode>
  );
}
