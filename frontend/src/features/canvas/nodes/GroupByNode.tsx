import type { TypedNodeProps } from "../types/nodeConfigs";
import BaseNode from "./BaseNode";

export default function GroupByNode({ data, selected }: TypedNodeProps<"group_by">) {
  const groupCols = data.config?.group_columns ?? [];

  return (
    <BaseNode label={data.label || "Group By"} color="bg-purple-400" selected={selected}>
      {groupCols.length > 0 ? groupCols.join(", ") : "Not configured"}
    </BaseNode>
  );
}
