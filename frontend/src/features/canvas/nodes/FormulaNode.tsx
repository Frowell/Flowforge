import type { TypedNodeProps } from "../types/nodeConfigs";
import BaseNode from "./BaseNode";

export default function FormulaNode({ data, selected }: TypedNodeProps<"formula">) {
  const expression = data.config?.expression;

  return (
    <BaseNode label={data.label || "Formula"} color="bg-amber-400" selected={selected}>
      {expression
        ? expression.slice(0, 30) + (expression.length > 30 ? "..." : "")
        : "No expression"}
    </BaseNode>
  );
}
