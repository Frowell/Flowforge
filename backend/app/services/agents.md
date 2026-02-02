# Services — Agent Rules

> Parent rules: [`/workspace/backend/agents.md`](../../agents.md) | Architecture: [`/workspace/planning.md`](../../../planning.md)

## Multi-Tenancy in Services

All services that access data or produce queries must be tenant-aware:

- Services receive `tenant_id` as an explicit parameter — never extract it themselves from auth context.
- The route handler is responsible for extracting `tenant_id` from the JWT and passing it to services.
- Cache keys (Redis) MUST include `tenant_id` to prevent cross-tenant data leaks.
- Compiled SQL MUST include tenant filters for multi-tenant serving-layer tables.
- WebSocket pub/sub channels MUST include `tenant_id` in the channel name.

## Schema Registry (`schema_registry.py`)

- Reads table/column metadata from ClickHouse `system.columns` and Materialize `mz_catalog`.
- Caches discovered schemas in Redis with a configurable TTL. **Cache keys are prefixed with `tenant_id`** — different tenants may have access to different tables.
- **Strictly read-only** — never creates tables, views, or modifies external schemas.
- Exposes a unified catalog interface regardless of backing store.
- Periodically refreshes on a timer and on-demand when a user opens the canvas.

## Schema Engine (`schema_engine.py`)

- Server-side DAG validation: walks the workflow graph and applies registered schema transform functions per node type.
- Each node type registers a function: `(node_config, input_schemas) → output_schema`.
- **Must match the TypeScript engine** in `frontend/src/shared/schema/propagation.ts` — same logic, same results. If you change one, change the other.
- Validates type compatibility on every connection before execution.
- Returns detailed error information (node ID, port, expected vs actual types) on validation failure.

## Workflow Compiler (`workflow_compiler.py`)

- **Step 1**: Topological sort the node DAG to determine execution order.
- **Step 2**: Build SQLGlot expression trees for each node.
- **Step 3**: Merge adjacent compatible nodes into single queries. Filter → Select → Sort on the same source = one `SELECT ... WHERE ... ORDER BY`, not three queries.
- **Step 4**: Determine target backing store per query segment based on source table freshness requirements.
- **Step 5**: Inject tenant filter (`WHERE tenant_id = :tid`) into compiled SQL when serving-layer tables contain multi-tenant data. This is a mandatory step — the compiler receives `tenant_id` and applies it at the SQL level.
- **Never** produce one-query-per-node output. Query merging is mandatory.
- Multi-source DAGs (joins) produce subqueries or CTEs as needed.
- All SQL generation uses SQLGlot — never string concatenation.

## Query Router (`query_router.py`)

- Dispatches compiled queries to the appropriate backing store based on freshness intent:
  - **Live data** → Materialize (< 10ms)
  - **Point lookup** → Redis (< 1ms)
  - **Analytical** → ClickHouse (< 500ms)
- This is the **only** code outside `app/core/` that imports backing store clients.
- Nodes and the compiler express query intent, not destination. The router decides.
- Handles connection pooling, timeouts, and retries per store.

## Formula Parser (`formula_parser.py`)

- Parses bracket-notation column references: `[column_name]`.
- Builds an AST from the expression grammar (arithmetic, functions, conditionals).
- Compiles AST → SQL via SQLGlot, handling dialect differences (ClickHouse vs Materialize/PG).
- Validates all referenced columns against the input schema — rejects unknown columns with clear error messages.
- Supports: math, text, date, logic, aggregate (inside Group By only), and window functions (with Sort defined).

## Preview Service (`preview_service.py`)

- Content-addressed Redis cache for preview results.
- **Cache keys MUST include `tenant_id`** — hash of `(tenant_id, target_node_id, subgraph_configs, offset, limit)`. Without `tenant_id` in the key, tenant A could receive tenant B's cached result for an identical query structure.
- Query constraints: `LIMIT 100`, `max_execution_time = 3`, `max_memory_usage = 100MB`, `max_rows_to_read = 10M`.
- Preview SQL includes tenant filter from the compiler output.

## WebSocket Manager (`websocket_manager.py`)

- Tracks active WebSocket connections per user/session.
- Pushes execution status updates (pending → running → complete/error) to connected clients.
- Pushes live data updates for Materialize-backed sources.
- Uses Redis pub/sub for multi-instance support — any backend instance can publish, all instances with connected clients receive.
- **Pub/sub channels are tenant-scoped** — channel names include `tenant_id` to prevent cross-tenant message leakage. Format: `flowforge:{tenant_id}:execution:{execution_id}`.
- Handles connection lifecycle: connect, disconnect, reconnect, heartbeat.
