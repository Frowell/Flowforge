import type { TypedNodeProps } from "../types/nodeConfigs";
import BaseNode from "./BaseNode";

export default function JoinNode({ data, selected }: TypedNodeProps<"join">) {
  const joinType = data.config?.join_type ?? "inner";

  return (
    <BaseNode label={data.label || "Join"} color="bg-purple-400" selected={selected} inputPorts={2}>
      {joinType.toUpperCase()} JOIN
    </BaseNode>
  );
}
