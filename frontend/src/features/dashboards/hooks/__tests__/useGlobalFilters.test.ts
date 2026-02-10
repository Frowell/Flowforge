/**
 * useGlobalFilters hook tests — column intersection logic.
 */
import { describe, expect, it, vi, beforeEach } from "vitest";
import { renderHook } from "@testing-library/react";

// Mock react-router-dom
vi.mock("react-router-dom", () => ({
  useParams: () => ({ dashboardId: "dash-1" }),
}));

// Mock TanStack Query's useQueries
const mockUseQueries = vi.fn();
vi.mock("@tanstack/react-query", () => ({
  useQueries: (...args: unknown[]) => mockUseQueries(...args),
}));

// Mock apiClient
vi.mock("@/shared/query-engine/client", () => ({
  apiClient: { get: vi.fn() },
}));

// Mock useDashboardWidgets
vi.mock("../useDashboardWidgets", () => ({
  useDashboardWidgets: () => ({
    data: [{ id: "w-1" }, { id: "w-2" }],
    isLoading: false,
  }),
}));

// Mock dashboardStore
vi.mock("../../stores/dashboardStore", () => ({
  useDashboardStore: (selector: (s: Record<string, unknown>) => unknown) =>
    selector({
      activeFilters: [],
      setFilter: vi.fn(),
      clearFilters: vi.fn(),
    }),
}));

import { useGlobalFilters } from "../useGlobalFilters";

beforeEach(() => {
  vi.clearAllMocks();
});

describe("useGlobalFilters", () => {
  it("returns empty availableColumns when no widget data cached", () => {
    mockUseQueries.mockReturnValue([
      { data: undefined, isLoading: false },
      { data: undefined, isLoading: false },
    ]);

    const { result } = renderHook(() => useGlobalFilters());
    expect(result.current.availableColumns).toEqual([]);
  });

  it("computes intersection of columns across two widgets", () => {
    mockUseQueries.mockReturnValue([
      {
        data: {
          columns: [
            { name: "date", dtype: "datetime" },
            { name: "symbol", dtype: "string" },
            { name: "price", dtype: "float64" },
          ],
        },
        isLoading: false,
      },
      {
        data: {
          columns: [
            { name: "date", dtype: "datetime" },
            { name: "symbol", dtype: "string" },
            { name: "volume", dtype: "int64" },
          ],
        },
        isLoading: false,
      },
    ]);

    const { result } = renderHook(() => useGlobalFilters());
    const names = result.current.availableColumns.map((c) => c.name);
    expect(names).toEqual(["date", "symbol"]);
  });

  it("excludes columns not present in all widgets", () => {
    mockUseQueries.mockReturnValue([
      {
        data: {
          columns: [
            { name: "date", dtype: "datetime" },
            { name: "unique_a", dtype: "string" },
          ],
        },
        isLoading: false,
      },
      {
        data: {
          columns: [
            { name: "date", dtype: "datetime" },
            { name: "unique_b", dtype: "string" },
          ],
        },
        isLoading: false,
      },
    ]);

    const { result } = renderHook(() => useGlobalFilters());
    const names = result.current.availableColumns.map((c) => c.name);
    expect(names).toEqual(["date"]);
    expect(names).not.toContain("unique_a");
    expect(names).not.toContain("unique_b");
  });

  it("maps datetime columns to date_range filter type", () => {
    mockUseQueries.mockReturnValue([
      {
        data: {
          columns: [{ name: "created_at", dtype: "datetime" }],
        },
        isLoading: false,
      },
    ]);

    const { result } = renderHook(() => useGlobalFilters());
    expect(result.current.availableColumns).toHaveLength(1);
    expect(result.current.availableColumns[0]!.suggestedFilterType).toBe("date_range");
  });

  it("maps string columns to text filter type", () => {
    mockUseQueries.mockReturnValue([
      {
        data: {
          columns: [{ name: "ticker", dtype: "string" }],
        },
        isLoading: false,
      },
    ]);

    const { result } = renderHook(() => useGlobalFilters());
    expect(result.current.availableColumns).toHaveLength(1);
    expect(result.current.availableColumns[0]!.suggestedFilterType).toBe("text");
  });

  it("maps non-datetime columns to text filter type", () => {
    mockUseQueries.mockReturnValue([
      {
        data: {
          columns: [
            { name: "count", dtype: "int64" },
            { name: "ratio", dtype: "float64" },
          ],
        },
        isLoading: false,
      },
    ]);

    const { result } = renderHook(() => useGlobalFilters());
    expect(result.current.availableColumns).toHaveLength(2);
    expect(result.current.availableColumns[0]!.suggestedFilterType).toBe("text");
    expect(result.current.availableColumns[1]!.suggestedFilterType).toBe("text");
  });
});
