/**
 * ChartRenderer — central dispatch component mapping chart_type + config + data
 * to the correct shared chart component.
 *
 * Used in WidgetCard, EmbedWidget, and canvas DataPreview.
 * Lazy-loads each chart component for code splitting.
 */

import { lazy, Suspense } from "react";
import type {
  ChartDataPoint,
  BarChartConfig,
  LineChartConfig,
  ScatterPlotConfig,
  CandlestickConfig,
  KPICardConfig,
  PivotTableConfig,
  AxisConfig,
} from "./types";
import DataGrid from "../DataGrid";

const LazyBarChart = lazy(() => import("./BarChart"));
const LazyLineChart = lazy(() => import("./LineChart"));
const LazyScatterPlot = lazy(() => import("./ScatterPlot"));
const LazyCandlestickChart = lazy(() => import("./CandlestickChart"));
const LazyKPICard = lazy(() => import("./KPICard"));
const LazyPivotTable = lazy(() => import("./PivotTable"));

interface ChartRendererProps {
  chartType: string;
  config: Record<string, unknown>;
  data: ChartDataPoint[];
  columns?: Array<{ name: string; dtype: string }>;
  interactive?: boolean;
  onDrillDown?: (filters: Record<string, unknown>) => void;
  className?: string;
}

function toAxis(value: unknown): AxisConfig {
  if (typeof value === "string") return { column: value };
  if (value && typeof value === "object" && "column" in value) return value as AxisConfig;
  return { column: "" };
}

function toAxisArray(value: unknown): AxisConfig[] {
  if (Array.isArray(value)) return value.map(toAxis);
  if (typeof value === "string") {
    return value
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean)
      .map((col) => ({ column: col }));
  }
  return [];
}

function toStringArray(value: unknown): string[] {
  if (Array.isArray(value)) return value.map(String);
  if (typeof value === "string") return value.split(",").map((s) => s.trim()).filter(Boolean);
  return [];
}

function normalizeBarConfig(config: Record<string, unknown>): BarChartConfig {
  return {
    xAxis: toAxis(config.xAxis ?? config.x_axis),
    yAxis: toAxisArray(config.yAxis ?? config.y_axis),
    colorGroup: config.colorGroup as string | undefined,
    orientation: (config.orientation as "vertical" | "horizontal") ?? "vertical",
    stacked: (config.stacked as boolean) ?? false,
  };
}

function normalizeLineConfig(config: Record<string, unknown>): LineChartConfig {
  return {
    xAxis: toAxis(config.xAxis ?? config.x_axis),
    yAxis: toAxisArray(config.yAxis ?? config.y_axis),
    areaFill: (config.areaFill ?? config.area_fill) as boolean | undefined,
  };
}

function normalizeScatterConfig(config: Record<string, unknown>): ScatterPlotConfig {
  return {
    xAxis: toAxis(config.xAxis ?? config.x_axis),
    yAxis: toAxis(config.yAxis ?? config.y_axis),
    sizeColumn: config.sizeColumn as string | undefined,
    colorColumn: config.colorColumn as string | undefined,
    trendLine: config.trendLine as boolean | undefined,
  };
}

function normalizeCandlestickConfig(config: Record<string, unknown>): CandlestickConfig {
  return {
    timeColumn: (config.timeColumn ?? config.time_column ?? "") as string,
    openColumn: (config.openColumn ?? config.open_column ?? "") as string,
    highColumn: (config.highColumn ?? config.high_column ?? "") as string,
    lowColumn: (config.lowColumn ?? config.low_column ?? "") as string,
    closeColumn: (config.closeColumn ?? config.close_column ?? "") as string,
    volumeColumn: config.volumeColumn as string | undefined,
  };
}

function normalizeKPIConfig(config: Record<string, unknown>): KPICardConfig {
  return {
    metricColumn: (config.metricColumn ?? config.metric_column ?? "") as string,
    aggregation: ((config.aggregation ?? "SUM") as string).toUpperCase() as KPICardConfig["aggregation"],
    comparisonValue: config.comparisonValue as number | undefined,
    thresholds: config.thresholds as KPICardConfig["thresholds"],
    format: config.format as string | undefined,
  };
}

function normalizePivotConfig(config: Record<string, unknown>): PivotTableConfig {
  return {
    rowDimensions: toStringArray(config.rowDimensions ?? config.row_dimensions),
    columnDimensions: toStringArray(config.columnDimensions ?? config.column_dimensions),
    valueColumn: (config.valueColumn ?? config.value_column ?? "") as string,
    aggregation: (config.aggregation ?? "SUM") as string,
  };
}

const Loading = () => (
  <div className="w-full h-full flex items-center justify-center">
    <div className="w-5 h-5 border-2 border-white/20 border-t-white/60 rounded-full animate-spin" />
  </div>
);

export default function ChartRenderer({
  chartType,
  config,
  data,
  columns,
  interactive = true,
  onDrillDown,
  className,
}: ChartRendererProps) {
  const baseProps = { data, interactive, onDrillDown, className };

  // For table type, derive columns from data if not provided
  const tableColumns = columns ?? (data.length > 0
    ? Object.keys(data[0]).map((name) => ({ name, dtype: "string" }))
    : []);

  return (
    <Suspense fallback={<Loading />}>
      {chartType === "bar" && (
        <LazyBarChart {...baseProps} config={{ ...normalizeBarConfig(config) }} />
      )}
      {chartType === "line" && (
        <LazyLineChart {...baseProps} config={{ ...normalizeLineConfig(config) }} />
      )}
      {chartType === "scatter" && (
        <LazyScatterPlot {...baseProps} config={{ ...normalizeScatterConfig(config) }} />
      )}
      {chartType === "candlestick" && (
        <LazyCandlestickChart {...baseProps} config={{ ...normalizeCandlestickConfig(config) }} />
      )}
      {chartType === "kpi" && (
        <LazyKPICard {...baseProps} config={{ ...normalizeKPIConfig(config) }} />
      )}
      {chartType === "pivot" && (
        <LazyPivotTable {...baseProps} config={{ ...normalizePivotConfig(config) }} />
      )}
      {chartType === "table" && (
        <DataGrid columns={tableColumns} rows={data as Record<string, unknown>[]} className={className} />
      )}
      {!["bar", "line", "scatter", "candlestick", "kpi", "pivot", "table"].includes(chartType) && (
        <div className="w-full h-full flex items-center justify-center text-white/30 text-sm">
          Unsupported chart type: {chartType}
        </div>
      )}
    </Suspense>
  );
}
