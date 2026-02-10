/**
 * Workflow execution controls and status display.
 *
 * Wires up useExecution hook for run/cancel and real-time status via WebSocket.
 */

import { useExecution } from "../hooks/useExecution";
import { apiClient } from "@/shared/query-engine/client";

interface ExecutionStatusProps {
  workflowId: string;
}

export default function ExecutionStatus({ workflowId }: ExecutionStatusProps) {
  const { execute, isExecuting, status, error } = useExecution(workflowId);

  const isRunning =
    isExecuting || status?.status === "pending" || status?.status === "running";
  const isFailed = status?.status === "failed";
  const isCompleted = status?.status === "completed";
  const isCancelled = status?.status === "cancelled";

  const handleCancel = () => {
    if (status?.id) {
      apiClient.post(`/api/v1/executions/${status.id}/cancel`);
    }
  };

  return (
    <div className="flex items-center gap-2">
      {isRunning ? (
        <button
          onClick={handleCancel}
          className="px-3 py-1 text-xs bg-red-600 text-white rounded hover:opacity-80"
        >
          Cancel
        </button>
      ) : (
        <button
          className="px-3 py-1 text-xs bg-canvas-accent text-white rounded hover:opacity-80 disabled:opacity-50"
          disabled={isRunning}
          onClick={() => execute()}
        >
          Run
        </button>
      )}

      <div className="flex items-center gap-1.5">
        {/* Status indicator dot */}
        <span
          className={`inline-block w-2 h-2 rounded-full ${
            isRunning
              ? "bg-yellow-400 animate-pulse"
              : isFailed
                ? "bg-red-500"
                : isCompleted
                  ? "bg-green-500"
                  : isCancelled
                    ? "bg-orange-400"
                    : "bg-white/20"
          }`}
        />

        <span className="text-xs text-white/40">
          {isRunning
            ? "Running..."
            : isFailed
              ? "Failed"
              : isCompleted
                ? "Completed"
                : isCancelled
                  ? "Cancelled"
                  : "Ready"}
        </span>
      </div>

      {isFailed && error && (
        <span className="text-xs text-red-400 truncate max-w-[200px]" title={error.message}>
          {error.message}
        </span>
      )}
    </div>
  );
}
