import type { TypedNodeProps } from "../types/nodeConfigs";
import BaseNode from "./BaseNode";

export default function UniqueNode({ data, selected }: TypedNodeProps<"unique">) {
  return (
    <BaseNode label={data.label || "Unique"} color="bg-cyan-400" selected={selected}>
      Deduplicate rows
    </BaseNode>
  );
}
