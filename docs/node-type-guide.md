# Node Type Guide

> Parent: [`/workspace/agents.md`](../agents.md) | Architecture: [`/workspace/Application plan.md`](../Application%20plan.md)

## New Node Type Checklist

Adding a new canvas node type requires touching ALL 6 of these files:

1. **Backend schema transform** — `backend/app/services/schema_engine.py` — register `input_schema → output_schema` function
2. **Backend compiler** — `backend/app/services/workflow_compiler.py` — add SQLGlot compilation rule
3. **Frontend schema transform** — `frontend/src/shared/schema/propagation.ts` — mirror the Python transform
4. **Node component** — `frontend/src/features/canvas/nodes/<NodeType>Node.tsx` — React Flow custom node
5. **Config panel** — `frontend/src/features/canvas/panels/<NodeType>Panel.tsx` — schema-aware configuration UI
6. **Type definitions** — update shared types in both `backend/app/schemas/` and `frontend/src/shared/schema/types.ts`

If any of these 6 are missing, the node type is incomplete.

---

## Canvas Node Types

### Phase 1 (Core)
- **DataSource** — Select a table from the schema catalog
- **Filter** — Add WHERE conditions (schema passes through unchanged)
- **Select** — Choose columns to keep (schema narrows)
- **Sort** — Add ORDER BY clauses (schema passes through unchanged)
- **TableView** — Terminal node — paginated table output

### Phase 2 (Analytical)
- **GroupBy** — GROUP BY + aggregate functions (schema changes to group keys + aggregated columns)
- **Join** — Two-input JOIN (INNER, LEFT, RIGHT, FULL)
- **Union** — Two-input UNION
- **Formula** — Computed columns via `[column]` bracket-notation expressions
- **Rename** — Rename columns
- **Unique** — DISTINCT
- **Sample** — Random sample (LIMIT with ORDER BY RAND())

### Phase 3 (Visualization)
- Bar Chart, Line Chart, Candlestick, Scatter Plot, KPI Card, Pivot Table

---

## Chart Library

All charts use **Apache ECharts** via `echarts-for-react`. Chart types: Bar, Line, Candlestick, Scatter, KPI Card, Pivot Table. All live in `frontend/src/shared/components/charts/`.

---

## Schema Propagation — The Core Invariant

Every node type declares its input → output schema transform in BOTH TypeScript (client-side, instant feedback) and Python (server-side, authoritative). If you add or modify a node type, both implementations must be updated and kept in sync.

### Backend (Python)

Schema transforms are registered in `backend/app/services/schema_engine.py`. Each transform is a pure function: `(input_schema, node_config) → output_schema`.

### Frontend (TypeScript)

Schema transforms are mirrored in `frontend/src/shared/schema/propagation.ts`. The client uses these for instant feedback when the user edits node configuration — no round-trip to the server required.

### Keeping Them in Sync

When modifying a transform:
1. Change the Python version first (authoritative)
2. Mirror the logic in TypeScript
3. Add test cases in both `backend/tests/` and `frontend/src/shared/schema/__tests__/`

---

## Query Merging

Adjacent compatible nodes MUST be merged into single SQL queries by the workflow compiler. A linear chain of Filter → Select → Sort on the same table produces ONE query, not three. Never generate one-query-per-node output.

### Merge-Compatible Pairs

| Upstream | Downstream | Merged? |
|----------|-----------|---------|
| DataSource | Filter | Yes — becomes `SELECT * FROM table WHERE ...` |
| Filter | Select | Yes — adds column selection to existing query |
| Select | Sort | Yes — adds ORDER BY to existing query |
| Filter | GroupBy | Yes — becomes `SELECT ... FROM table WHERE ... GROUP BY ...` |
| GroupBy | Filter (HAVING) | Yes — becomes HAVING clause |
| Any | Join | No — join creates new query segment |

### Implementation

The compiler (`backend/app/services/workflow_compiler.py`) performs a topological sort of the DAG, then greedily merges adjacent nodes into query segments. Each segment produces one SQLGlot AST that is compiled to a SQL string for the target dialect.
