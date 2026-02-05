/**
 * Base node component shared by all custom nodes.
 *
 * Handles: label, ports, selection highlight, execution status indicator.
 */

import { Handle, Position } from "@xyflow/react";
import { cn } from "@/shared/lib/cn";

interface BaseNodeProps {
  label: string;
  color: string;
  selected?: boolean;
  inputPorts?: number; // default 1, 0 for Data Source
  outputPorts?: number; // default 1, 0 for terminal nodes
  children?: React.ReactNode;
}

export default function BaseNode({
  label,
  color,
  selected,
  inputPorts = 1,
  outputPorts = 1,
  children,
}: BaseNodeProps) {
  return (
    <div
      className={cn(
        "bg-canvas-node rounded-lg border px-3 py-2 min-w-[140px] shadow-lg",
        selected ? "border-canvas-accent" : "border-white/10",
      )}
    >
      {/* Input handles */}
      {Array.from({ length: inputPorts }, (_, i) => (
        <Handle
          key={`input-${i}`}
          type="target"
          position={Position.Left}
          id={`input-${i}`}
          className="!bg-white/40 !w-2.5 !h-2.5 !border-white/20"
          style={inputPorts > 1 ? { top: `${((i + 1) / (inputPorts + 1)) * 100}%` } : undefined}
        />
      ))}

      <div className="flex items-center gap-2">
        <div className={cn("w-2 h-2 rounded-full shrink-0", color)} />
        <span className="text-xs font-medium text-white truncate">{label}</span>
      </div>

      {children && <div className="mt-1 text-[10px] text-white/40">{children}</div>}

      {/* Output handles */}
      {Array.from({ length: outputPorts }, (_, i) => (
        <Handle
          key={`output-${i}`}
          type="source"
          position={Position.Right}
          id={`output-${i}`}
          className="!bg-canvas-accent !w-2.5 !h-2.5 !border-canvas-accent/50"
        />
      ))}
    </div>
  );
}
