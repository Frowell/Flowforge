/**
 * KPI Card component — single metric display with optional comparison.
 *
 * Same component everywhere. No per-mode variants.
 */

import { cn } from "@/shared/lib/cn";
import type { BaseChartProps, KPICardConfig } from "./types";

interface Props extends BaseChartProps {
  config: KPICardConfig & Record<string, unknown>;
}

function aggregate(values: number[], fn: KPICardConfig["aggregation"]): number {
  if (values.length === 0) return 0;
  switch (fn) {
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
    case "LAST":
      return values[values.length - 1]!;
    default:
      return 0;
  }
}

function getThresholdColor(value: number, thresholds?: KPICardConfig["thresholds"]): string {
  if (!thresholds) return "text-white";
  if (value >= thresholds.green) return "text-green-400";
  if (value >= thresholds.yellow) return "text-yellow-400";
  return "text-red-400";
}

export default function KPICard({ data, config, className }: Props) {
  const { metricColumn, aggregation, comparisonValue, thresholds } = config;
  const values = data.map((row) => Number(row[metricColumn])).filter((v) => !isNaN(v));

  const value = aggregate(values, aggregation);
  const colorClass = getThresholdColor(value, thresholds);

  const change =
    comparisonValue !== undefined
      ? ((value - comparisonValue) / Math.abs(comparisonValue)) * 100
      : undefined;

  return (
    <div className={cn("w-full h-full flex flex-col items-center justify-center p-4", className)}>
      <div className={cn("text-4xl font-bold tabular-nums", colorClass)}>
        {value.toLocaleString(undefined, { maximumFractionDigits: 2 })}
      </div>
      {change !== undefined && (
        <div className={cn("text-sm mt-1", change >= 0 ? "text-green-400" : "text-red-400")}>
          {change >= 0 ? "+" : ""}
          {change.toFixed(1)}%
        </div>
      )}
      <div className="text-xs text-white/40 mt-2 uppercase tracking-wide">
        {aggregation} of {metricColumn}
      </div>
    </div>
  );
}
