/**
 * Cross-validation tests: verify TypeScript schema engine matches fixture expectations.
 *
 * Loads the same JSON fixtures used by the Python test in
 * backend/tests/services/test_schema_cross_validation.py and asserts that
 * propagateSchemas() produces identical output schemas.
 */

import { readFileSync, readdirSync } from "fs";
import { join } from "path";
import { describe, expect, it } from "vitest";
import { propagateSchemas, type WorkflowEdge, type WorkflowNode } from "../propagation";
import type { ColumnSchema } from "../types";

interface FixtureSchema {
  name: string;
  dtype: string;
  nullable: boolean;
}

interface Fixture {
  description: string;
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  expected: Record<string, FixtureSchema[]>;
}

const FIXTURES_DIR = join(__dirname, "../../../../../tests/fixtures/schema");

function loadFixtures(): Array<[string, Fixture]> {
  const files = readdirSync(FIXTURES_DIR)
    .filter((f) => f.endsWith(".json"))
    .sort();
  return files.map((f) => {
    const raw = readFileSync(join(FIXTURES_DIR, f), "utf-8");
    return [f.replace(".json", ""), JSON.parse(raw) as Fixture];
  });
}

function normalizeSchema(
  schemas: ColumnSchema[],
): Array<{ name: string; dtype: string; nullable: boolean }> {
  return schemas.map((s) => ({
    name: s.name,
    dtype: s.dtype,
    nullable: s.nullable,
  }));
}

describe("Cross-validation: TypeScript schema engine vs fixtures", () => {
  const fixtures = loadFixtures();

  for (const [name, fixture] of fixtures) {
    it(`matches expected output for fixture: ${name}`, () => {
      const result = propagateSchemas(fixture.nodes, fixture.edges);

      for (const [nodeId, expectedSchema] of Object.entries(fixture.expected)) {
        const actualSchema = result.get(nodeId) ?? [];
        const actual = normalizeSchema(actualSchema);
        const expected = expectedSchema.map((e) => ({
          name: e.name,
          dtype: e.dtype,
          nullable: e.nullable,
        }));

        expect(actual).toEqual(expected);
      }
    });
  }
});
