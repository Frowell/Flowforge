import type { TypedNodeProps } from "../types/nodeConfigs";
import BaseNode from "./BaseNode";

export default function WindowNode({ data, selected }: TypedNodeProps<"window">) {
  const func = data.config?.function;
  const partitionBy = data.config?.partition_by;
  const outputColumn = data.config?.output_column;

  let display = "Not configured";
  if (func) {
    const partition = partitionBy?.length ? ` over ${partitionBy.join(", ")}` : "";
    display = `${func}${partition}`;
    if (outputColumn) display += ` → ${outputColumn}`;
  }

  return (
    <BaseNode label={data.label || "Window"} color="bg-amber-400" selected={selected}>
      {display}
    </BaseNode>
  );
}
