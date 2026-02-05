/**
 * Schema propagation engine tests.
 *
 * Tests all Phase 1 node types plus multi-node DAG, cycle detection,
 * and unknown node type handling.
 *
 * Must produce identical results to backend/app/services/schema_engine.py.
 */

import { describe, it, expect } from "vitest";
import { propagateSchemas, type WorkflowNode, type WorkflowEdge } from "../propagation";
import type { ColumnSchema } from "../types";

const SAMPLE_COLUMNS: ColumnSchema[] = [
  { name: "id", dtype: "int64", nullable: false },
  { name: "symbol", dtype: "string", nullable: false },
  { name: "price", dtype: "float64", nullable: true },
  { name: "quantity", dtype: "int64", nullable: true },
];

// ── Data Source ────────────────────────────────────────────────────────

describe("data_source transform", () => {
  it("outputs columns from config", () => {
    const nodes: WorkflowNode[] = [
      {
        id: "src",
        type: "data_source",
        data: { config: { columns: SAMPLE_COLUMNS } },
      },
    ];
    const result = propagateSchemas(nodes, []);
    const schema = result.get("src")!;
    expect(schema).toHaveLength(4);
    expect(schema[0].name).toBe("id");
    expect(schema[3].name).toBe("quantity");
  });

  it("outputs empty when no columns configured", () => {
    const nodes: WorkflowNode[] = [
      {
        id: "src",
        type: "data_source",
        data: { config: { columns: [] } },
      },
    ];
    const result = propagateSchemas(nodes, []);
    expect(result.get("src")).toEqual([]);
  });
});

// ── Filter ─────────────────────────────────────────────────────────────

describe("filter transform", () => {
  it("passthrough preserves all columns", () => {
    const nodes: WorkflowNode[] = [
      {
        id: "src",
        type: "data_source",
        data: { config: { columns: SAMPLE_COLUMNS } },
      },
      {
        id: "flt",
        type: "filter",
        data: { config: { column: "symbol", operator: "=", value: "AAPL" } },
      },
    ];
    const edges: WorkflowEdge[] = [{ source: "src", target: "flt" }];
    const result = propagateSchemas(nodes, edges);
    expect(result.get("flt")).toHaveLength(SAMPLE_COLUMNS.length);
  });

  it("preserves column dtypes", () => {
    const nodes: WorkflowNode[] = [
      {
        id: "src",
        type: "data_source",
        data: { config: { columns: SAMPLE_COLUMNS } },
      },
      {
        id: "flt",
        type: "filter",
        data: { config: {} },
      },
    ];
    const edges: WorkflowEdge[] = [{ source: "src", target: "flt" }];
    const result = propagateSchemas(nodes, edges);
    const schema = result.get("flt")!;
    expect(schema[2].name).toBe("price");
    expect(schema[2].dtype).toBe("float64");
  });
});

// ── Select ─────────────────────────────────────────────────────────────

describe("select transform", () => {
  it("returns only specified columns in order", () => {
    const nodes: WorkflowNode[] = [
      {
        id: "src",
        type: "data_source",
        data: { config: { columns: SAMPLE_COLUMNS } },
      },
      {
        id: "sel",
        type: "select",
        data: { config: { columns: ["price", "symbol"] } },
      },
    ];
    const edges: WorkflowEdge[] = [{ source: "src", target: "sel" }];
    const result = propagateSchemas(nodes, edges);
    const schema = result.get("sel")!;
    expect(schema).toHaveLength(2);
    expect(schema[0].name).toBe("price");
    expect(schema[1].name).toBe("symbol");
  });

  it("ignores columns that do not exist in input", () => {
    const nodes: WorkflowNode[] = [
      {
        id: "src",
        type: "data_source",
        data: { config: { columns: SAMPLE_COLUMNS } },
      },
      {
        id: "sel",
        type: "select",
        data: { config: { columns: ["symbol", "nonexistent"] } },
      },
    ];
    const edges: WorkflowEdge[] = [{ source: "src", target: "sel" }];
    const result = propagateSchemas(nodes, edges);
    expect(result.get("sel")).toHaveLength(1);
  });
});

// ── Sort ───────────────────────────────────────────────────────────────

describe("sort transform", () => {
  it("passthrough preserves all columns", () => {
    const nodes: WorkflowNode[] = [
      {
        id: "src",
        type: "data_source",
        data: { config: { columns: SAMPLE_COLUMNS } },
      },
      {
        id: "srt",
        type: "sort",
        data: { config: { sort_by: [{ column: "price", direction: "desc" }] } },
      },
    ];
    const edges: WorkflowEdge[] = [{ source: "src", target: "srt" }];
    const result = propagateSchemas(nodes, edges);
    expect(result.get("srt")).toHaveLength(SAMPLE_COLUMNS.length);
  });
});

// ── Rename ─────────────────────────────────────────────────────────────

describe("rename transform", () => {
  it("substitutes column names", () => {
    const nodes: WorkflowNode[] = [
      {
        id: "src",
        type: "data_source",
        data: { config: { columns: SAMPLE_COLUMNS } },
      },
      {
        id: "ren",
        type: "rename",
        data: { config: { rename_map: { price: "trade_price", symbol: "ticker" } } },
      },
    ];
    const edges: WorkflowEdge[] = [{ source: "src", target: "ren" }];
    const result = propagateSchemas(nodes, edges);
    const names = result.get("ren")!.map((c) => c.name);
    expect(names).toContain("trade_price");
    expect(names).toContain("ticker");
    expect(names).not.toContain("price");
    expect(names).not.toContain("symbol");
  });

  it("preserves column count", () => {
    const nodes: WorkflowNode[] = [
      {
        id: "src",
        type: "data_source",
        data: { config: { columns: SAMPLE_COLUMNS } },
      },
      {
        id: "ren",
        type: "rename",
        data: { config: { rename_map: { price: "trade_price" } } },
      },
    ];
    const edges: WorkflowEdge[] = [{ source: "src", target: "ren" }];
    const result = propagateSchemas(nodes, edges);
    expect(result.get("ren")).toHaveLength(SAMPLE_COLUMNS.length);
  });
});

// ── Formula ────────────────────────────────────────────────────────────

describe("formula transform", () => {
  it("adds computed column to output", () => {
    const nodes: WorkflowNode[] = [
      {
        id: "src",
        type: "data_source",
        data: { config: { columns: SAMPLE_COLUMNS } },
      },
      {
        id: "frm",
        type: "formula",
        data: {
          config: {
            expression: "[price] * [quantity]",
            output_column: "notional",
            output_dtype: "float64",
          },
        },
      },
    ];
    const edges: WorkflowEdge[] = [{ source: "src", target: "frm" }];
    const result = propagateSchemas(nodes, edges);
    const schema = result.get("frm")!;
    expect(schema).toHaveLength(SAMPLE_COLUMNS.length + 1);
    expect(schema[schema.length - 1].name).toBe("notional");
    expect(schema[schema.length - 1].dtype).toBe("float64");
    expect(schema[schema.length - 1].nullable).toBe(true);
  });
});

// ── Unique ─────────────────────────────────────────────────────────────

describe("unique transform", () => {
  it("passthrough preserves all columns", () => {
    const nodes: WorkflowNode[] = [
      {
        id: "src",
        type: "data_source",
        data: { config: { columns: SAMPLE_COLUMNS } },
      },
      { id: "unq", type: "unique", data: { config: {} } },
    ];
    const edges: WorkflowEdge[] = [{ source: "src", target: "unq" }];
    const result = propagateSchemas(nodes, edges);
    expect(result.get("unq")).toHaveLength(SAMPLE_COLUMNS.length);
  });
});

// ── Sample ─────────────────────────────────────────────────────────────

describe("sample transform", () => {
  it("passthrough preserves all columns", () => {
    const nodes: WorkflowNode[] = [
      {
        id: "src",
        type: "data_source",
        data: { config: { columns: SAMPLE_COLUMNS } },
      },
      { id: "smp", type: "sample", data: { config: { count: 10 } } },
    ];
    const edges: WorkflowEdge[] = [{ source: "src", target: "smp" }];
    const result = propagateSchemas(nodes, edges);
    expect(result.get("smp")).toHaveLength(SAMPLE_COLUMNS.length);
  });
});

// ── Table Output (Terminal) ────────────────────────────────────────────

describe("table_output transform", () => {
  it("returns empty (terminal node)", () => {
    const nodes: WorkflowNode[] = [
      {
        id: "src",
        type: "data_source",
        data: { config: { columns: SAMPLE_COLUMNS } },
      },
      { id: "out", type: "table_output", data: { config: {} } },
    ];
    const edges: WorkflowEdge[] = [{ source: "src", target: "out" }];
    const result = propagateSchemas(nodes, edges);
    expect(result.get("out")).toEqual([]);
  });
});

// ── Multi-node DAG ─────────────────────────────────────────────────────

describe("multi-node DAG", () => {
  it("Source -> Filter -> Select -> Sort validates correctly", () => {
    const nodes: WorkflowNode[] = [
      {
        id: "src",
        type: "data_source",
        data: { config: { columns: SAMPLE_COLUMNS } },
      },
      {
        id: "flt",
        type: "filter",
        data: { config: { column: "symbol", operator: "=", value: "AAPL" } },
      },
      {
        id: "sel",
        type: "select",
        data: { config: { columns: ["symbol", "price"] } },
      },
      {
        id: "srt",
        type: "sort",
        data: { config: { sort_by: [{ column: "price", direction: "desc" }] } },
      },
    ];
    const edges: WorkflowEdge[] = [
      { source: "src", target: "flt" },
      { source: "flt", target: "sel" },
      { source: "sel", target: "srt" },
    ];
    const result = propagateSchemas(nodes, edges);

    // After filter: all 4 columns
    expect(result.get("flt")).toHaveLength(4);
    // After select: only 2
    expect(result.get("sel")).toHaveLength(2);
    // After sort: still 2
    expect(result.get("srt")).toHaveLength(2);
    expect(result.get("srt")![0].name).toBe("symbol");
    expect(result.get("srt")![1].name).toBe("price");
  });

  it("disconnected nodes handled gracefully", () => {
    const nodes: WorkflowNode[] = [
      {
        id: "src1",
        type: "data_source",
        data: { config: { columns: [{ name: "a", dtype: "string" as const, nullable: false }] } },
      },
      {
        id: "src2",
        type: "data_source",
        data: { config: { columns: [{ name: "b", dtype: "int64" as const, nullable: true }] } },
      },
    ];
    const result = propagateSchemas(nodes, []);
    expect(result.get("src1")).toHaveLength(1);
    expect(result.get("src2")).toHaveLength(1);
  });
});

// ── Error Cases ────────────────────────────────────────────────────────

describe("error handling", () => {
  it("throws on cycle", () => {
    const nodes: WorkflowNode[] = [
      { id: "a", type: "filter", data: { config: {} } },
      { id: "b", type: "filter", data: { config: {} } },
    ];
    const edges: WorkflowEdge[] = [
      { source: "a", target: "b" },
      { source: "b", target: "a" },
    ];
    expect(() => propagateSchemas(nodes, edges)).toThrow("cycle");
  });

  it("throws on unknown node type", () => {
    const nodes = [
      { id: "x", type: "nonexistent_type" as any, data: { config: {} } },
    ];
    expect(() => propagateSchemas(nodes, [])).toThrow("Unknown node type");
  });
});

// ── Group By ───────────────────────────────────────────────────────────

describe("group_by transform", () => {
  it("produces group keys + aggregates", () => {
    const nodes: WorkflowNode[] = [
      {
        id: "src",
        type: "data_source",
        data: { config: { columns: SAMPLE_COLUMNS } },
      },
      {
        id: "grp",
        type: "group_by",
        data: {
          config: {
            group_columns: ["symbol"],
            aggregations: [
              { column: "price", function: "AVG", alias: "avg_price", output_dtype: "float64" },
            ],
          },
        },
      },
    ];
    const edges: WorkflowEdge[] = [{ source: "src", target: "grp" }];
    const result = propagateSchemas(nodes, edges);
    const schema = result.get("grp")!;
    expect(schema).toHaveLength(2);
    expect(schema[0].name).toBe("symbol");
    expect(schema[1].name).toBe("avg_price");
    expect(schema[1].dtype).toBe("float64");
  });
});

// ── Join ───────────────────────────────────────────────────────────────

describe("join transform", () => {
  it("merges schemas from both inputs", () => {
    const nodes: WorkflowNode[] = [
      {
        id: "left",
        type: "data_source",
        data: {
          config: {
            columns: [
              { name: "symbol", dtype: "string", nullable: false },
              { name: "price", dtype: "float64", nullable: true },
            ],
          },
        },
      },
      {
        id: "right",
        type: "data_source",
        data: {
          config: {
            columns: [
              { name: "symbol", dtype: "string", nullable: false },
              { name: "sector", dtype: "string", nullable: true },
            ],
          },
        },
      },
      {
        id: "jn",
        type: "join",
        data: { config: { join_type: "inner", left_key: "symbol", right_key: "symbol" } },
      },
    ];
    const edges: WorkflowEdge[] = [
      { source: "left", target: "jn" },
      { source: "right", target: "jn" },
    ];
    const result = propagateSchemas(nodes, edges);
    const schema = result.get("jn")!;
    // symbol (from left), price (from left), sector (from right - symbol deduplicated)
    expect(schema).toHaveLength(3);
    const names = schema.map((c) => c.name);
    expect(names).toContain("symbol");
    expect(names).toContain("price");
    expect(names).toContain("sector");
  });
});
