/**
 * Main canvas page — React Flow workspace with node palette and config panel.
 */

import { useCallback, useRef, useEffect } from "react";
import { useParams } from "react-router-dom";
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  Controls,
  MiniMap,
  BackgroundVariant,
  useReactFlow,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { useWorkflowStore } from "../stores/workflowStore";
import { useWorkflow, useSaveWorkflow } from "../hooks/useWorkflow";
import NodePalette from "./NodePalette";
import ConfigPanel from "./ConfigPanel";
import DataPreview from "./DataPreview";
import ExecutionStatus from "./ExecutionStatus";
import WorkflowPicker from "./WorkflowPicker";
import { nodeTypes } from "../nodes";
import { useKeyboardShortcuts } from "../hooks/useKeyboardShortcuts";

function CanvasInner({ workflowId }: { workflowId: string }) {
  const nodes = useWorkflowStore((s) => s.nodes);
  const edges = useWorkflowStore((s) => s.edges);
  const onNodesChange = useWorkflowStore((s) => s.onNodesChange);
  const onEdgesChange = useWorkflowStore((s) => s.onEdgesChange);
  const onConnect = useWorkflowStore((s) => s.onConnect);
  const selectNode = useWorkflowStore((s) => s.selectNode);
  const addNode = useWorkflowStore((s) => s.addNode);
  const setGraph = useWorkflowStore((s) => s.setGraph);
  const selectedNodeId = useWorkflowStore((s) => s.selectedNodeId);
  const { screenToFlowPosition } = useReactFlow();
  const canvasRef = useRef<HTMLDivElement>(null);

  const { data: workflow, isLoading } = useWorkflow(workflowId);
  const saveWorkflow = useSaveWorkflow();

  // All useCallback hooks must be before any early returns (Rules of Hooks)
  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: { id: string }) => {
      selectNode(node.id);
    },
    [selectNode],
  );

  const onPaneClick = useCallback(() => {
    selectNode(null);
  }, [selectNode]);

  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
  }, []);

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      const nodeType = event.dataTransfer.getData("application/reactflow");
      if (!nodeType) return;

      const position = screenToFlowPosition({
        x: event.clientX,
        y: event.clientY,
      });
      const id = `${nodeType}_${crypto.randomUUID().slice(0, 8)}`;

      addNode({
        id,
        type: nodeType,
        position,
        data: {
          label: nodeType.replace(/_/g, " "),
          nodeType,
          config: {},
        },
      });
    },
    [screenToFlowPosition, addNode],
  );

  const handleSave = useCallback(() => {
    saveWorkflow.mutate({ id: workflowId, name: workflow?.name ?? "Untitled" });
  }, [saveWorkflow, workflowId, workflow?.name]);

  // Load workflow graph into store when data arrives
  useEffect(() => {
    if (workflow?.graph_json) {
      const { nodes: loadedNodes, edges: loadedEdges } = workflow.graph_json as {
        nodes: typeof nodes;
        edges: typeof edges;
      };
      setGraph(loadedNodes ?? [], loadedEdges ?? []);
    }
  }, [workflow, setGraph]);

  useKeyboardShortcuts({
    containerRef: canvasRef,
  });

  if (isLoading) {
    return (
      <div className="h-[calc(100vh-3rem)] w-screen flex items-center justify-center bg-canvas-bg">
        <div className="text-white/50 text-sm">Loading workflow...</div>
      </div>
    );
  }

  return (
    <div ref={canvasRef} tabIndex={-1} className="h-[calc(100vh-3rem)] w-screen flex flex-col outline-none">
      <div className="h-10 bg-canvas-bg border-b border-canvas-border flex items-center px-4 shrink-0 justify-between">
        <span className="text-sm text-white/80">{workflow?.name ?? "Workflow"}</span>
        <div className="flex items-center gap-3">
          <button
            onClick={handleSave}
            disabled={saveWorkflow.isPending}
            className="px-3 py-1 text-xs bg-canvas-accent text-white rounded hover:opacity-80 disabled:opacity-50"
          >
            {saveWorkflow.isPending ? "Saving..." : "Save"}
          </button>
          <ExecutionStatus />
        </div>
      </div>

      <div className="flex-1 flex">
        <NodePalette />

        <div className="flex-1 relative">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeClick={onNodeClick}
            onPaneClick={onPaneClick}
            onDragOver={onDragOver}
            onDrop={onDrop}
            nodeTypes={nodeTypes}
            fitView
            className="bg-canvas-bg"
          >
            <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="#ffffff15" />
            <Controls />
            <MiniMap nodeColor="#e94560" maskColor="rgba(0,0,0,0.5)" />
          </ReactFlow>
        </div>

        {selectedNodeId && <ConfigPanel nodeId={selectedNodeId} />}
      </div>

      <DataPreview />
    </div>
  );
}

export default function Canvas() {
  const { workflowId } = useParams<{ workflowId: string }>();

  if (!workflowId) {
    return <WorkflowPicker />;
  }

  return (
    <ReactFlowProvider>
      <CanvasInner workflowId={workflowId} />
    </ReactFlowProvider>
  );
}
