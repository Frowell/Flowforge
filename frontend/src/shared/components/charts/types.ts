/**
 * Shared chart type definitions.
 *
 * All chart components accept these common props.
 * Charts are responsive — they fill their container.
 */

export interface ChartDataPoint {
  [key: string]: string | number | null;
}

export interface BaseChartProps {
  /** Row data to render */
  data: ChartDataPoint[];
  /** Chart-specific configuration */
  config: Record<string, unknown>;
  /** Enable interactive features (tooltips, click handlers) */
  interactive?: boolean;
  /** Drill-down callback — fired when a chart element is clicked */
  onDrillDown?: (filters: Record<string, unknown>) => void;
  /** Additional CSS classes for the container */
  className?: string;
}

export interface AxisConfig {
  column: string;
  label?: string;
}

export interface BarChartConfig {
  xAxis: AxisConfig;
  yAxis: AxisConfig[];
  colorGroup?: string;
  orientation?: "vertical" | "horizontal";
  stacked?: boolean;
}

export interface LineChartConfig {
  xAxis: AxisConfig;
  yAxis: AxisConfig[];
  areaFill?: boolean;
}

export interface ScatterPlotConfig {
  xAxis: AxisConfig;
  yAxis: AxisConfig;
  sizeColumn?: string;
  colorColumn?: string;
  trendLine?: boolean;
}

export interface CandlestickConfig {
  timeColumn: string;
  openColumn: string;
  highColumn: string;
  lowColumn: string;
  closeColumn: string;
  volumeColumn?: string;
}

export interface KPICardConfig {
  metricColumn: string;
  aggregation: "SUM" | "AVG" | "COUNT" | "MIN" | "MAX" | "LAST";
  comparisonValue?: number;
  thresholds?: { red: number; yellow: number; green: number };
  format?: string;
}

export interface PivotTableConfig {
  rowDimensions: string[];
  columnDimensions: string[];
  valueColumn: string;
  aggregation: string;
}
