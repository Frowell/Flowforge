/**
 * Workflow store tests — verify Zustand store actions for canvas state.
 */

import { describe, it, expect, beforeEach } from "vitest";
import { useWorkflowStore, type WorkflowNodeData } from "../stores/workflowStore";
import type { Node, Edge } from "@xyflow/react";

function makeNode(
  id: string,
  nodeType: string = "filter",
  config: Record<string, unknown> = {},
): Node<WorkflowNodeData> {
  return {
    id,
    type: "custom",
    position: { x: 0, y: 0 },
    data: { label: id, nodeType, config },
  };
}

describe("workflowStore", () => {
  beforeEach(() => {
    // Reset store state before each test
    useWorkflowStore.getState().clear();
  });

  describe("addNode", () => {
    it("adds a node to the store", () => {
      const node = makeNode("n1", "data_source");
      useWorkflowStore.getState().addNode(node);

      const { nodes } = useWorkflowStore.getState();
      expect(nodes).toHaveLength(1);
      expect(nodes[0].id).toBe("n1");
      expect(nodes[0].data.nodeType).toBe("data_source");
    });

    it("adds multiple nodes", () => {
      useWorkflowStore.getState().addNode(makeNode("n1"));
      useWorkflowStore.getState().addNode(makeNode("n2"));

      expect(useWorkflowStore.getState().nodes).toHaveLength(2);
    });
  });

  describe("removeNode", () => {
    it("removes a node from the store", () => {
      useWorkflowStore.getState().addNode(makeNode("n1"));
      useWorkflowStore.getState().addNode(makeNode("n2"));
      useWorkflowStore.getState().removeNode("n1");

      const { nodes } = useWorkflowStore.getState();
      expect(nodes).toHaveLength(1);
      expect(nodes[0].id).toBe("n2");
    });

    it("removes connected edges when node is removed", () => {
      useWorkflowStore.getState().addNode(makeNode("n1"));
      useWorkflowStore.getState().addNode(makeNode("n2"));
      useWorkflowStore.getState().addNode(makeNode("n3"));

      // Simulate edges
      useWorkflowStore.setState({
        edges: [
          { id: "e1", source: "n1", target: "n2" },
          { id: "e2", source: "n2", target: "n3" },
        ],
      });

      useWorkflowStore.getState().removeNode("n2");

      const { edges } = useWorkflowStore.getState();
      // Both edges involving n2 should be removed
      expect(edges).toHaveLength(0);
    });

    it("clears selectedNodeId if removed node was selected", () => {
      useWorkflowStore.getState().addNode(makeNode("n1"));
      useWorkflowStore.getState().selectNode("n1");
      expect(useWorkflowStore.getState().selectedNodeId).toBe("n1");

      useWorkflowStore.getState().removeNode("n1");
      expect(useWorkflowStore.getState().selectedNodeId).toBeNull();
    });

    it("preserves selectedNodeId if different node removed", () => {
      useWorkflowStore.getState().addNode(makeNode("n1"));
      useWorkflowStore.getState().addNode(makeNode("n2"));
      useWorkflowStore.getState().selectNode("n1");

      useWorkflowStore.getState().removeNode("n2");
      expect(useWorkflowStore.getState().selectedNodeId).toBe("n1");
    });
  });

  describe("updateNodeConfig", () => {
    it("updates data config on a specific node", () => {
      useWorkflowStore.getState().addNode(makeNode("n1", "filter", { column: "symbol" }));

      useWorkflowStore.getState().updateNodeConfig("n1", { operator: "=" });

      const node = useWorkflowStore.getState().nodes[0];
      expect(node.data.config).toEqual({ column: "symbol", operator: "=" });
    });

    it("does not affect other nodes", () => {
      useWorkflowStore.getState().addNode(makeNode("n1", "filter", { column: "a" }));
      useWorkflowStore.getState().addNode(makeNode("n2", "filter", { column: "b" }));

      useWorkflowStore.getState().updateNodeConfig("n1", { column: "c" });

      expect(useWorkflowStore.getState().nodes[1].data.config).toEqual({ column: "b" });
    });
  });

  describe("onConnect", () => {
    it("adds an edge between nodes", () => {
      useWorkflowStore.getState().addNode(makeNode("n1"));
      useWorkflowStore.getState().addNode(makeNode("n2"));

      useWorkflowStore.getState().onConnect({
        source: "n1",
        target: "n2",
        sourceHandle: null,
        targetHandle: null,
      });

      const { edges } = useWorkflowStore.getState();
      expect(edges).toHaveLength(1);
      expect(edges[0].source).toBe("n1");
      expect(edges[0].target).toBe("n2");
    });
  });

  describe("selectNode", () => {
    it("sets selectedNodeId", () => {
      useWorkflowStore.getState().selectNode("n1");
      expect(useWorkflowStore.getState().selectedNodeId).toBe("n1");
    });

    it("clears selectedNodeId with null", () => {
      useWorkflowStore.getState().selectNode("n1");
      useWorkflowStore.getState().selectNode(null);
      expect(useWorkflowStore.getState().selectedNodeId).toBeNull();
    });
  });

  describe("setGraph", () => {
    it("loads graph state", () => {
      const nodes = [makeNode("n1"), makeNode("n2")];
      const edges: Edge[] = [{ id: "e1", source: "n1", target: "n2" }];

      useWorkflowStore.getState().setGraph(nodes, edges);

      const state = useWorkflowStore.getState();
      expect(state.nodes).toHaveLength(2);
      expect(state.edges).toHaveLength(1);
    });

    it("resets selectedNodeId", () => {
      useWorkflowStore.getState().selectNode("old");
      useWorkflowStore.getState().setGraph([], []);
      expect(useWorkflowStore.getState().selectedNodeId).toBeNull();
    });
  });

  describe("clear", () => {
    it("resets all state", () => {
      useWorkflowStore.getState().addNode(makeNode("n1"));
      useWorkflowStore.getState().selectNode("n1");

      useWorkflowStore.getState().clear();

      const state = useWorkflowStore.getState();
      expect(state.nodes).toEqual([]);
      expect(state.edges).toEqual([]);
      expect(state.selectedNodeId).toBeNull();
    });
  });
});
