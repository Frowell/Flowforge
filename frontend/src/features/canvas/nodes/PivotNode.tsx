import type { TypedNodeProps } from "../types/nodeConfigs";
import BaseNode from "./BaseNode";

export default function PivotNode({ data, selected }: TypedNodeProps<"pivot">) {
  const pivotCol = data.config?.pivot_column ?? "";
  const valueCol = data.config?.value_column ?? "";

  return (
    <BaseNode label={data.label || "Pivot"} color="bg-purple-400" selected={selected}>
      {pivotCol ? `${pivotCol} → ${valueCol}` : "Not configured"}
    </BaseNode>
  );
}
