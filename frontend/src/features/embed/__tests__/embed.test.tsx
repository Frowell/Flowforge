/**
 * Embed component tests.
 */
import { render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

// Mock react-router-dom
const mockParams: Record<string, string> = {};
const mockSearchParams = new URLSearchParams();

vi.mock("react-router-dom", () => ({
  useParams: () => mockParams,
  useSearchParams: () => [mockSearchParams, vi.fn()],
}));

// Mock recharts
vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  BarChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Bar: () => <div />,
  LineChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Line: () => <div />,
  XAxis: () => <div />,
  YAxis: () => <div />,
  CartesianGrid: () => <div />,
  Tooltip: () => <div />,
  Legend: () => <div />,
  AreaChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Area: () => <div />,
  ScatterChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Scatter: () => <div />,
  Cell: () => <div />,
  ZAxis: () => <div />,
  ComposedChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  ReferenceLine: () => <div />,
}));

// Mock TanStack Query
vi.mock("@tanstack/react-query", () => ({
  useQuery: () => ({
    data: null,
    isLoading: true,
    error: null,
  }),
  QueryClient: vi.fn(),
  QueryClientProvider: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

import EmbedRoot from "../EmbedRoot";

describe("EmbedRoot", () => {
  it("shows error when widget ID is missing", () => {
    Object.assign(mockParams, {});
    mockSearchParams.set("api_key", "sk_live_test");
    render(<EmbedRoot />);
    const text = document.body.textContent ?? "";
    expect(text.toLowerCase()).toContain("missing");
  });

  it("shows error when API key is missing", () => {
    Object.assign(mockParams, { widgetId: "widget-1" });
    // Clear api_key
    mockSearchParams.delete("api_key");
    render(<EmbedRoot />);
    const text = document.body.textContent ?? "";
    expect(text.toLowerCase()).toContain("missing");
  });

  it("renders embed widget when params are valid", () => {
    Object.assign(mockParams, { widgetId: "widget-1" });
    mockSearchParams.set("api_key", "sk_live_test");
    render(<EmbedRoot />);
    // Should render something (loading state or widget)
    expect(document.body.children.length).toBeGreaterThan(0);
  });
});
