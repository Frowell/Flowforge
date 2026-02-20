/**
 * Data preview hook — debounced preview via TanStack Query.
 *
 * 300ms debounce on node/config changes via stable query key.
 * Built-in signal for automatic request cancellation.
 * placeholderData keeps previous results during pagination.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { apiClient } from "@/shared/query-engine/client";
import type { PreviewResponse } from "@/shared/query-engine/types";
import type { Node, Edge } from "@xyflow/react";

const DEBOUNCE_MS = 300;
const DEFAULT_PAGE_SIZE = 100;
const STALE_TIME = 5 * 60 * 1000; // 5 minutes — matches server-side Redis cache TTL

interface UseDataPreviewOptions {
  workflowId: string | undefined;
  nodeId: string | null;
  nodes: Node[];
  edges: Edge[];
}

export function useDataPreview({ workflowId, nodeId, nodes, edges }: UseDataPreviewOptions) {
  const [offset, setOffset] = useState(0);
  const [debouncedKey, setDebouncedKey] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  // Extract only structural data for the query key (ignore positions)
  const structureKey = useMemo(() => {
    if (!workflowId || !nodeId) return null;
    const n = nodes.map((node) => ({
      id: node.id,
      type: node.type,
      data: node.data,
    }));
    const e = edges.map((edge) => ({
      source: edge.source,
      target: edge.target,
    }));
    return JSON.stringify({ workflowId, nodeId, n, e });
  }, [workflowId, nodeId, nodes, edges]);

  // Reset offset when node or graph structure changes
  const prevStructureKeyRef = useRef(structureKey);
  useEffect(() => {
    if (prevStructureKeyRef.current !== structureKey) {
      prevStructureKeyRef.current = structureKey;
      setOffset(0);
    }
  }, [structureKey]);

  // Debounce structure changes (not pagination)
  useEffect(() => {
    clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      setDebouncedKey(structureKey);
    }, DEBOUNCE_MS);
    return () => clearTimeout(timerRef.current);
  }, [structureKey]);

  const enabled = !!debouncedKey && !!workflowId && !!nodeId;

  const serializedNodes = useMemo(
    () =>
      nodes.map((n) => ({
        id: n.id,
        type: n.type,
        data: n.data,
        position: n.position,
      })),
    [nodes],
  );

  const serializedEdges = useMemo(
    () =>
      edges.map((e) => ({
        id: e.id,
        source: e.source,
        target: e.target,
        sourceHandle: e.sourceHandle,
        targetHandle: e.targetHandle,
      })),
    [edges],
  );

  const { data, isLoading, error, dataUpdatedAt, refetch } = useQuery({
    queryKey: ["preview", debouncedKey, offset] as const,
    queryFn: ({ signal }) =>
      apiClient.post<PreviewResponse>(
        "/api/v1/executions/preview",
        {
          workflow_id: workflowId,
          target_node_id: nodeId,
          graph: { nodes: serializedNodes, edges: serializedEdges },
          offset,
          limit: DEFAULT_PAGE_SIZE,
        },
        signal,
      ),
    enabled,
    staleTime: STALE_TIME,
    placeholderData: keepPreviousData,
  });

  const nextPage = useCallback(() => {
    if (data && offset + data.limit < data.total_estimate) {
      setOffset((prev) => prev + (data?.limit ?? DEFAULT_PAGE_SIZE));
    }
  }, [data, offset]);

  const prevPage = useCallback(() => {
    if (offset > 0) {
      setOffset((prev) => Math.max(0, prev - (data?.limit ?? DEFAULT_PAGE_SIZE)));
    }
  }, [data, offset]);

  return {
    data: data ?? null,
    isLoading,
    error: error as Error | null,
    offset,
    nextPage,
    prevPage,
    setOffset,
    dataUpdatedAt: dataUpdatedAt || null,
    refetch,
  };
}
