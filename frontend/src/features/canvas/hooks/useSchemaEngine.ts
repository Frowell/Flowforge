/**
 * Client-side schema propagation hook.
 *
 * Runs the synchronous schema engine on every connection change
 * to provide instant feedback (dropdown population, type errors).
 */

import { useMemo } from "react";
import { propagateSchemas } from "@/shared/schema/propagation";
import type { ColumnSchema } from "@/shared/schema/types";
import { useWorkflowStore } from "../stores/workflowStore";
import type { WorkflowNode } from "@/shared/schema/propagation";

/**
 * Returns a map of nodeId -> outputSchema for the current workflow graph.
 * Recomputes synchronously whenever nodes or edges change.
 */
export function useSchemaEngine(): Map<string, ColumnSchema[]> {
  const nodes = useWorkflowStore((s) => s.nodes);
  const edges = useWorkflowStore((s) => s.edges);

  // Extract only structural properties — position changes don't affect schemas
  const structuralNodes = useMemo(
    () => nodes.map((n) => ({ id: n.id, type: n.type, config: n.data.config })),
    [nodes],
  );
  const structuralEdges = useMemo(
    () => edges.map((e) => ({ source: e.source, target: e.target })),
    [edges],
  );

  // Stable key that only changes when structure changes, not on drag
  const structureKey = useMemo(
    () => JSON.stringify({ n: structuralNodes, e: structuralEdges }),
    [structuralNodes, structuralEdges],
  );

  return useMemo(() => {
    try {
      const workflowNodes: WorkflowNode[] = structuralNodes.map((n) => ({
        id: n.id,
        type: n.type as WorkflowNode["type"],
        data: { config: n.config },
      }));

      return propagateSchemas(workflowNodes, structuralEdges);
    } catch {
      return new Map();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [structureKey]);
}

/**
 * Get the output schema for a specific node.
 */
export function useNodeOutputSchema(nodeId: string | null): ColumnSchema[] {
  const schemas = useSchemaEngine();
  if (!nodeId) return [];
  return schemas.get(nodeId) ?? [];
}

/**
 * Get the input schema for a specific node (from its upstream connections).
 */
export function useNodeInputSchema(nodeId: string | null): ColumnSchema[] {
  const schemas = useSchemaEngine();
  const edges = useWorkflowStore((s) => s.edges);

  if (!nodeId) return [];

  const sourceEdge = edges.find((e) => e.target === nodeId);
  if (!sourceEdge) return [];

  return schemas.get(sourceEdge.source) ?? [];
}

/**
 * Get ALL input schemas for a node (array of arrays).
 * Needed for multi-input nodes like Join and Union.
 */
export function useNodeInputSchemas(nodeId: string | null): ColumnSchema[][] {
  const schemas = useSchemaEngine();
  const edges = useWorkflowStore((s) => s.edges);

  if (!nodeId) return [];

  return edges.filter((e) => e.target === nodeId).map((e) => schemas.get(e.source) ?? []);
}
