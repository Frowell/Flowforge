import type { TypedNodeProps } from "../types/nodeConfigs";
import BaseNode from "./BaseNode";

export default function DataSourceNode({ data, selected }: TypedNodeProps<"data_source">) {
  const table = data.config?.table ?? "No table selected";

  return (
    <BaseNode
      label={data.label || "Data Source"}
      color="bg-blue-400"
      selected={selected}
      inputPorts={0}
    >
      {table}
    </BaseNode>
  );
}
