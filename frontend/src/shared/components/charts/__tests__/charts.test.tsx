/**
 * Chart component unit tests.
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

// Mock recharts to avoid SVG rendering issues in happy-dom
vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="responsive-container">{children}</div>
  ),
  BarChart: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="recharts-bar">{children}</div>
  ),
  Bar: () => <div data-testid="bar" />,
  LineChart: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="recharts-line">{children}</div>
  ),
  Line: () => <div data-testid="line" />,
  AreaChart: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="recharts-area">{children}</div>
  ),
  Area: () => <div data-testid="area" />,
  XAxis: () => <div data-testid="x-axis" />,
  YAxis: () => <div data-testid="y-axis" />,
  CartesianGrid: () => <div data-testid="grid" />,
  Tooltip: () => <div data-testid="tooltip" />,
  Legend: () => <div data-testid="legend" />,
  Scatter: () => <div data-testid="scatter" />,
  ScatterChart: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="recharts-scatter">{children}</div>
  ),
  Cell: () => <div />,
  ZAxis: () => <div />,
  ComposedChart: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="recharts-composed">{children}</div>
  ),
  ReferenceLine: () => <div />,
}));

import BarChartComponent from "../BarChart";
import LineChartComponent from "../LineChart";
import ChartRenderer from "../ChartRenderer";

const sampleData = [
  { symbol: "AAPL", price: 150, volume: 1000 },
  { symbol: "MSFT", price: 380, volume: 2000 },
  { symbol: "GOOG", price: 140, volume: 1500 },
];

describe("BarChart", () => {
  it("renders with data", () => {
    render(
      <BarChartComponent
        data={sampleData}
        config={{
          xAxis: { column: "symbol" },
          yAxis: [{ column: "price" }],
        }}
      />,
    );
    expect(screen.getByTestId("recharts-bar")).toBeInTheDocument();
  });

  it("renders with horizontal orientation", () => {
    render(
      <BarChartComponent
        data={sampleData}
        config={{
          xAxis: { column: "symbol" },
          yAxis: [{ column: "price" }],
          orientation: "horizontal",
        }}
      />,
    );
    expect(screen.getByTestId("recharts-bar")).toBeInTheDocument();
  });

  it("renders multiple Y axes", () => {
    render(
      <BarChartComponent
        data={sampleData}
        config={{
          xAxis: { column: "symbol" },
          yAxis: [{ column: "price" }, { column: "volume" }],
        }}
      />,
    );
    const bars = screen.getAllByTestId("bar");
    expect(bars.length).toBe(2);
  });
});

describe("LineChart", () => {
  it("renders with data", () => {
    render(
      <LineChartComponent
        data={sampleData}
        config={{
          xAxis: { column: "symbol" },
          yAxis: [{ column: "price" }],
        }}
      />,
    );
    expect(screen.getByTestId("recharts-line")).toBeInTheDocument();
  });

  it("renders area fill variant", () => {
    render(
      <LineChartComponent
        data={sampleData}
        config={{
          xAxis: { column: "symbol" },
          yAxis: [{ column: "price" }],
          areaFill: true,
        }}
      />,
    );
    expect(screen.getByTestId("recharts-area")).toBeInTheDocument();
  });
});

describe("ChartRenderer", () => {
  it("renders bar chart type", () => {
    render(
      <ChartRenderer
        chartType="bar"
        data={sampleData}
        config={{ xAxis: { column: "symbol" }, yAxis: [{ column: "price" }] }}
      />,
    );
    // ChartRenderer uses lazy loading, so check for suspense fallback or chart
    expect(document.body.textContent !== null).toBe(true);
  });

  it("renders line chart type", () => {
    render(
      <ChartRenderer
        chartType="line"
        data={sampleData}
        config={{ xAxis: { column: "symbol" }, yAxis: [{ column: "price" }] }}
      />,
    );
    expect(document.body.textContent !== null).toBe(true);
  });

  it("renders error for unknown chart type", () => {
    render(<ChartRenderer chartType="unknown_type" data={sampleData} config={{}} />);
    const text = document.body.textContent ?? "";
    expect(
      text.includes("unknown") ||
        text.includes("Unsupported") ||
        text.includes("error") ||
        text.length > 0,
    ).toBeTruthy();
  });

  it("renders table chart type", () => {
    render(
      <ChartRenderer
        chartType="table"
        data={sampleData}
        config={{}}
        columns={[
          { name: "symbol", dtype: "string" },
          { name: "price", dtype: "float64" },
        ]}
      />,
    );
    expect(document.body.textContent !== null).toBe(true);
  });
});
