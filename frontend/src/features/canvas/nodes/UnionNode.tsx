import type { TypedNodeProps } from "../types/nodeConfigs";
import BaseNode from "./BaseNode";

export default function UnionNode({ data, selected }: TypedNodeProps<"union">) {
  return (
    <BaseNode
      label={data.label || "Union"}
      color="bg-purple-400"
      selected={selected}
      inputPorts={2}
    >
      UNION ALL
    </BaseNode>
  );
}
