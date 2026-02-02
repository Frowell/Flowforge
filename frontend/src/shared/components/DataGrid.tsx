/**
 * Data grid component for tabular data display.
 *
 * Used by Table Output nodes and data preview panels.
 * TODO: Replace with TanStack Table for full features.
 */

import { cn } from "@/shared/lib/cn";

interface DataGridProps {
  columns: Array<{ name: string; dtype: string }>;
  rows: Record<string, unknown>[];
  className?: string;
}

export default function DataGrid({ columns, rows, className }: DataGridProps) {
  return (
    <div className={cn("w-full h-full overflow-auto", className)}>
      <table className="w-full text-sm text-left">
        <thead className="sticky top-0 bg-canvas-node border-b border-white/10">
          <tr>
            {columns.map((col) => (
              <th
                key={col.name}
                className="px-3 py-2 font-medium text-white/70 whitespace-nowrap"
              >
                {col.name}
                <span className="ml-1 text-xs text-white/30">{col.dtype}</span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-b border-white/5 hover:bg-white/5">
              {columns.map((col) => (
                <td key={col.name} className="px-3 py-1.5 text-white/80 whitespace-nowrap">
                  {String(row[col.name] ?? "")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length === 0 && (
        <div className="text-center py-8 text-white/30 text-sm">No data</div>
      )}
    </div>
  );
}
