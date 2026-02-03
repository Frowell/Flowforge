/**
 * Schema type definitions — shared between registry, propagation, and canvas nodes.
 *
 * These types must stay in sync with backend/app/schemas/schema.py.
 */

export interface ColumnSchema {
  name: string;
  dtype: "string" | "int64" | "float64" | "bool" | "datetime" | "object";
  nullable: boolean;
  description?: string;
}

export interface TableSchema {
  name: string;
  database: string;
  source: "clickhouse" | "materialize" | "redis";
  columns: ColumnSchema[];
}

export interface CatalogResponse {
  tables: TableSchema[];
}

/**
 * Schema transform function signature.
 * Each node type registers one of these.
 */
export type SchemaTransformFn = (
  config: Record<string, unknown>,
  inputs: ColumnSchema[][],
) => ColumnSchema[];

/**
 * Node type identifiers — must match backend node type strings.
 */
export type NodeType =
  | "data_source"
  | "filter"
  | "select"
  | "rename"
  | "sort"
  | "join"
  | "union"
  | "group_by"
  | "pivot"
  | "formula"
  | "unique"
  | "sample"
  | "limit"
  | "window"
  | "chart_output"
  | "table_output"
  | "kpi_output";
