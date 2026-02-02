/**
 * Workflow canvas Zustand store — UI state only.
 *
 * What belongs here: nodes, edges, selectedNodeId, canvas actions.
 * What does NOT belong: fetched data, schema catalog, execution status, preview results.
 */

import { create } from "zustand";
import type { Node, Edge, OnNodesChange, OnEdgesChange, OnConnect } from "@xyflow/react";
import { applyNodeChanges, applyEdgeChanges, addEdge } from "@xyflow/react";

export interface WorkflowNodeData extends Record<string, unknown> {
  label: string;
  nodeType: string;
  config: Record<string, unknown>;
}

interface WorkflowState {
  // State
  nodes: Node<WorkflowNodeData>[];
  edges: Edge[];
  selectedNodeId: string | null;

  // Actions
  onNodesChange: OnNodesChange;
  onEdgesChange: OnEdgesChange;
  onConnect: OnConnect;
  selectNode: (nodeId: string | null) => void;
  addNode: (node: Node<WorkflowNodeData>) => void;
  removeNode: (nodeId: string) => void;
  updateNodeConfig: (nodeId: string, config: Record<string, unknown>) => void;
  setGraph: (nodes: Node<WorkflowNodeData>[], edges: Edge[]) => void;
  clear: () => void;
}

export const useWorkflowStore = create<WorkflowState>((set, get) => ({
  nodes: [],
  edges: [],
  selectedNodeId: null,

  onNodesChange: (changes) => {
    set({ nodes: applyNodeChanges(changes, get().nodes) as Node<WorkflowNodeData>[] });
  },

  onEdgesChange: (changes) => {
    set({ edges: applyEdgeChanges(changes, get().edges) });
  },

  onConnect: (connection) => {
    set({ edges: addEdge(connection, get().edges) });
  },

  selectNode: (nodeId) => {
    set({ selectedNodeId: nodeId });
  },

  addNode: (node) => {
    set({ nodes: [...get().nodes, node] });
  },

  removeNode: (nodeId) => {
    set({
      nodes: get().nodes.filter((n) => n.id !== nodeId),
      edges: get().edges.filter((e) => e.source !== nodeId && e.target !== nodeId),
      selectedNodeId: get().selectedNodeId === nodeId ? null : get().selectedNodeId,
    });
  },

  updateNodeConfig: (nodeId, config) => {
    set({
      nodes: get().nodes.map((n) =>
        n.id === nodeId ? { ...n, data: { ...n.data, config: { ...n.data.config, ...config } } } : n,
      ),
    });
  },

  setGraph: (nodes, edges) => {
    set({ nodes, edges, selectedNodeId: null });
  },

  clear: () => {
    set({ nodes: [], edges: [], selectedNodeId: null });
  },
}));
