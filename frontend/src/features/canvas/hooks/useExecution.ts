/**
 * Workflow execution hook — runs workflow, tracks status via WebSocket.
 */

import { useMutation } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { apiClient } from "@/shared/query-engine/client";
import { wsManager } from "@/shared/websocket/manager";
import type { ExecutionStatusResponse } from "@/shared/query-engine/types";

export function useExecution(workflowId: string | undefined) {
  const [status, setStatus] = useState<ExecutionStatusResponse | null>(null);

  const executeMutation = useMutation({
    mutationFn: () =>
      apiClient.post<ExecutionStatusResponse>("/api/v1/executions", {
        workflow_id: workflowId,
      }),
    onSuccess: (data) => {
      setStatus(data);
    },
  });

  // Subscribe to execution status updates via WebSocket
  useEffect(() => {
    if (!status?.id) return;

    const unsubscribe = wsManager.subscribe("execution_status", (message) => {
      const msg = message as ExecutionStatusResponse & { type: string };
      if (msg.id === status.id) {
        setStatus((prev) => (prev ? { ...prev, ...msg } : prev));
      }
    });

    return unsubscribe;
  }, [status?.id]);

  return {
    execute: executeMutation.mutate,
    isExecuting: executeMutation.isPending,
    status,
    error: executeMutation.error,
  };
}
