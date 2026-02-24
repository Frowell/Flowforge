import type { TypedNodeProps } from "../types/nodeConfigs";
import BaseNode from "./BaseNode";

export default function RenameNode({ data, selected }: TypedNodeProps<"rename">) {
  const renameMap = data.config?.rename_map ?? {};
  const count = Object.keys(renameMap).length;

  return (
    <BaseNode label={data.label || "Rename"} color="bg-cyan-400" selected={selected}>
      {count > 0 ? `${count} renamed` : "No renames"}
    </BaseNode>
  );
}
