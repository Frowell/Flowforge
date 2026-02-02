/**
 * Bar chart component — used in canvas preview, dashboard widget, and embed.
 *
 * Same component everywhere. No per-mode variants.
 * Responsive — fills its container.
 */

import {
  BarChart as RechartsBarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { cn } from "@/shared/lib/cn";
import type { BaseChartProps, BarChartConfig } from "./types";

const COLORS = ["#e94560", "#53a8b6", "#79c99e", "#f4a261", "#8b5cf6"];

interface Props extends BaseChartProps {
  config: BarChartConfig & Record<string, unknown>;
}

export default function BarChart({ data, config, interactive = true, onDrillDown, className }: Props) {
  const { xAxis, yAxis, orientation, stacked } = config;
  const isHorizontal = orientation === "horizontal";

  return (
    <div className={cn("w-full h-full min-h-[200px]", className)}>
      <ResponsiveContainer width="100%" height="100%">
        <RechartsBarChart
          data={data}
          layout={isHorizontal ? "vertical" : "horizontal"}
          onClick={
            interactive && onDrillDown
              ? (e) => {
                  if (e?.activePayload?.[0]) {
                    onDrillDown({ [xAxis.column]: e.activeLabel });
                  }
                }
              : undefined
          }
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#ffffff10" />
          {isHorizontal ? (
            <>
              <YAxis dataKey={xAxis.column} type="category" stroke="#ffffff50" fontSize={12} />
              <XAxis type="number" stroke="#ffffff50" fontSize={12} />
            </>
          ) : (
            <>
              <XAxis dataKey={xAxis.column} stroke="#ffffff50" fontSize={12} />
              <YAxis stroke="#ffffff50" fontSize={12} />
            </>
          )}
          {interactive && <Tooltip contentStyle={{ background: "#0f3460", border: "1px solid #ffffff20" }} />}
          <Legend />
          {yAxis.map((axis, i) => (
            <Bar
              key={axis.column}
              dataKey={axis.column}
              name={axis.label ?? axis.column}
              fill={COLORS[i % COLORS.length]}
              stackId={stacked ? "stack" : undefined}
            />
          ))}
        </RechartsBarChart>
      </ResponsiveContainer>
    </div>
  );
}
