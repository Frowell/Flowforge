/**
 * Workflow version hooks — list, get, and rollback via TanStack Query.
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/shared/query-engine/client";
import type { WorkflowResponse, WorkflowVersionResponse } from "@/shared/query-engine/types";
import { WORKFLOWS_KEY, VERSIONS_KEY } from "./queryKeys";

export function useWorkflowVersions(workflowId: string | undefined) {
  return useQuery({
    queryKey: [...VERSIONS_KEY, workflowId],
    queryFn: () =>
      apiClient.get<{ items: WorkflowVersionResponse[]; total: number }>(
        `/api/v1/workflows/${workflowId}/versions`,
      ),
    enabled: !!workflowId,
  });
}

export function useWorkflowVersion(workflowId: string | undefined, versionId: string | undefined) {
  return useQuery({
    queryKey: [...VERSIONS_KEY, workflowId, versionId],
    queryFn: () =>
      apiClient.get<WorkflowVersionResponse>(
        `/api/v1/workflows/${workflowId}/versions/${versionId}`,
      ),
    enabled: !!workflowId && !!versionId,
  });
}

export function useRollbackWorkflow() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ workflowId, versionId }: { workflowId: string; versionId: string }) =>
      apiClient.post<WorkflowResponse>(
        `/api/v1/workflows/${workflowId}/versions/${versionId}/rollback`,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: WORKFLOWS_KEY });
      queryClient.invalidateQueries({ queryKey: VERSIONS_KEY });
    },
  });
}
