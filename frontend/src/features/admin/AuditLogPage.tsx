/**
 * Audit log admin page — paginated table with filter dropdowns.
 *
 * Only accessible to admin users.
 */

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/shared/query-engine/client";

interface AuditLogEntry {
  id: string;
  tenant_id: string;
  user_id: string;
  action: string;
  resource_type: string;
  resource_id: string;
  metadata: Record<string, unknown> | null;
  created_at: string;
}

interface AuditLogListResponse {
  items: AuditLogEntry[];
  total: number;
  offset: number;
  limit: number;
}

const RESOURCE_TYPES = ["workflow", "dashboard", "widget", "api_key"] as const;
const ACTIONS = ["created", "updated", "deleted", "executed"] as const;

const ACTION_COLORS: Record<string, string> = {
  created: "bg-emerald-500/20 text-emerald-300",
  updated: "bg-blue-500/20 text-blue-300",
  deleted: "bg-red-500/20 text-red-300",
  executed: "bg-purple-500/20 text-purple-300",
  revoked: "bg-orange-500/20 text-orange-300",
};

const PAGE_SIZE = 25;

export default function AuditLogPage() {
  const [offset, setOffset] = useState(0);
  const [resourceType, setResourceType] = useState<string>("");
  const [action, setAction] = useState<string>("");

  const params: Record<string, string> = {
    limit: String(PAGE_SIZE),
    offset: String(offset),
  };
  if (resourceType) params.resource_type = resourceType;
  if (action) params.action = action;

  const { data, isLoading, error } = useQuery({
    queryKey: ["auditLogs", offset, resourceType, action],
    queryFn: () => apiClient.get<AuditLogListResponse>("/api/v1/audit-logs", params),
  });

  const hasPrev = offset > 0;
  const hasNext = data ? offset + PAGE_SIZE < data.total : false;

  return (
    <div className="h-[calc(100vh-3rem)] w-screen flex flex-col bg-canvas-bg">
      <div className="h-10 border-b border-canvas-border flex items-center px-4 shrink-0 justify-between">
        <h1 className="text-sm font-medium text-white/80">Audit Log</h1>
        <div className="flex items-center gap-3">
          <select
            value={resourceType}
            onChange={(e) => {
              setResourceType(e.target.value);
              setOffset(0);
            }}
            className="bg-canvas-node text-xs text-white/80 border border-canvas-border rounded px-2 py-1"
          >
            <option value="">All resources</option>
            {RESOURCE_TYPES.map((rt) => (
              <option key={rt} value={rt}>
                {rt}
              </option>
            ))}
          </select>
          <select
            value={action}
            onChange={(e) => {
              setAction(e.target.value);
              setOffset(0);
            }}
            className="bg-canvas-node text-xs text-white/80 border border-canvas-border rounded px-2 py-1"
          >
            <option value="">All actions</option>
            {ACTIONS.map((a) => (
              <option key={a} value={a}>
                {a}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="flex-1 overflow-auto">
        {isLoading && (
          <div className="flex items-center justify-center h-32">
            <span className="text-white/30 text-sm animate-pulse">Loading...</span>
          </div>
        )}

        {error && (
          <div className="flex items-center justify-center h-32">
            <span className="text-red-400 text-sm">
              {error instanceof Error ? error.message : "Failed to load audit logs"}
            </span>
          </div>
        )}

        {data && data.items.length === 0 && (
          <div className="flex items-center justify-center h-32">
            <span className="text-white/30 text-sm">No audit events found</span>
          </div>
        )}

        {data && data.items.length > 0 && (
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-canvas-border text-white/40 uppercase tracking-wider">
                <th className="text-left px-4 py-2 font-medium">Time</th>
                <th className="text-left px-4 py-2 font-medium">Action</th>
                <th className="text-left px-4 py-2 font-medium">Resource</th>
                <th className="text-left px-4 py-2 font-medium">Resource ID</th>
                <th className="text-left px-4 py-2 font-medium">User ID</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((entry) => (
                <tr key={entry.id} className="border-b border-canvas-border/50 hover:bg-white/5">
                  <td className="px-4 py-2 text-white/60 whitespace-nowrap">
                    {new Date(entry.created_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-2">
                    <span
                      className={`inline-block px-2 py-0.5 rounded text-[10px] font-medium ${
                        ACTION_COLORS[entry.action] ?? "bg-white/10 text-white/60"
                      }`}
                    >
                      {entry.action}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-white/60">{entry.resource_type}</td>
                  <td className="px-4 py-2 text-white/40 font-mono">
                    {entry.resource_id.slice(0, 8)}...
                  </td>
                  <td className="px-4 py-2 text-white/40 font-mono">
                    {entry.user_id.slice(0, 8)}...
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {data && (
        <div className="h-10 border-t border-canvas-border flex items-center justify-between px-4 shrink-0">
          <span className="text-xs text-white/30">{data.total} total events</span>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
              disabled={!hasPrev}
              className="px-2 py-1 text-xs text-white/60 border border-canvas-border rounded disabled:opacity-30 disabled:cursor-not-allowed hover:bg-white/10"
            >
              Prev
            </button>
            <span className="text-xs text-white/40">
              {offset + 1}&ndash;{Math.min(offset + PAGE_SIZE, data.total)}
            </span>
            <button
              onClick={() => setOffset(offset + PAGE_SIZE)}
              disabled={!hasNext}
              className="px-2 py-1 text-xs text-white/60 border border-canvas-border rounded disabled:opacity-30 disabled:cursor-not-allowed hover:bg-white/10"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
