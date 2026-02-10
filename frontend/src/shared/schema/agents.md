# Schema Engine — Agent Rules

> Parent rules: [`/workspace/frontend/src/shared/agents.md`](../../agents.md)

## Purpose

This directory contains the client-side schema catalog and propagation engine — the architectural core that makes the no-code canvas work. It computes output schemas for every node in a workflow DAG, enabling schema-aware configuration panels with real column names and type-appropriate operators.

## File Catalog

| File             | Purpose                                                                         |
| ---------------- | ------------------------------------------------------------------------------- |
| `propagation.ts` | Synchronous schema propagation engine — computes output schemas for entire DAG  |
| `registry.ts`    | Schema catalog cache — wraps TanStack Query, fetches from `/api/v1/schema`      |
| `types.ts`       | `ColumnSchema`, `TableSchema`, `NodeType`, `SchemaTransformFn` type definitions |

## Critical Invariant: Python Parity

**`propagation.ts` MUST produce identical results to `backend/app/services/schema_engine.py` for the same inputs.**

Both engines are tested against the same 11 shared JSON fixtures in `tests/fixtures/schema/`. When modifying a transform in one engine, you must update the other to match. The `scripts/validate-schema-parity.sh` script verifies this.

## Performance Target

The propagation engine must complete in **< 10ms for a 50-node graph**. It runs synchronously on every connection change to provide instant feedback:

- Config panel dropdowns populate with real column names from upstream schemas
- Type-aware operator pickers adjust based on column types (string → contains, number → >, datetime → before)
- Type errors highlight immediately on connect (red border, not on execution)

## Transform Registry

Every node type registers a transform function:

```typescript
type SchemaTransformFn = (
  config: Record<string, unknown>, // Node configuration
  inputs: ColumnSchema[][], // Input schemas (1 for most nodes, 2 for Join/Union)
) => ColumnSchema[]; // Output schema
```

### Registered Transforms (17)

| Transform      | Behavior                                   |
| -------------- | ------------------------------------------ |
| `data_source`  | Returns columns from catalog config        |
| `filter`       | Passthrough (same columns)                 |
| `select`       | Subset of input columns in specified order |
| `rename`       | Input columns with name substitutions      |
| `sort`         | Passthrough                                |
| `limit`        | Passthrough                                |
| `sample`       | Passthrough                                |
| `unique`       | Passthrough                                |
| `group_by`     | Group keys + aggregate output columns      |
| `join`         | Merged schemas from both inputs            |
| `union`        | Aligned schemas from both inputs           |
| `pivot`        | Group keys + pivoted value columns         |
| `formula`      | Input columns + new calculated column      |
| `window`       | Input columns + new window function column |
| `chart_output` | Terminal (empty output)                    |
| `table_output` | Terminal (empty output)                    |
| `kpi_output`   | Terminal (empty output)                    |

## Schema Registry

`registry.ts` fetches table/column metadata from the backend via TanStack Query:

- **Cache**: TanStack Query manages caching and refetching — never store schemas in Zustand
- **TTL**: Aligned with backend `schema_cache_ttl` (default 5 minutes)
- **Scope**: The backend filters schemas by tenant context from the JWT — the frontend sees only its tenant's tables

## Rules

- **Synchronous only.** `propagation.ts` must never make network calls or use `async/await`. All data it needs comes from function arguments.
- **No side effects.** Transform functions are pure: same inputs → same outputs.
- **Topological sort.** The propagation engine uses Kahn's algorithm to traverse the DAG in dependency order. Circular references are detected and reported.
- **Never import from `features/`** — this is shared infrastructure consumed by canvas, dashboards, and embed.
