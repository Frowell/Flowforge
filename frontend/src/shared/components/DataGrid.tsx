/**
 * Data grid component for tabular data display.
 *
 * Used by Table Output nodes and data preview panels.
 * Built on @tanstack/react-table for sortable headers and column resizing.
 * Uses @tanstack/react-virtual for row virtualization to handle large datasets.
 */

import { useMemo, useRef, useState } from "react";
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  flexRender,
  createColumnHelper,
  type SortingState,
  type ColumnDef,
} from "@tanstack/react-table";
import { useVirtualizer } from "@tanstack/react-virtual";
import { cn } from "@/shared/lib/cn";

interface DataGridProps {
  columns: Array<{ name: string; dtype: string }>;
  rows: Record<string, unknown>[];
  className?: string;
}

const ROW_HEIGHT = 35;

export default function DataGrid({ columns, rows, className }: DataGridProps) {
  const [sorting, setSorting] = useState<SortingState>([]);
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  const columnDefs = useMemo<ColumnDef<Record<string, unknown>, unknown>[]>(() => {
    const helper = createColumnHelper<Record<string, unknown>>();
    return columns.map((col) =>
      helper.accessor((row) => row[col.name], {
        id: col.name,
        header: () => (
          <span>
            {col.name}
            <span className="ml-1 text-xs text-white/30">{col.dtype}</span>
          </span>
        ),
        cell: (info) => String(info.getValue() ?? ""),
        size: 150,
        minSize: 60,
      }),
    );
  }, [columns]);

  const table = useReactTable({
    data: rows,
    columns: columnDefs,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    columnResizeMode: "onChange",
  });

  const { rows: tableRows } = table.getRowModel();

  const virtualizer = useVirtualizer({
    count: tableRows.length,
    getScrollElement: () => scrollContainerRef.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: 10,
  });

  return (
    <div ref={scrollContainerRef} className={cn("w-full h-full overflow-auto", className)}>
      <table className="w-full text-sm text-left" style={{ width: table.getCenterTotalSize() }}>
        <thead className="sticky top-0 bg-canvas-node border-b border-white/10 z-10">
          {table.getHeaderGroups().map((headerGroup) => (
            <tr key={headerGroup.id}>
              {headerGroup.headers.map((header) => (
                <th
                  key={header.id}
                  className="px-3 py-2 font-medium text-white/70 whitespace-nowrap relative select-none"
                  style={{ width: header.getSize() }}
                >
                  <div
                    className={cn(
                      "flex items-center gap-1",
                      header.column.getCanSort() && "cursor-pointer hover:text-white",
                    )}
                    onClick={header.column.getToggleSortingHandler()}
                  >
                    {flexRender(header.column.columnDef.header, header.getContext())}
                    {{
                      asc: " \u2191",
                      desc: " \u2193",
                    }[header.column.getIsSorted() as string] ?? null}
                  </div>
                  <div
                    onMouseDown={header.getResizeHandler()}
                    onTouchStart={header.getResizeHandler()}
                    className={cn(
                      "absolute right-0 top-0 h-full w-1 cursor-col-resize select-none touch-none",
                      header.column.getIsResizing() ? "bg-accent-primary" : "hover:bg-white/20",
                    )}
                  />
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody
          style={{
            height: `${virtualizer.getTotalSize()}px`,
            position: "relative",
          }}
        >
          {virtualizer.getVirtualItems().map((virtualRow) => {
            const row = tableRows[virtualRow.index];
            if (!row) return null;
            return (
              <tr
                key={row.id}
                className="border-b border-white/5 hover:bg-white/5 absolute w-full"
                style={{
                  height: `${virtualRow.size}px`,
                  transform: `translateY(${virtualRow.start}px)`,
                }}
              >
                {row.getVisibleCells().map((cell) => (
                  <td
                    key={cell.id}
                    className="px-3 py-1.5 text-white/80 whitespace-nowrap"
                    style={{ width: cell.column.getSize() }}
                  >
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
      {rows.length === 0 && <div className="text-center py-8 text-white/30 text-sm">No data</div>}
    </div>
  );
}
