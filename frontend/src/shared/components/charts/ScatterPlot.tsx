/**
 * Scatter plot component.
 *
 * Same component everywhere. No per-mode variants.
 */

import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { cn } from "@/shared/lib/cn";
import type { BaseChartProps, ScatterPlotConfig } from "./types";

interface Props extends BaseChartProps {
  config: ScatterPlotConfig & Record<string, unknown>;
}

export default function ScatterPlot({ data, config, interactive = true, className }: Props) {
  const { xAxis, yAxis } = config;

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
          />
          <YAxis
            dataKey={yAxis.column}
            name={yAxis.label ?? yAxis.column}
            stroke="#ffffff50"
            fontSize={12}
          />
          {interactive && (
            <Tooltip contentStyle={{ background: "#0f3460", border: "1px solid #ffffff20" }} />
          )}
          <Scatter data={data} fill="#e94560" />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}
