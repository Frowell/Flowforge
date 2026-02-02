/**
 * Client-side schema propagation engine.
 *
 * Synchronous — must complete in < 10ms for a 50-node graph.
 * MUST produce identical results to backend/app/services/schema_engine.py.
 *
 * Runs on every connection change to provide instant feedback:
 * - Populate config panel dropdowns from upstream schemas
 * - Highlight type errors on connect
 */

import type { ColumnSchema, NodeType, SchemaTransformFn } from "./types";

// ── Transform Registry ──────────────────────────────────────────────────

const transforms: Record<string, SchemaTransformFn> = {};

function registerTransform(nodeType: NodeType, fn: SchemaTransformFn) {
  transforms[nodeType] = fn;
}

// Data Source: output from catalog
registerTransform("data_source", (config, _inputs) => {
  const columns = (config.columns ?? []) as ColumnSchema[];
  return columns;
});

// Filter: passthrough
registerTransform("filter", (_config, inputs) => {
  return inputs[0] ? [...inputs[0]] : [];
});

// Select: subset in specified order
registerTransform("select", (config, inputs) => {
  if (!inputs[0]) return [];
  const selectedNames = (config.columns ?? []) as string[];
  const inputByName = new Map(inputs[0].map((col) => [col.name, col]));
  return selectedNames.filter((n) => inputByName.has(n)).map((n) => inputByName.get(n)!);
});

// Rename: name substitutions
registerTransform("rename", (config, inputs) => {
  if (!inputs[0]) return [];
  const renameMap = (config.rename_map ?? {}) as Record<string, string>;
  return inputs[0].map((col) => ({
    ...col,
    name: renameMap[col.name] ?? col.name,
  }));
});

// Sort: passthrough
registerTransform("sort", (_config, inputs) => {
  return inputs[0] ? [...inputs[0]] : [];
});

// Join: merged schemas from both inputs
registerTransform("join", (_config, inputs) => {
  if (inputs.length < 2) return inputs[0] ?? [];
  const leftNames = new Set(inputs[0]!.map((c) => c.name));
  return [...inputs[0]!, ...inputs[1]!.filter((c) => !leftNames.has(c.name))];
});

// Union: columns from first input
registerTransform("union", (_config, inputs) => {
  return inputs[0] ? [...inputs[0]] : [];
});

// Group By: group keys + aggregates
registerTransform("group_by", (config, inputs) => {
  if (!inputs[0]) return [];
  const groupColumns = (config.group_columns ?? []) as string[];
  const aggregations = (config.aggregations ?? []) as Array<{
    column: string;
    function: string;
    alias: string;
    output_dtype: string;
  }>;

  const inputByName = new Map(inputs[0].map((col) => [col.name, col]));
  const output: ColumnSchema[] = [];

  for (const name of groupColumns) {
    const col = inputByName.get(name);
    if (col) output.push(col);
  }

  for (const agg of aggregations) {
    output.push({
      name: agg.alias ?? `${agg.function}_${agg.column}`,
      dtype: (agg.output_dtype as ColumnSchema["dtype"]) ?? "float64",
      nullable: true,
    });
  }

  return output;
});

// Pivot: row dimensions + pivoted value column
registerTransform("pivot", (config, inputs) => {
  if (!inputs[0]) return [];
  const rowColumns = (config.row_columns ?? []) as string[];
  const valueColumn = (config.value_column ?? "") as string;
  const aggregation = (config.aggregation ?? "SUM") as string;

  const inputByName = new Map(inputs[0].map((col) => [col.name, col]));
  const output: ColumnSchema[] = [];

  for (const name of rowColumns) {
    const col = inputByName.get(name);
    if (col) output.push(col);
  }

  if (valueColumn) {
    output.push({
      name: `${valueColumn}_${aggregation.toLowerCase()}`,
      dtype: "float64",
      nullable: true,
    });
  }

  return output;
});

// Formula: input + new calculated column
registerTransform("formula", (config, inputs) => {
  if (!inputs[0]) return [];
  return [
    ...inputs[0],
    {
      name: (config.output_column as string) ?? "calculated",
      dtype: (config.output_dtype as ColumnSchema["dtype"]) ?? "float64",
      nullable: true,
    },
  ];
});

// Unique: passthrough
registerTransform("unique", (_config, inputs) => {
  return inputs[0] ? [...inputs[0]] : [];
});

// Sample: passthrough
registerTransform("sample", (_config, inputs) => {
  return inputs[0] ? [...inputs[0]] : [];
});

// Terminal nodes: no output
registerTransform("chart_output", () => []);
registerTransform("table_output", () => []);

// ── Engine ──────────────────────────────────────────────────────────────

export interface WorkflowNode {
  id: string;
  type: NodeType;
  data: { config: Record<string, unknown> };
}

export interface WorkflowEdge {
  source: string;
  target: string;
}

/**
 * Propagate schemas through the entire DAG.
 *
 * Returns a map of node ID -> output schema.
 * Throws on cycles or unknown node types.
 */
export function propagateSchemas(
  nodes: WorkflowNode[],
  edges: WorkflowEdge[],
): Map<string, ColumnSchema[]> {
  const nodeMap = new Map(nodes.map((n) => [n.id, n]));
  const inbound = new Map<string, string[]>();
  for (const edge of edges) {
    const existing = inbound.get(edge.target) ?? [];
    existing.push(edge.source);
    inbound.set(edge.target, existing);
  }

  // Kahn's topological sort
  const inDegree = new Map<string, number>();
  for (const node of nodes) inDegree.set(node.id, 0);
  for (const edge of edges) {
    inDegree.set(edge.target, (inDegree.get(edge.target) ?? 0) + 1);
  }

  const queue: string[] = [];
  for (const [id, deg] of inDegree) {
    if (deg === 0) queue.push(id);
  }

  const outputSchemas = new Map<string, ColumnSchema[]>();
  let visited = 0;

  while (queue.length > 0) {
    const nodeId = queue.shift()!;
    visited++;
    const node = nodeMap.get(nodeId);
    if (!node) continue;

    const transform = transforms[node.type];
    if (!transform) throw new Error(`Unknown node type: ${node.type}`);

    const inputSchemas = (inbound.get(nodeId) ?? []).map(
      (srcId) => outputSchemas.get(srcId) ?? [],
    );

    outputSchemas.set(nodeId, transform(node.data.config, inputSchemas));

    for (const edge of edges) {
      if (edge.source === nodeId) {
        const newDeg = (inDegree.get(edge.target) ?? 1) - 1;
        inDegree.set(edge.target, newDeg);
        if (newDeg === 0) queue.push(edge.target);
      }
    }
  }

  if (visited !== nodes.length) {
    throw new Error("Workflow contains a cycle");
  }

  return outputSchemas;
}
