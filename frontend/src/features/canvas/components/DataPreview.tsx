/**
 * Node output data preview — shows paginated rows of the selected node's output.
 */

import { useState } from "react";
import { useParams } from "react-router-dom";
import { useWorkflowStore } from "../stores/workflowStore";
import { useDataPreview } from "../hooks/useDataPreview";
import DataGrid from "@/shared/components/DataGrid";

export default function DataPreview() {
  const { workflowId } = useParams<{ workflowId: string }>();
  const selectedNodeId = useWorkflowStore((s) => s.selectedNodeId);
  const nodes = useWorkflowStore((s) => s.nodes);
  const edges = useWorkflowStore((s) => s.edges);

  const [dismissedStale, setDismissedStale] = useState(false);

  const { data, isLoading, error, offset, nextPage, prevPage, dataUpdatedAt, refetch } = useDataPreview({
    workflowId,
    nodeId: selectedNodeId,
    nodes,
    edges,
  });

  if (!selectedNodeId) return null;

  // Show stale indicator when cache_hit and data is older than 5 minutes
  const isStale = data?.cache_hit && dataUpdatedAt
    ? Date.now() - dataUpdatedAt > 5 * 60 * 1000
    : false;

  const rangeStart = data ? data.offset + 1 : 0;
  const rangeEnd = data ? Math.min(data.offset + data.limit, data.total_estimate) : 0;
  const hasPrev = offset > 0;
  const hasNext = data ? offset + data.limit < data.total_estimate : false;

  return (
    <div className="h-48 border-t border-canvas-border bg-canvas-node">
      <div className="flex items-center px-4 py-2 border-b border-canvas-border">
        <h3 className="text-xs font-medium text-white/60 uppercase">Data Preview</h3>
        {data && (
          <>
            <span className="ml-2 text-xs text-white/30">
              rows {rangeStart}&ndash;{rangeEnd} of {data.total_estimate}
            </span>
            <div className="ml-auto flex items-center gap-2">
              <button
                onClick={prevPage}
                disabled={!hasPrev}
                className="px-2 py-0.5 text-xs text-white/60 border border-canvas-border rounded disabled:opacity-30 disabled:cursor-not-allowed hover:bg-white/10"
              >
                Prev
              </button>
              <button
                onClick={nextPage}
                disabled={!hasNext}
                className="px-2 py-0.5 text-xs text-white/60 border border-canvas-border rounded disabled:opacity-30 disabled:cursor-not-allowed hover:bg-white/10"
              >
                Next
              </button>
              <span className="text-xs text-white/30">{data.execution_ms}ms</span>
              {data.cache_hit && <span className="text-xs text-green-400/60">cached</span>}
            </div>
          </>
        )}
        {isLoading && (
          <span className="ml-auto text-xs text-white/30 animate-pulse">Loading...</span>
        )}
      </div>
      {error && <div className="px-4 py-2 text-xs text-red-400">{error.message}</div>}
      {isStale && !dismissedStale && (
        <div className="flex items-center gap-2 px-4 py-1.5 bg-yellow-500/10 border-b border-yellow-500/20">
          <span className="text-xs text-yellow-300">Schema may be outdated</span>
          <button
            onClick={() => { refetch(); setDismissedStale(true); }}
            className="text-xs text-yellow-300 underline hover:text-yellow-200"
          >
            Refresh
          </button>
        </div>
      )}
      <div className="h-[calc(100%-36px)] overflow-auto">
        <DataGrid columns={data?.columns ?? []} rows={data?.rows ?? []} />
      </div>
    </div>
  );
}
