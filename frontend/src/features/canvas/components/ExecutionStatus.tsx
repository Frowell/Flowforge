/**
 * Workflow execution controls and status display.
 */

export default function ExecutionStatus() {
  // TODO: Wire up useExecution hook

  return (
    <div className="flex items-center gap-2">
      <button
        className="px-3 py-1 text-xs bg-canvas-accent text-white rounded hover:opacity-80"
        onClick={() => {
          // TODO: Execute workflow
        }}
      >
        Run
      </button>
      <span className="text-xs text-white/40">Ready</span>
    </div>
  );
}
