/**
 * Workflow execution hook — runs workflow, tracks status via WebSocket.
 *
 * Status is stored in TanStack Query cache so it survives unmount
 * and is accessible from any component via the same query key.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { apiClient } from "@/shared/query-engine/client";
import { wsManager } from "@/shared/websocket/manager";
import type { ExecutionStatusResponse } from "@/shared/query-engine/types";

function executionQueryKey(workflowId: string | undefined, executionId: string | undefined) {
  return ["execution", workflowId, executionId] as const;
}

export function useExecution(workflowId: string | undefined) {
  const queryClient = useQueryClient();
  const executionIdRef = useRef<string | undefined>(undefined);

  const executeMutation = useMutation({
    mutationFn: () =>
      apiClient.post<ExecutionStatusResponse>("/api/v1/executions", {
        workflow_id: workflowId,
      }),
    onSuccess: (data) => {
      executionIdRef.current = data.id;
      queryClient.setQueryData(executionQueryKey(workflowId, data.id), data);
    },
  });

  const executionId = executionIdRef.current;

  const { data: status = null } = useQuery<ExecutionStatusResponse | null>({
    queryKey: executionQueryKey(workflowId, executionId),
    enabled: !!executionId,
    staleTime: Infinity,
    queryFn: () => null,
  });

  // Subscribe to execution status updates via WebSocket
  useEffect(() => {
    if (!executionId) return;

    const unsubscribe = wsManager.subscribe("execution_status", (message) => {
      const msg = message as ExecutionStatusResponse & { type: string };
      if (msg.id === executionId) {
        queryClient.setQueryData(
          executionQueryKey(workflowId, executionId),
          (prev: ExecutionStatusResponse | null | undefined) => (prev ? { ...prev, ...msg } : msg),
        );

        // Invalidate execution history when execution finishes
        if (msg.status === "completed" || msg.status === "failed" || msg.status === "cancelled") {
          queryClient.invalidateQueries({ queryKey: ["execution-history", workflowId] });
        }
      }
    });

    return unsubscribe;
  }, [executionId, workflowId, queryClient]);

  return {
    execute: executeMutation.mutate,
    isExecuting: executeMutation.isPending,
    status,
    error: executeMutation.error,
  };
}
