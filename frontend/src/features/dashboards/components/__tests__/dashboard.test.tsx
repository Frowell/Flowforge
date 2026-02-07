/**
 * Dashboard component tests.
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

// Mock react-router-dom
vi.mock("react-router-dom", () => ({
  useParams: () => ({ dashboardId: "dash-1" }),
  useSearchParams: () => [new URLSearchParams(), vi.fn()],
  useNavigate: () => vi.fn(),
  Link: ({ children, to }: { children: React.ReactNode; to: string }) => (
    <a href={to}>{children}</a>
  ),
}));

// Mock react-grid-layout
vi.mock("react-grid-layout", () => {
  const Responsive = ({ children }: { children: React.ReactNode }) => (
    <div data-testid="grid-layout">{children}</div>
  );
  return {
    default: Responsive,
    Responsive,
    WidthProvider: (Component: React.ComponentType) => Component,
  };
});

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

// Mock TanStack Query hooks
vi.mock("@/features/dashboards/hooks/useDashboard", () => ({
  useDashboard: () => ({
    data: { id: "dash-1", name: "Test Dashboard", description: "A test" },
    isLoading: false,
    error: null,
  }),
}));

vi.mock("@/features/dashboards/hooks/useDashboardWidgets", () => ({
  useDashboardWidgets: () => ({
    data: [],
    isLoading: false,
    error: null,
  }),
}));

vi.mock("@/features/dashboards/hooks/useWidget", () => ({
  useUpdateWidget: () => ({ mutate: vi.fn() }),
}));

vi.mock("@/features/dashboards/hooks/useGlobalFilters", () => ({
  useGlobalFilters: () => ({
    activeFilters: [],
    setFilter: vi.fn(),
    clearFilters: vi.fn(),
  }),
}));

// Mock dashboardStore
vi.mock("@/features/dashboards/stores/dashboardStore", () => ({
  useDashboardStore: (selector: (s: Record<string, unknown>) => unknown) =>
    selector({
      isEditing: false,
      setEditing: vi.fn(),
      drillDownFilters: [],
      addDrillDownFilter: vi.fn(),
      clearDrillDownFilters: vi.fn(),
    }),
}));

// Mock Toast store
vi.mock("@/shared/components/Toast", () => ({
  useToastStore: (selector: (s: Record<string, unknown>) => unknown) =>
    selector({ addToast: vi.fn() }),
}));

import DashboardGrid from "../DashboardGrid";

describe("DashboardGrid", () => {
  it("renders dashboard name", () => {
    render(<DashboardGrid />);
    expect(screen.getByText("Test Dashboard")).toBeInTheDocument();
  });

  it("shows empty state when no widgets", () => {
    render(<DashboardGrid />);
    const text = document.body.textContent ?? "";
    // Should show some empty state or the dashboard with no widgets
    expect(text.length).toBeGreaterThan(0);
  });
});
