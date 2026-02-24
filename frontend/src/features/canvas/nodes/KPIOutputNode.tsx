import type { TypedNodeProps } from "../types/nodeConfigs";
import BaseNode from "./BaseNode";

export default function KPIOutputNode({ data, selected }: TypedNodeProps<"kpi_output">) {
  const valueColumn = data.config?.value_column;
  const title = data.config?.title;
  const format = data.config?.format;

  let display = "Not configured";
  if (valueColumn) {
    display = title || valueColumn;
    if (format) display += ` (${format})`;
  }

  return (
    <BaseNode label={data.label || "KPI"} color="bg-green-400" selected={selected} outputPorts={0}>
      {display}
    </BaseNode>
  );
}
