/**
 * Formula expression editor with column reference highlighting.
 *
 * Bracket syntax: [column_name] references a column from the input schema.
 * Shows available functions in a sidebar palette.
 */

import { useState } from "react";
import { cn } from "@/shared/lib/cn";
import type { ColumnSchema } from "@/shared/schema/types";

interface FormulaEditorProps {
  value: string;
  onChange: (value: string) => void;
  availableColumns: ColumnSchema[];
  className?: string;
}

export default function FormulaEditor({
  value,
  onChange,
  availableColumns,
  className,
}: FormulaEditorProps) {
  const [error, setError] = useState<string | null>(null);

  const insertColumnRef = (colName: string) => {
    onChange(value + `[${colName}]`);
  };

  return (
    <div className={cn("flex flex-col gap-2", className)}>
      <textarea
        value={value}
        onChange={(e) => {
          onChange(e.target.value);
          setError(null);
        }}
        placeholder="e.g. ([revenue] - [cost]) / [revenue] * 100"
        className="w-full bg-canvas-bg border border-white/10 rounded px-3 py-2 text-sm text-white font-mono resize-y min-h-[80px] focus:border-canvas-accent focus:outline-none"
      />
      {error && <div className="text-red-400 text-xs">{error}</div>}
      <div className="flex flex-wrap gap-1">
        {availableColumns.map((col) => (
          <button
            key={col.name}
            onClick={() => insertColumnRef(col.name)}
            className="px-2 py-0.5 text-xs bg-canvas-node border border-white/10 rounded hover:border-canvas-accent text-white/70 hover:text-white"
          >
            [{col.name}]
          </button>
        ))}
      </div>
    </div>
  );
}
