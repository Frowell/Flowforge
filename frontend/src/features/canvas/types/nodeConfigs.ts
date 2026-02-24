/**
 * Per-node-type config interfaces and typed NodeProps helpers.
 *
 * Fixes M10 (double-cast NodeProps) and M11 (untyped node configs).
 *
 * Usage in node components:
 *   import type { TypedNodeProps } from "../types/nodeConfigs";
 *   export default function FilterNode({ data, selected }: TypedNodeProps<"filter">) { ... }
 */

import type { Node, NodeProps } from "@xyflow/react";
import type { NodeType, ColumnSchema } from "@/shared/schema/types";

// ---------------------------------------------------------------------------
// Per-node config interfaces (all fields optional — nodes may be unconfigured)
// ---------------------------------------------------------------------------

export interface DataSourceConfig {
  table?: string;
  columns?: ColumnSchema[];
  source?: string;
}

export interface FilterConfig {
  column?: string;
  operator?: string;
  value?: string;
}

export interface SelectConfig {
  columns?: string[];
}

export interface RenameConfig {
  rename_map?: Record<string, string>;
}

export interface SortRule {
  column: string;
  direction: string;
}

export interface SortConfig {
  column?: string;
  direction?: string;
  sort_by?: SortRule[];
}

export interface Aggregation {
  column: string;
  function: string;
  alias: string;
}

export interface GroupByConfig {
  group_columns?: string[];
  aggregations?: Aggregation[];
  agg_column?: string;
  agg_function?: string;
}

export interface JoinConfig {
  join_type?: string;
  left_key?: string;
  right_key?: string;
}

export type UnionConfig = Record<string, unknown>;

export interface PivotConfig {
  row_columns?: string[];
  pivot_column?: string;
  value_column?: string;
  aggregation?: string;
}

export interface FormulaConfig {
  expression?: string;
  output_column?: string;
  output_dtype?: string;
}

export type UniqueConfig = Record<string, unknown>;

export interface SampleConfig {
  count?: number;
}

export interface LimitConfig {
  limit?: number;
  offset?: number;
}

export interface WindowConfig {
  function?: string;
  source_column?: string;
  partition_by?: string[];
  order_by?: string;
  order_direction?: string;
  output_column?: string;
}

export interface ChartOutputConfig {
  chart_type?: string;
}

export interface TableOutputConfig {
  title?: string;
  rows_per_page?: number;
}

export interface KPIOutputConfig {
  value_column?: string;
  title?: string;
  format?: string;
  compare_column?: string;
  prefix?: string;
  suffix?: string;
}

// ---------------------------------------------------------------------------
// Config map: NodeType string → config interface
// ---------------------------------------------------------------------------

export interface NodeConfigMap {
  data_source: DataSourceConfig;
  filter: FilterConfig;
  select: SelectConfig;
  rename: RenameConfig;
  sort: SortConfig;
  group_by: GroupByConfig;
  join: JoinConfig;
  union: UnionConfig;
  pivot: PivotConfig;
  formula: FormulaConfig;
  unique: UniqueConfig;
  sample: SampleConfig;
  limit: LimitConfig;
  window: WindowConfig;
  chart_output: ChartOutputConfig;
  table_output: TableOutputConfig;
  kpi_output: KPIOutputConfig;
}

// ---------------------------------------------------------------------------
// WorkflowNodeData — the base interface (unchanged, used by store)
// ---------------------------------------------------------------------------

export interface WorkflowNodeData extends Record<string, unknown> {
  label: string;
  nodeType: string;
  config: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Typed variants for node components
// ---------------------------------------------------------------------------

/** Node data with typed config for a specific node type. */
export interface TypedNodeData<T extends NodeType> extends Record<string, unknown> {
  label: string;
  nodeType: T;
  config: NodeConfigMap[T];
}

/** A React Flow `Node` parameterized for a specific workflow node type. */
export type WorkflowNode<T extends NodeType> = Node<TypedNodeData<T>, T>;

/** Typed props for custom node components — replaces `NodeProps` + double-cast. */
export type TypedNodeProps<T extends NodeType> = NodeProps<WorkflowNode<T>>;
