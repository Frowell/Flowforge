/**
 * Main canvas page — React Flow workspace with node palette and config panel.
 */

import { useCallback } from "react";
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
import NodePalette from "./NodePalette";
import ConfigPanel from "./ConfigPanel";
import DataPreview from "./DataPreview";
import ExecutionStatus from "./ExecutionStatus";
import { nodeTypes } from "../nodes";

function CanvasInner() {
  const nodes = useWorkflowStore((s) => s.nodes);
  const edges = useWorkflowStore((s) => s.edges);
  const onNodesChange = useWorkflowStore((s) => s.onNodesChange);
  const onEdgesChange = useWorkflowStore((s) => s.onEdgesChange);
  const onConnect = useWorkflowStore((s) => s.onConnect);
  const selectNode = useWorkflowStore((s) => s.selectNode);
  const addNode = useWorkflowStore((s) => s.addNode);
  const selectedNodeId = useWorkflowStore((s) => s.selectedNodeId);
  const { screenToFlowPosition } = useReactFlow();

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

  return (
    <div className="h-screen w-screen flex flex-col">
      <header className="h-12 bg-canvas-node border-b border-canvas-border flex items-center px-4 shrink-0 justify-between">
        <h1 className="text-sm font-semibold tracking-wide text-white">FlowForge</h1>
        <ExecutionStatus />
      </header>

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
  return (
    <ReactFlowProvider>
      <CanvasInner />
    </ReactFlowProvider>
  );
}
