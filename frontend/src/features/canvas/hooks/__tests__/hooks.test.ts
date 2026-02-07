/**
 * Canvas hook tests (non-DOM hooks).
 */
import { describe, expect, it } from "vitest";
import { propagateSchemas, type WorkflowNode } from "@/shared/schema/propagation";

describe("propagateSchemas (used by useSchemaEngine)", () => {
  it("returns empty map for empty graph", () => {
    const result = propagateSchemas([], []);
    expect(result.size).toBe(0);
  });

  it("propagates data source schema", () => {
    const nodes = [
      {
        id: "src",
        type: "data_source" as const,
        data: {
          config: {
            columns: [
              { name: "id", dtype: "string", nullable: false },
              { name: "value", dtype: "float64", nullable: true },
            ],
          },
        },
      },
    ];
    const result = propagateSchemas(nodes, []);
    expect(result.get("src")).toHaveLength(2);
    expect(result.get("src")![0].name).toBe("id");
  });

  it("propagates filter as passthrough", () => {
    const nodes = [
      {
        id: "src",
        type: "data_source" as const,
        data: {
          config: {
            columns: [{ name: "x", dtype: "int64", nullable: false }],
          },
        },
      },
      {
        id: "flt",
        type: "filter" as const,
        data: { config: { column: "x", operator: "=", value: 1 } },
      },
    ];
    const edges = [{ source: "src", target: "flt" }];
    const result = propagateSchemas(nodes, edges);
    expect(result.get("flt")).toEqual(result.get("src"));
  });

  it("select narrows columns", () => {
    const nodes = [
      {
        id: "src",
        type: "data_source" as const,
        data: {
          config: {
            columns: [
              { name: "a", dtype: "string", nullable: false },
              { name: "b", dtype: "int64", nullable: false },
              { name: "c", dtype: "float64", nullable: true },
            ],
          },
        },
      },
      {
        id: "sel",
        type: "select" as const,
        data: { config: { columns: ["a", "c"] } },
      },
    ];
    const edges = [{ source: "src", target: "sel" }];
    const result = propagateSchemas(nodes, edges);
    expect(result.get("sel")).toHaveLength(2);
    expect(result.get("sel")![0].name).toBe("a");
    expect(result.get("sel")![1].name).toBe("c");
  });

  it("formula adds a column", () => {
    const nodes = [
      {
        id: "src",
        type: "data_source" as const,
        data: {
          config: {
            columns: [{ name: "price", dtype: "float64", nullable: false }],
          },
        },
      },
      {
        id: "f",
        type: "formula" as const,
        data: {
          config: {
            expression: "[price] * 2",
            output_column: "doubled",
            output_dtype: "float64",
          },
        },
      },
    ];
    const edges = [{ source: "src", target: "f" }];
    const result = propagateSchemas(nodes, edges);
    expect(result.get("f")).toHaveLength(2);
    expect(result.get("f")![1].name).toBe("doubled");
  });

  it("throws on cycle", () => {
    const nodes = [
      { id: "a", type: "filter" as const, data: { config: {} } },
      { id: "b", type: "filter" as const, data: { config: {} } },
    ];
    const edges = [
      { source: "a", target: "b" },
      { source: "b", target: "a" },
    ];
    expect(() => propagateSchemas(nodes, edges)).toThrow(/cycle/i);
  });

  it("throws on unknown node type", () => {
    const nodes = [
      { id: "x", type: "unknown_type" as unknown as WorkflowNode["type"], data: { config: {} } },
    ];
    expect(() => propagateSchemas(nodes, [])).toThrow(/unknown/i);
  });

  it("join merges schemas", () => {
    const nodes = [
      {
        id: "l",
        type: "data_source" as const,
        data: { config: { columns: [{ name: "id", dtype: "string", nullable: false }] } },
      },
      {
        id: "r",
        type: "data_source" as const,
        data: { config: { columns: [{ name: "name", dtype: "string", nullable: true }] } },
      },
      { id: "j", type: "join" as const, data: { config: {} } },
    ];
    const edges = [
      { source: "l", target: "j" },
      { source: "r", target: "j" },
    ];
    const result = propagateSchemas(nodes, edges);
    expect(result.get("j")).toHaveLength(2);
  });

  it("rename changes column names", () => {
    const nodes = [
      {
        id: "src",
        type: "data_source" as const,
        data: { config: { columns: [{ name: "old_name", dtype: "string", nullable: false }] } },
      },
      {
        id: "ren",
        type: "rename" as const,
        data: { config: { rename_map: { old_name: "new_name" } } },
      },
    ];
    const edges = [{ source: "src", target: "ren" }];
    const result = propagateSchemas(nodes, edges);
    expect(result.get("ren")![0].name).toBe("new_name");
  });

  it("terminal nodes return empty schema", () => {
    const nodes = [
      {
        id: "src",
        type: "data_source" as const,
        data: { config: { columns: [{ name: "x", dtype: "int64", nullable: false }] } },
      },
      { id: "out", type: "table_output" as const, data: { config: {} } },
    ];
    const edges = [{ source: "src", target: "out" }];
    const result = propagateSchemas(nodes, edges);
    expect(result.get("out")).toHaveLength(0);
  });
});
