/**
 * Canvas keyboard shortcuts.
 *
 * Manages Delete, Undo/Redo, Save, Execute, Select All, and Escape.
 * Skips shortcuts when focus is inside an input, textarea, or contenteditable.
 */

import { useEffect, useCallback, type RefObject } from "react";
import { useWorkflowStore } from "../stores/workflowStore";

interface UseKeyboardShortcutsOptions {
  containerRef: RefObject<HTMLDivElement | null>;
  onSave?: () => void;
  onExecute?: () => void;
}

export function useKeyboardShortcuts({
  containerRef,
  onSave,
  onExecute,
}: UseKeyboardShortcutsOptions) {
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      // Skip when focus is in an input element
      const target = e.target as HTMLElement;
      if (
        target.tagName === "INPUT" ||
        target.tagName === "TEXTAREA" ||
        target.tagName === "SELECT" ||
        target.isContentEditable
      ) {
        return;
      }

      const isMod = e.metaKey || e.ctrlKey;

      // Delete / Backspace — remove selected node(s)
      if (e.key === "Delete" || e.key === "Backspace") {
        const selectedNodeId = useWorkflowStore.getState().selectedNodeId;
        if (selectedNodeId) {
          e.preventDefault();
          useWorkflowStore.getState().removeNode(selectedNodeId);
        }
        return;
      }

      // Cmd/Ctrl+Z — undo
      if (isMod && e.key === "z" && !e.shiftKey) {
        e.preventDefault();
        useWorkflowStore.temporal.getState().undo();
        return;
      }

      // Cmd/Ctrl+Shift+Z or Cmd/Ctrl+Y — redo
      if ((isMod && e.key === "z" && e.shiftKey) || (isMod && e.key === "y")) {
        e.preventDefault();
        useWorkflowStore.temporal.getState().redo();
        return;
      }

      // Cmd/Ctrl+S — save workflow
      if (isMod && e.key === "s") {
        e.preventDefault();
        onSave?.();
        return;
      }

      // Cmd/Ctrl+Enter — execute workflow
      if (isMod && e.key === "Enter") {
        e.preventDefault();
        onExecute?.();
        return;
      }

      // Cmd/Ctrl+A — select all nodes
      if (isMod && e.key === "a") {
        e.preventDefault();
        const { nodes, onNodesChange } = useWorkflowStore.getState();
        onNodesChange(
          nodes.map((n) => ({ type: "select" as const, id: n.id, selected: true })),
        );
        return;
      }

      // Escape — deselect all
      if (e.key === "Escape") {
        e.preventDefault();
        const { nodes, onNodesChange } = useWorkflowStore.getState();
        onNodesChange(
          nodes.map((n) => ({ type: "select" as const, id: n.id, selected: false })),
        );
        useWorkflowStore.getState().selectNode(null);
        return;
      }
    },
    [onSave, onExecute],
  );

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    container.addEventListener("keydown", handleKeyDown);
    return () => {
      container.removeEventListener("keydown", handleKeyDown);
    };
  }, [containerRef, handleKeyDown]);
}
