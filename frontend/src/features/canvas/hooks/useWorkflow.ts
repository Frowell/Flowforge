/**
 * Workflow CRUD hook — save, load, list, delete via TanStack Query.
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/shared/query-engine/client";
import type { WorkflowResponse, PaginatedResponse } from "@/shared/query-engine/types";
import { useWorkflowStore } from "../stores/workflowStore";
import { WORKFLOWS_KEY, VERSIONS_KEY } from "./queryKeys";

export function useWorkflowList(page = 1, pageSize = 20) {
  return useQuery({
    queryKey: [...WORKFLOWS_KEY, page, pageSize],
    queryFn: () =>
      apiClient.get<PaginatedResponse<WorkflowResponse>>(
        `/api/v1/workflows?page=${page}&page_size=${pageSize}`,
      ),
  });
}

export function useWorkflow(workflowId: string | undefined) {
  return useQuery({
    queryKey: [...WORKFLOWS_KEY, workflowId],
    queryFn: () => apiClient.get<WorkflowResponse>(`/api/v1/workflows/${workflowId}`),
    enabled: !!workflowId,
  });
}

export function useSaveWorkflow() {
  const queryClient = useQueryClient();
  const { nodes, edges } = useWorkflowStore();

  return useMutation({
    mutationFn: async ({ id, name }: { id?: string; name: string }) => {
      const graphJson = { nodes, edges };
      if (id) {
        return apiClient.patch<WorkflowResponse>(`/api/v1/workflows/${id}`, {
          name,
          graph_json: graphJson,
        });
      }
      return apiClient.post<WorkflowResponse>("/api/v1/workflows", {
        name,
        graph_json: graphJson,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: WORKFLOWS_KEY });
      queryClient.invalidateQueries({ queryKey: VERSIONS_KEY });
    },
  });
}

export function useDeleteWorkflow() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (workflowId: string) => apiClient.delete(`/api/v1/workflows/${workflowId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: WORKFLOWS_KEY });
    },
  });
}
