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
import type { WorkflowNode, WorkflowEdge } from "@/shared/schema/propagation";

/**
 * Returns a map of nodeId -> outputSchema for the current workflow graph.
 * Recomputes synchronously whenever nodes or edges change.
 */
export function useSchemaEngine(): Map<string, ColumnSchema[]> {
  const nodes = useWorkflowStore((s) => s.nodes);
  const edges = useWorkflowStore((s) => s.edges);

  return useMemo(() => {
    try {
      const workflowNodes: WorkflowNode[] = nodes.map((n) => ({
        id: n.id,
        type: n.data.nodeType as WorkflowNode["type"],
        data: { config: n.data.config },
      }));

      const workflowEdges: WorkflowEdge[] = edges.map((e) => ({
        source: e.source,
        target: e.target,
      }));

      return propagateSchemas(workflowNodes, workflowEdges);
    } catch {
      return new Map();
    }
  }, [nodes, edges]);
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
