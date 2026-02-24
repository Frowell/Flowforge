import type { TypedNodeProps } from "../types/nodeConfigs";
import BaseNode from "./BaseNode";

export default function LimitNode({ data, selected }: TypedNodeProps<"limit">) {
  const limit = data.config?.limit;
  const offset = data.config?.offset;

  let display = "Not configured";
  if (limit !== undefined) {
    display = offset ? `Top ${limit} (skip ${offset})` : `Top ${limit}`;
  }

  return (
    <BaseNode label={data.label || "Limit"} color="bg-cyan-400" selected={selected}>
      {display}
    </BaseNode>
  );
}
