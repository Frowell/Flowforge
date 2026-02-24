import type { TypedNodeProps } from "../types/nodeConfigs";
import BaseNode from "./BaseNode";

export default function ChartOutputNode({ data, selected }: TypedNodeProps<"chart_output">) {
  const chartType = data.config?.chart_type ?? "bar";

  return (
    <BaseNode
      label={data.label || "Chart"}
      color="bg-green-400"
      selected={selected}
      outputPorts={0}
    >
      {chartType.charAt(0).toUpperCase() + chartType.slice(1)} chart
    </BaseNode>
  );
}
