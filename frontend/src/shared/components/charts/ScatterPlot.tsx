/**
 * Scatter plot component with size, color, and trendline support.
 *
 * Same component everywhere. No per-mode variants.
 */

import { useMemo } from "react";
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  ZAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  ReferenceLine,
} from "recharts";
import { cn } from "@/shared/lib/cn";
import type { BaseChartProps, ScatterPlotConfig } from "./types";

const COLORS = ["#e94560", "#53a8b6", "#79c99e", "#f4a261", "#8b5cf6", "#f472b6", "#a3e635"];

interface Props extends BaseChartProps {
  config: ScatterPlotConfig & Record<string, unknown>;
}

function linearRegression(points: Array<{ x: number; y: number }>): { slope: number; intercept: number } | null {
  if (points.length < 2) return null;
  const n = points.length;
  let sumX = 0, sumY = 0, sumXX = 0, sumXY = 0;
  for (const p of points) {
    sumX += p.x;
    sumY += p.y;
    sumXX += p.x * p.x;
    sumXY += p.x * p.y;
  }
  const denom = n * sumXX - sumX * sumX;
  if (denom === 0) return null;
  const slope = (n * sumXY - sumX * sumY) / denom;
  const intercept = (sumY - slope * sumX) / n;
  return { slope, intercept };
}

export default function ScatterPlot({ data, config, interactive = true, className }: Props) {
  const { xAxis, yAxis, sizeColumn, colorColumn, trendLine } = config;

  const { groups, xMin, xMax } = useMemo(() => {
    const grouped = new Map<string, Record<string, unknown>[]>();

    for (const row of data) {
      const key = colorColumn ? String(row[colorColumn] ?? "unknown") : "__all__";
      const arr = grouped.get(key);
      if (arr) arr.push(row);
      else grouped.set(key, [row]);
    }

    let xMin = Infinity;
    let xMax = -Infinity;
    for (const row of data) {
      const xVal = Number(row[xAxis.column]);
      if (!isNaN(xVal)) {
        if (xVal < xMin) xMin = xVal;
        if (xVal > xMax) xMax = xVal;
      }
    }

    return { groups: grouped, xMin, xMax };
  }, [data, colorColumn, xAxis.column]);

  const regression = useMemo(() => {
    if (!trendLine) return null;
    const points = data
      .map((row) => ({ x: Number(row[xAxis.column]), y: Number(row[yAxis.column]) }))
      .filter((p) => !isNaN(p.x) && !isNaN(p.y));
    return linearRegression(points);
  }, [data, xAxis.column, yAxis.column, trendLine]);

  const groupEntries = Array.from(groups.entries());

  return (
    <div className={cn("w-full h-full min-h-[200px]", className)}>
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart>
          <CartesianGrid strokeDasharray="3 3" stroke="#ffffff10" />
          <XAxis
            dataKey={xAxis.column}
            name={xAxis.label ?? xAxis.column}
            stroke="#ffffff50"
            fontSize={12}
            type="number"
          />
          <YAxis
            dataKey={yAxis.column}
            name={yAxis.label ?? yAxis.column}
            stroke="#ffffff50"
            fontSize={12}
            type="number"
          />
          {sizeColumn && (
            <ZAxis dataKey={sizeColumn} range={[20, 400]} name={sizeColumn} />
          )}
          {interactive && (
            <Tooltip
              contentStyle={{ background: "#0f3460", border: "1px solid #ffffff20" }}
              cursor={{ strokeDasharray: "3 3" }}
            />
          )}
          {colorColumn && <Legend />}
          {groupEntries.map(([key, rows], i) => (
            <Scatter
              key={key}
              name={key === "__all__" ? undefined : key}
              data={rows}
              fill={COLORS[i % COLORS.length]}
            />
          ))}
          {regression && isFinite(xMin) && isFinite(xMax) && (
            <ReferenceLine
              segment={[
                { x: xMin, y: regression.slope * xMin + regression.intercept },
                { x: xMax, y: regression.slope * xMax + regression.intercept },
              ]}
              stroke="#ffffff60"
              strokeDasharray="6 3"
              strokeWidth={1.5}
            />
          )}
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}
