import type { TypedNodeProps } from "../types/nodeConfigs";
import BaseNode from "./BaseNode";

export default function SelectNode({ data, selected }: TypedNodeProps<"select">) {
  const columns = data.config?.columns ?? [];

  return (
    <BaseNode label={data.label || "Select"} color="bg-cyan-400" selected={selected}>
      {columns.length > 0 ? `${columns.length} columns` : "All columns"}
    </BaseNode>
  );
}
