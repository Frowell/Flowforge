import type { TypedNodeProps } from "../types/nodeConfigs";
import BaseNode from "./BaseNode";

export default function SortNode({ data, selected }: TypedNodeProps<"sort">) {
  const column = data.config?.column;
  const direction = data.config?.direction ?? "ASC";

  return (
    <BaseNode label={data.label || "Sort"} color="bg-cyan-400" selected={selected}>
      {column ? `${column} ${direction}` : "Not configured"}
    </BaseNode>
  );
}
