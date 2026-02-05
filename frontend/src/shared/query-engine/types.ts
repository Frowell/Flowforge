/**
 * API request/response types matching backend Pydantic schemas.
 */

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface WorkflowResponse {
  id: string;
  name: string;
  description: string | null;
  graph_json: Record<string, unknown>;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface WorkflowCreate {
  name: string;
  description?: string;
  graph_json?: Record<string, unknown>;
}

export interface WorkflowUpdate {
  name?: string;
  description?: string;
  graph_json?: Record<string, unknown>;
}

export interface WorkflowVersionResponse {
  id: string;
  workflow_id: string;
  version_number: number;
  graph_json: Record<string, unknown>;
  created_by: string;
  created_at: string;
}

export interface DashboardResponse {
  id: string;
  name: string;
  description: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface WidgetResponse {
  id: string;
  dashboard_id: string;
  source_workflow_id: string;
  source_node_id: string;
  title: string | null;
  layout: { x: number; y: number; w: number; h: number };
  config_overrides: Record<string, unknown>;
  auto_refresh_interval: number | null;
  created_at: string;
  updated_at: string;
}

export interface QueryResultResponse {
  columns: Array<{ name: string; dtype: string }>;
  rows: Record<string, unknown>[];
  total_rows: number;
  truncated: boolean;
}

export interface WidgetDataResponse {
  columns: Array<{ name: string; dtype: string }>;
  rows: Record<string, unknown>[];
  total_rows: number;
  execution_ms: number;
  cache_hit: boolean;
  offset: number;
  limit: number;
  chart_config: Record<string, unknown> | null;
}

export interface PreviewResponse {
  columns: Array<{ name: string; dtype: string }>;
  rows: Record<string, unknown>[];
  total_estimate: number;
  execution_ms: number;
  cache_hit: boolean;
  offset: number;
  limit: number;
}

export interface ExecutionStatusResponse {
  id: string;
  workflow_id: string;
  status: "pending" | "running" | "completed" | "failed";
  started_at: string | null;
  completed_at: string | null;
  node_statuses: Record<
    string,
    {
      status: "pending" | "running" | "completed" | "failed" | "skipped";
      started_at: string | null;
      completed_at: string | null;
      rows_processed: number | null;
      error: string | null;
    }
  >;
}
