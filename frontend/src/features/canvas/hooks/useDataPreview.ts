/**
 * Data preview hook — Layer 1: debounce + cancellation + pagination.
 *
 * 300ms debounce on node/config changes.
 * AbortController cancels in-flight requests on new triggers or unmount.
 * Offset resets to 0 on node or graph config change; pagination fires immediately.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { apiClient } from "@/shared/query-engine/client";
import type { PreviewResponse } from "@/shared/query-engine/types";
import type { Node, Edge } from "@xyflow/react";

const DEBOUNCE_MS = 300;
const DEFAULT_PAGE_SIZE = 100;

interface UseDataPreviewOptions {
  workflowId: string | undefined;
  nodeId: string | null;
  nodes: Node[];
  edges: Edge[];
}

export function useDataPreview({ workflowId, nodeId, nodes, edges }: UseDataPreviewOptions) {
  const [data, setData] = useState<PreviewResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [offset, setOffset] = useState(0);
  const [dataUpdatedAt, setDataUpdatedAt] = useState<number | null>(null);
  const [refetchTrigger, setRefetchTrigger] = useState(0);
  const abortRef = useRef<AbortController | null>(null);

  // Reset offset when node or graph config changes
  const prevNodeIdRef = useRef(nodeId);
  const prevNodesRef = useRef(nodes);
  const prevEdgesRef = useRef(edges);

  useEffect(() => {
    const nodeChanged = prevNodeIdRef.current !== nodeId;
    const graphChanged = prevNodesRef.current !== nodes || prevEdgesRef.current !== edges;

    prevNodeIdRef.current = nodeId;
    prevNodesRef.current = nodes;
    prevEdgesRef.current = edges;

    if (nodeChanged || graphChanged) {
      setOffset(0);
    }
  }, [nodeId, nodes, edges]);

  useEffect(() => {
    if (!workflowId || !nodeId) {
      setData(null);
      setIsLoading(false);
      setError(null);
      return;
    }

    setIsLoading(true);

    const timer = setTimeout(() => {
      // Abort any in-flight request
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      const serializedNodes = nodes.map((n) => ({
        id: n.id,
        type: n.type,
        data: n.data,
        position: n.position,
      }));

      const serializedEdges = edges.map((e) => ({
        id: e.id,
        source: e.source,
        target: e.target,
        sourceHandle: e.sourceHandle,
        targetHandle: e.targetHandle,
      }));

      apiClient
        .post<PreviewResponse>(
          "/api/v1/executions/preview",
          {
            workflow_id: workflowId,
            target_node_id: nodeId,
            graph: { nodes: serializedNodes, edges: serializedEdges },
            offset,
            limit: DEFAULT_PAGE_SIZE,
          },
          controller.signal,
        )
        .then((result) => {
          setData(result);
          setError(null);
          setDataUpdatedAt(Date.now());
        })
        .catch((err) => {
          if (err instanceof DOMException && err.name === "AbortError") return;
          setError(err);
        })
        .finally(() => {
          if (!controller.signal.aborted) {
            setIsLoading(false);
          }
        });
    }, DEBOUNCE_MS);

    return () => {
      clearTimeout(timer);
      abortRef.current?.abort();
    };
  }, [workflowId, nodeId, nodes, edges, offset, refetchTrigger]);

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

  const refetch = useCallback(() => {
    setRefetchTrigger((prev) => prev + 1);
  }, []);

  return { data, isLoading, error, offset, nextPage, prevPage, setOffset, dataUpdatedAt, refetch };
}
