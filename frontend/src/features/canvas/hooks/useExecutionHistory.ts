/**
 * Hook for fetching paginated workflow execution history.
 *
 * Reads from the persistent PostgreSQL-backed endpoint,
 * not the real-time Redis/WebSocket status.
 */

import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/shared/query-engine/client";
import type { ExecutionListResponse } from "@/shared/query-engine/types";

export function useExecutionHistory(workflowId: string | undefined, page = 1) {
  return useQuery({
    queryKey: ["execution-history", workflowId, page],
    queryFn: () =>
      apiClient.get<ExecutionListResponse>(`/api/v1/executions/history/${workflowId}`, {
        page: String(page),
      }),
    enabled: !!workflowId,
  });
}
