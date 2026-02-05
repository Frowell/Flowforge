/**
 * Pivot table component — row/column dimensions with aggregated values.
 *
 * Same component everywhere. No per-mode variants.
 */

import { useMemo } from "react";
import { cn } from "@/shared/lib/cn";
import type { BaseChartProps, PivotTableConfig } from "./types";

interface Props extends BaseChartProps {
  config: PivotTableConfig & Record<string, unknown>;
}

type AggFn = "SUM" | "AVG" | "COUNT" | "MIN" | "MAX";

function aggregateValues(values: number[], fn: string): number {
  if (values.length === 0) return 0;
  const aggFn = fn.toUpperCase() as AggFn;
  switch (aggFn) {
    case "SUM":
      return values.reduce((a, b) => a + b, 0);
    case "AVG":
      return values.reduce((a, b) => a + b, 0) / values.length;
    case "COUNT":
      return values.length;
    case "MIN":
      return Math.min(...values);
    case "MAX":
      return Math.max(...values);
    default:
      return values.reduce((a, b) => a + b, 0);
  }
}

interface PivotResult {
  rowKeys: string[][];
  colKeys: string[][];
  cells: Map<string, number>;
}

function pivotData(
  data: Record<string, unknown>[],
  rowDims: string[],
  colDims: string[],
  valueColumn: string,
  aggregation: string,
): PivotResult {
  const rowKeySet = new Map<string, string[]>();
  const colKeySet = new Map<string, string[]>();
  const buckets = new Map<string, number[]>();

  for (const row of data) {
    const rParts = rowDims.map((d) => String(row[d] ?? ""));
    const cParts = colDims.map((d) => String(row[d] ?? ""));
    const rKey = rParts.join("||");
    const cKey = cParts.join("||");

    if (!rowKeySet.has(rKey)) rowKeySet.set(rKey, rParts);
    if (!colKeySet.has(cKey)) colKeySet.set(cKey, cParts);

    const cellKey = `${rKey}:::${cKey}`;
    const val = Number(row[valueColumn]);
    if (!isNaN(val)) {
      const arr = buckets.get(cellKey);
      if (arr) arr.push(val);
      else buckets.set(cellKey, [val]);
    }
  }

  const cells = new Map<string, number>();
  for (const [key, values] of buckets) {
    cells.set(key, aggregateValues(values, aggregation));
  }

  return {
    rowKeys: Array.from(rowKeySet.values()),
    colKeys: Array.from(colKeySet.values()),
    cells,
  };
}

export default function PivotTable({ data, config, className }: Props) {
  const { rowDimensions, columnDimensions, valueColumn, aggregation } = config;

  const pivot = useMemo(
    () => pivotData(data, rowDimensions, columnDimensions, valueColumn, aggregation),
    [data, rowDimensions, columnDimensions, valueColumn, aggregation],
  );

  if (data.length === 0) {
    return (
      <div
        className={cn(
          "w-full h-full flex items-center justify-center text-white/30 text-sm",
          className,
        )}
      >
        No data
      </div>
    );
  }

  return (
    <div className={cn("w-full h-full overflow-auto", className)}>
      <table className="min-w-full border-collapse text-xs text-white">
        <thead>
          <tr>
            {rowDimensions.map((dim) => (
              <th
                key={dim}
                className="sticky top-0 bg-canvas-node px-3 py-2 text-left font-medium text-white/60 border-b border-canvas-border"
              >
                {dim}
              </th>
            ))}
            {pivot.colKeys.map((ck) => (
              <th
                key={ck.join("||")}
                className="sticky top-0 bg-canvas-node px-3 py-2 text-right font-medium text-white/60 border-b border-canvas-border"
              >
                {ck.join(" / ")}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {pivot.rowKeys.map((rk) => {
            const rKey = rk.join("||");
            return (
              <tr key={rKey} className="hover:bg-white/5">
                {rk.map((val, i) => (
                  <td key={i} className="px-3 py-1.5 border-b border-canvas-border text-white/80">
                    {val}
                  </td>
                ))}
                {pivot.colKeys.map((ck) => {
                  const cKey = ck.join("||");
                  const cellKey = `${rKey}:::${cKey}`;
                  const value = pivot.cells.get(cellKey);
                  return (
                    <td
                      key={cKey}
                      className="px-3 py-1.5 border-b border-canvas-border text-right tabular-nums"
                    >
                      {value !== undefined
                        ? value.toLocaleString(undefined, { maximumFractionDigits: 2 })
                        : "—"}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
