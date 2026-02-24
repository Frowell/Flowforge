import type { TypedNodeProps } from "../types/nodeConfigs";
import BaseNode from "./BaseNode";

export default function FilterNode({ data, selected }: TypedNodeProps<"filter">) {
  const column = data.config?.column;

  return (
    <BaseNode label={data.label || "Filter"} color="bg-cyan-400" selected={selected}>
      {column ? `${column} ${data.config?.operator ?? "="} ...` : "Not configured"}
    </BaseNode>
  );
}
