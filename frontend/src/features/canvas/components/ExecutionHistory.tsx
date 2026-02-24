/**
 * ExecutionHistory — table of past workflow executions.
 *
 * Displays paginated history from PostgreSQL (persistent).
 * Separate from the real-time ExecutionStatus component (Redis/WS).
 */

import { useState } from "react";
import { useExecutionHistory } from "../hooks/useExecutionHistory";
import type { ExecutionHistoryItem } from "@/shared/query-engine/types";

interface ExecutionHistoryProps {
  workflowId: string | undefined;
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    completed: "bg-green-500/20 text-green-400",
    failed: "bg-red-500/20 text-red-400",
    running: "bg-yellow-500/20 text-yellow-400",
    pending: "bg-gray-500/20 text-gray-400",
    cancelled: "bg-orange-500/20 text-orange-400",
  };
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${colors[status] ?? colors.pending}`}
    >
      {status}
    </span>
  );
}

function formatDuration(startedAt: string | null, completedAt: string | null): string {
  if (!startedAt || !completedAt) return "-";
  const ms = new Date(completedAt).getTime() - new Date(startedAt).getTime();
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.floor(ms / 60_000)}m ${Math.round((ms % 60_000) / 1000)}s`;
}

function formatTimestamp(iso: string | null): string {
  if (!iso) return "-";
  return new Date(iso).toLocaleString();
}

export function ExecutionHistory({ workflowId }: ExecutionHistoryProps) {
  const [page, setPage] = useState(1);
  const { data, isLoading, error } = useExecutionHistory(workflowId, page);

  if (!workflowId) return null;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8 text-gray-400">
        Loading execution history...
      </div>
    );
  }

  if (error) {
    return (
      <div className="py-4 text-center text-sm text-red-400">Failed to load execution history</div>
    );
  }

  if (!data || data.items.length === 0) {
    return <div className="py-8 text-center text-sm text-gray-500">No executions yet</div>;
  }

  const totalPages = Math.ceil(data.total / data.page_size);

  return (
    <div className="flex flex-col gap-2">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-gray-700 text-xs uppercase text-gray-400">
            <th className="px-3 py-2">Status</th>
            <th className="px-3 py-2">Started</th>
            <th className="px-3 py-2">Duration</th>
            <th className="px-3 py-2">Error</th>
          </tr>
        </thead>
        <tbody>
          {data.items.map((item: ExecutionHistoryItem) => (
            <tr key={item.id} className="border-b border-gray-800 hover:bg-gray-800/50">
              <td className="px-3 py-2">
                <StatusBadge status={item.status} />
              </td>
              <td className="px-3 py-2 text-gray-300">{formatTimestamp(item.started_at)}</td>
              <td className="px-3 py-2 text-gray-300">
                {formatDuration(item.started_at, item.completed_at)}
              </td>
              <td
                className="max-w-[200px] truncate px-3 py-2 text-gray-400"
                title={item.error_message ?? undefined}
              >
                {item.error_message ?? "-"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {totalPages > 1 && (
        <div className="flex items-center justify-between px-3 py-2 text-sm text-gray-400">
          <span>
            Page {data.page} of {totalPages} ({data.total} total)
          </span>
          <div className="flex gap-2">
            <button
              className="rounded px-2 py-1 hover:bg-gray-700 disabled:opacity-50"
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
            >
              Previous
            </button>
            <button
              className="rounded px-2 py-1 hover:bg-gray-700 disabled:opacity-50"
              disabled={page >= totalPages}
              onClick={() => setPage((p) => p + 1)}
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
