/**
 * Line chart component — used in canvas preview, dashboard widget, and embed.
 *
 * Same component everywhere. No per-mode variants.
 */

import {
  LineChart as RechartsLineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  Area,
  AreaChart,
} from "recharts";
import { cn } from "@/shared/lib/cn";
import type { BaseChartProps, LineChartConfig } from "./types";

const COLORS = ["#e94560", "#53a8b6", "#79c99e", "#f4a261", "#8b5cf6"];

interface Props extends BaseChartProps {
  config: LineChartConfig & Record<string, unknown>;
}

export default function LineChart({ data, config, interactive = true, onDrillDown, className }: Props) {
  const { xAxis, yAxis, areaFill } = config;
  const ChartComponent = areaFill ? AreaChart : RechartsLineChart;

  return (
    <div className={cn("w-full h-full min-h-[200px]", className)}>
      <ResponsiveContainer width="100%" height="100%">
        <ChartComponent data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#ffffff10" />
          <XAxis dataKey={xAxis.column} stroke="#ffffff50" fontSize={12} />
          <YAxis stroke="#ffffff50" fontSize={12} />
          {interactive && <Tooltip contentStyle={{ background: "#0f3460", border: "1px solid #ffffff20" }} />}
          <Legend />
          {yAxis.map((axis, i) =>
            areaFill ? (
              <Area
                key={axis.column}
                type="monotone"
                dataKey={axis.column}
                name={axis.label ?? axis.column}
                stroke={COLORS[i % COLORS.length]}
                fill={COLORS[i % COLORS.length]}
                fillOpacity={0.2}
              />
            ) : (
              <Line
                key={axis.column}
                type="monotone"
                dataKey={axis.column}
                name={axis.label ?? axis.column}
                stroke={COLORS[i % COLORS.length]}
                dot={false}
              />
            ),
          )}
        </ChartComponent>
      </ResponsiveContainer>
    </div>
  );
}
