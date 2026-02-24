import type { TypedNodeProps } from "../types/nodeConfigs";
import BaseNode from "./BaseNode";

export default function TableOutputNode({ data, selected }: TypedNodeProps<"table_output">) {
  return (
    <BaseNode
      label={data.label || "Table View"}
      color="bg-green-400"
      selected={selected}
      outputPorts={0}
    >
      Paginated grid
    </BaseNode>
  );
}
