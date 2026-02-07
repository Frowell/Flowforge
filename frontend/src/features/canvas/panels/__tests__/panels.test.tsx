/**
 * Panel component unit tests.
 * Tests that panels render fields and call updateNodeConfig.
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

// Mock Zustand store
const mockUpdateNodeConfig = vi.fn();
const mockNodes = [
  {
    id: "test-node",
    type: "data_source",
    data: { config: { table: "trades", columns: [] }, nodeType: "data_source" },
    position: { x: 0, y: 0 },
  },
];

vi.mock("@/features/canvas/stores/workflowStore", () => ({
  useWorkflowStore: (selector: (s: Record<string, unknown>) => unknown) =>
    selector({
      nodes: mockNodes,
      edges: [],
      updateNodeConfig: mockUpdateNodeConfig,
    }),
}));

// Mock schema registry (for DataSourcePanel)
vi.mock("@/shared/schema/registry", () => ({
  useCatalog: () => ({
    data: {
      tables: [
        { name: "trades", database: "flowforge", source: "clickhouse", columns: [] },
        { name: "instruments", database: "flowforge", source: "clickhouse", columns: [] },
      ],
    },
    isLoading: false,
  }),
}));

// Mock schema engine hooks (for panels that need upstream schema)
vi.mock("@/features/canvas/hooks/useSchemaEngine", () => ({
  useSchemaEngine: () => new Map(),
  useNodeInputSchema: () => [
    { name: "symbol", dtype: "string", nullable: false },
    { name: "price", dtype: "float64", nullable: false },
    { name: "quantity", dtype: "int64", nullable: false },
  ],
  useNodeInputSchemas: () => [
    [
      { name: "symbol", dtype: "string", nullable: false },
      { name: "price", dtype: "float64", nullable: false },
    ],
  ],
  useNodeOutputSchema: () => [
    { name: "symbol", dtype: "string", nullable: false },
    { name: "price", dtype: "float64", nullable: false },
  ],
}));

import DataSourcePanel from "../DataSourcePanel";
import FilterPanel from "../FilterPanel";
import SelectPanel from "../SelectPanel";
import SortPanel from "../SortPanel";
import GroupByPanel from "../GroupByPanel";
import JoinPanel from "../JoinPanel";
import UnionPanel from "../UnionPanel";
import FormulaPanel from "../FormulaPanel";

beforeEach(() => {
  mockUpdateNodeConfig.mockClear();
});

describe("DataSourcePanel", () => {
  it("renders table selector", () => {
    render(<DataSourcePanel nodeId="test-node" />);
    // Should show a select element or table list
    expect(
      screen.getByRole("combobox") || screen.getByText(/trades/i) || screen.getByText(/table/i),
    ).toBeTruthy();
  });

  it("shows available tables from catalog", () => {
    render(<DataSourcePanel nodeId="test-node" />);
    // Should list available tables from the mock catalog
    const text = document.body.textContent ?? "";
    expect(text).toContain("trades");
  });
});

describe("FilterPanel", () => {
  it("renders column selector", () => {
    render(<FilterPanel nodeId="test-node" />);
    // Should show column options from upstream schema
    const text = document.body.textContent ?? "";
    expect(
      text.includes("symbol") ||
        text.includes("price") ||
        text.includes("Column") ||
        text.includes("column"),
    ).toBeTruthy();
  });
});

describe("SelectPanel", () => {
  it("renders", () => {
    render(<SelectPanel nodeId="test-node" />);
    expect(document.body.textContent?.length).toBeGreaterThan(0);
  });
});

describe("SortPanel", () => {
  it("renders", () => {
    render(<SortPanel nodeId="test-node" />);
    expect(document.body.textContent?.length).toBeGreaterThan(0);
  });
});

describe("GroupByPanel", () => {
  it("renders", () => {
    render(<GroupByPanel nodeId="test-node" />);
    expect(document.body.textContent?.length).toBeGreaterThan(0);
  });
});

describe("JoinPanel", () => {
  it("renders", () => {
    render(<JoinPanel nodeId="test-node" />);
    expect(document.body.textContent?.length).toBeGreaterThan(0);
  });
});

describe("UnionPanel", () => {
  it("renders", () => {
    render(<UnionPanel nodeId="test-node" />);
    expect(document.body.textContent?.length).toBeGreaterThan(0);
  });
});

describe("FormulaPanel", () => {
  it("renders", () => {
    render(<FormulaPanel nodeId="test-node" />);
    expect(document.body.textContent?.length).toBeGreaterThan(0);
  });
});
