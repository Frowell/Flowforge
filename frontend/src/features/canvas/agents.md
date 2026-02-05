# Canvas Feature — Agent Rules

> Parent rules: [`/workspace/frontend/agents.md`](../../../agents.md) | Architecture: [`/workspace/planning.md`](../../../../../planning.md)

## Node Architecture

Each node type requires 3 files:

1. **Node component** — `nodes/<NodeType>Node.tsx` — React Flow custom node rendering
2. **Config panel** — `panels/<NodeType>Panel.tsx` — right-sidebar configuration UI
3. **Schema transform** — registered in `shared/schema/propagation.ts` — input → output schema function

All three must exist for a node type to be complete. The backend also requires its own schema transform and compiler rule (see root `agents.md` new-node checklist).

## Connection Rules

- Every node has exactly **1 output port**, except terminal nodes (Chart/Table outputs) which have **0 output ports**.
- Every node has exactly **1 input port**, except Join and Union which have **2 input ports**.
- Connections validate schema compatibility on connect — highlight red if incompatible.
- Drag-to-connect must enforce these port constraints.

## Schema-Aware Config Panels

- Config panels MUST derive all dropdowns and options from the upstream node's `outputSchema`.
- **Never** hardcode column lists, type options, or operator choices.
- When upstream schema changes (e.g., user reconnects a different source), panels must reactively update.
- Operator choices change based on column type:
  - Numeric: `=`, `!=`, `>`, `<`, `>=`, `<=`, `between`
  - String: `=`, `!=`, `contains`, `starts with`, `ends with`
  - Datetime: `=`, `!=`, `before`, `after`, `between`

## Workflow Store (Zustand)

The `workflowStore.ts` manages canvas UI state:

**Belongs in store:**

- `nodes` and `edges` (React Flow state)
- `selectedNodeId`
- Canvas actions (addNode, removeNode, updateNodeConfig, connect, etc.)

**Does NOT belong in store:**

- Fetched workflow data (use TanStack Query)
- Schema catalog data (use TanStack Query via `useSchemaEngine`)
- Execution status (use WebSocket via `useExecution`)
- Data preview results (use TanStack Query via `useDataPreview`)

## Canvas Hooks

| Hook              | Purpose                                                                         |
| ----------------- | ------------------------------------------------------------------------------- |
| `useWorkflow`     | Workflow CRUD — save, load, list, delete via TanStack Query                     |
| `useSchemaEngine` | Client-side schema propagation — runs on every connection change                |
| `useDataPreview`  | Fetches first 100 rows of a selected node's output                              |
| `useExecution`    | Runs workflow, tracks status via WebSocket (pending → running → complete/error) |

## Node Type Catalog

### Phase 1 (Core) — 5 nodes

| Node       | Inputs | Outputs      | Schema Effect                            |
| ---------- | ------ | ------------ | ---------------------------------------- |
| DataSource | 0      | 1            | Sets initial schema from table catalog   |
| Filter     | 1      | 1            | Pass-through (only row count changes)    |
| Select     | 1      | 1            | Narrows to selected columns              |
| Sort       | 1      | 1            | Pass-through (only row order changes)    |
| TableView  | 1      | 0 (terminal) | Pass-through + pagination (LIMIT/OFFSET) |

### Phase 2 (Analytical) — 7 nodes

| Node    | Inputs | Outputs | Schema Effect                    |
| ------- | ------ | ------- | -------------------------------- |
| GroupBy | 1      | 1       | Group keys + aggregated columns  |
| Join    | 2      | 1       | Merged columns from both inputs  |
| Union   | 2      | 1       | Schema must match between inputs |
| Formula | 1      | 1       | Adds computed columns            |
| Rename  | 1      | 1       | Changes column names             |
| Unique  | 1      | 1       | Pass-through (DISTINCT)          |
| Sample  | 1      | 1       | Pass-through (random subset)     |

### Phase 3 (Visualization) — 6 nodes

Bar Chart, Line Chart, Candlestick, Scatter Plot, KPI Card, Pivot Table — all terminal nodes (0 output ports). All render using shared chart components from `shared/components/charts/`.

## Preview Debounce Pattern

- **300ms debounce** after user clicks a node before sending preview request
- **Cancel in-flight requests** when user clicks a different node (via AbortController signal)
- Use TanStack Query with `signal` parameter for automatic cancellation
- `staleTime: 5 * 60 * 1000` (5 minutes) matches server-side Redis cache TTL
- This eliminates 60-70% of unnecessary preview queries
