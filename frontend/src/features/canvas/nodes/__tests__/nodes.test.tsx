/**
 * Node component unit tests.
 * Tests that each node type renders correctly with proper labels and config display.
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

// Mock @xyflow/react to avoid ReactFlow context requirement
vi.mock("@xyflow/react", () => ({
  Handle: ({ type, position, id }: { type: string; position: string; id: string }) => (
    <div data-testid={`handle-${type}-${id}`} />
  ),
  Position: { Left: "left", Right: "right", Top: "top", Bottom: "bottom" },
}));

// Import node components
import DataSourceNode from "../DataSourceNode";
import FilterNode from "../FilterNode";
import SelectNode from "../SelectNode";
import SortNode from "../SortNode";
import GroupByNode from "../GroupByNode";
import JoinNode from "../JoinNode";
import UnionNode from "../UnionNode";
import FormulaNode from "../FormulaNode";
import RenameNode from "../RenameNode";
import UniqueNode from "../UniqueNode";
import SampleNode from "../SampleNode";
import LimitNode from "../LimitNode";
import WindowNode from "../WindowNode";
import PivotNode from "../PivotNode";
import TableOutputNode from "../TableOutputNode";
import ChartOutputNode from "../ChartOutputNode";
import KPIOutputNode from "../KPIOutputNode";

const makeNodeProps = (config: Record<string, unknown> = {}, selected = false) => ({
  id: "test-node",
  data: { config, nodeType: "test" },
  selected,
  type: "test",
  isConnectable: true,
  xPos: 0,
  yPos: 0,
  zIndex: 0,
  dragging: false,
  positionAbsoluteX: 0,
  positionAbsoluteY: 0,
});

describe("DataSourceNode", () => {
  it("renders with label", () => {
    render(<DataSourceNode {...makeNodeProps({ table: "trades" })} />);
    expect(screen.getByText("Data Source")).toBeInTheDocument();
  });

  it("shows table name from config", () => {
    render(<DataSourceNode {...makeNodeProps({ table: "raw_trades" })} />);
    expect(screen.getByText("raw_trades")).toBeInTheDocument();
  });

  it("has no input handles (source node)", () => {
    const { container } = render(<DataSourceNode {...makeNodeProps()} />);
    expect(container.querySelector('[data-testid^="handle-target"]')).toBeNull();
  });

  it("has output handle", () => {
    render(<DataSourceNode {...makeNodeProps()} />);
    expect(screen.getByTestId("handle-source-output-0")).toBeInTheDocument();
  });
});

describe("FilterNode", () => {
  it("renders with label", () => {
    render(<FilterNode {...makeNodeProps()} />);
    expect(screen.getByText("Filter")).toBeInTheDocument();
  });

  it("shows filter expression when configured", () => {
    render(<FilterNode {...makeNodeProps({ column: "price", operator: ">" })} />);
    expect(screen.getByText(/price/)).toBeInTheDocument();
  });
});

describe("SelectNode", () => {
  it("renders with label", () => {
    render(<SelectNode {...makeNodeProps()} />);
    expect(screen.getByText("Select")).toBeInTheDocument();
  });
});

describe("SortNode", () => {
  it("renders with label", () => {
    render(<SortNode {...makeNodeProps()} />);
    expect(screen.getByText("Sort")).toBeInTheDocument();
  });
});

describe("GroupByNode", () => {
  it("renders with label", () => {
    render(<GroupByNode {...makeNodeProps()} />);
    expect(screen.getByText(/Group/)).toBeInTheDocument();
  });
});

describe("JoinNode", () => {
  it("renders with label", () => {
    render(<JoinNode {...makeNodeProps()} />);
    expect(screen.getByText("Join")).toBeInTheDocument();
  });

  it("shows join type", () => {
    render(<JoinNode {...makeNodeProps({ join_type: "left" })} />);
    expect(screen.getByText(/LEFT/i)).toBeInTheDocument();
  });

  it("has two input handles", () => {
    render(<JoinNode {...makeNodeProps()} />);
    expect(screen.getByTestId("handle-target-input-0")).toBeInTheDocument();
    expect(screen.getByTestId("handle-target-input-1")).toBeInTheDocument();
  });
});

describe("UnionNode", () => {
  it("renders with label", () => {
    render(<UnionNode {...makeNodeProps()} />);
    expect(screen.getByText("Union")).toBeInTheDocument();
  });
});

describe("FormulaNode", () => {
  it("renders with label", () => {
    render(<FormulaNode {...makeNodeProps()} />);
    expect(screen.getByText("Formula")).toBeInTheDocument();
  });
});

describe("RenameNode", () => {
  it("renders with label", () => {
    render(<RenameNode {...makeNodeProps()} />);
    expect(screen.getByText("Rename")).toBeInTheDocument();
  });
});

describe("UniqueNode", () => {
  it("renders with label", () => {
    render(<UniqueNode {...makeNodeProps()} />);
    expect(screen.getByText("Unique")).toBeInTheDocument();
  });
});

describe("SampleNode", () => {
  it("renders with label", () => {
    render(<SampleNode {...makeNodeProps()} />);
    expect(screen.getByText("Sample")).toBeInTheDocument();
  });
});

describe("LimitNode", () => {
  it("renders with label", () => {
    render(<LimitNode {...makeNodeProps()} />);
    expect(screen.getByText("Limit")).toBeInTheDocument();
  });
});

describe("WindowNode", () => {
  it("renders with label", () => {
    render(<WindowNode {...makeNodeProps()} />);
    expect(screen.getByText("Window")).toBeInTheDocument();
  });
});

describe("PivotNode", () => {
  it("renders with label", () => {
    render(<PivotNode {...makeNodeProps()} />);
    expect(screen.getByText("Pivot")).toBeInTheDocument();
  });
});

describe("TableOutputNode", () => {
  it("renders with label", () => {
    render(<TableOutputNode {...makeNodeProps()} />);
    expect(screen.getByText(/Table/)).toBeInTheDocument();
  });

  it("has input handle but no output handle", () => {
    render(<TableOutputNode {...makeNodeProps()} />);
    expect(screen.getByTestId("handle-target-input-0")).toBeInTheDocument();
    expect(screen.queryByTestId("handle-source-output-0")).toBeNull();
  });
});

describe("ChartOutputNode", () => {
  it("renders with label", () => {
    render(<ChartOutputNode {...makeNodeProps()} />);
    expect(screen.getByText(/Chart/)).toBeInTheDocument();
  });
});

describe("KPIOutputNode", () => {
  it("renders with label", () => {
    render(<KPIOutputNode {...makeNodeProps()} />);
    expect(screen.getByText(/KPI/)).toBeInTheDocument();
  });
});
