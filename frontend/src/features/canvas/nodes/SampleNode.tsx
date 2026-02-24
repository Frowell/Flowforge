import type { TypedNodeProps } from "../types/nodeConfigs";
import BaseNode from "./BaseNode";

export default function SampleNode({ data, selected }: TypedNodeProps<"sample">) {
  const count = data.config?.count;

  return (
    <BaseNode label={data.label || "Sample"} color="bg-cyan-400" selected={selected}>
      {count ? `${count} rows` : "Not configured"}
    </BaseNode>
  );
}
