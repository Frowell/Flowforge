/**
 * Pivot table component — row/column dimensions with aggregated values.
 *
 * Same component everywhere. No per-mode variants.
 */

import { cn } from "@/shared/lib/cn";
import type { BaseChartProps, PivotTableConfig } from "./types";

interface Props extends BaseChartProps {
  config: PivotTableConfig & Record<string, unknown>;
}

export default function PivotTable({ data, config, className }: Props) {
  // TODO: Implement pivot logic — group by row dimensions x column dimensions,
  // aggregate the value column, render as a grid

  const { rowDimensions, columnDimensions, valueColumn, aggregation } = config;

  return (
    <div className={cn("w-full h-full overflow-auto", className)}>
      <div className="text-white/30 text-sm p-4">
        Pivot Table — {data.length} rows
        <br />
        Rows: {rowDimensions.join(", ")} | Columns: {columnDimensions.join(", ")}
        <br />
        Value: {aggregation}({valueColumn})
      </div>
    </div>
  );
}
