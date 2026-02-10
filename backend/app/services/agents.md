# Services — Agent Rules

> Parent rules: [`/workspace/backend/agents.md`](../../agents.md)

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

## Schema Discovery SQL

The SchemaRegistry discovers tables/columns by querying:

**ClickHouse** (databases: `flowforge`, `metrics`, `marts`):
```sql
SELECT database, table, name, type
FROM system.columns
WHERE database IN ('flowforge', 'metrics', 'marts')
ORDER BY database, table, name;
```

**Materialize** (excludes internal schemas):
```sql
SELECT s.name AS schema_name, o.name AS object_name, c.name AS column_name, c.type_oid::regtype::text AS data_type
FROM mz_columns c
JOIN mz_objects o ON c.id = o.id
JOIN mz_schemas s ON o.schema_id = s.id
WHERE s.name NOT IN ('mz_internal', 'mz_catalog', 'pg_catalog', 'information_schema');
```

Discovery runs on startup and every 60 seconds. Results are cached in the `SchemaRegistry` singleton and in Redis (tenant-scoped cache keys).

## Serving Layer Routing Rules

| Table | Backing Store | Reason |
|-------|---------------|--------|
| `materialize.live_positions` | Materialize | Live data, < 10ms |
| `materialize.live_quotes` | Materialize | Live data, < 10ms |
| `materialize.live_pnl` | Materialize | Live data, < 10ms |
| `flowforge.raw_trades` | ClickHouse | Historical, ad-hoc analytical |
| `flowforge.raw_quotes` | ClickHouse | Historical, ad-hoc analytical |
| `metrics.vwap_5min` | ClickHouse | Windowed metrics |
| `metrics.rolling_volatility` | ClickHouse | Windowed metrics |
| `metrics.hourly_rollup` | ClickHouse | Pre-aggregated rollups |
| `metrics.daily_rollup` | ClickHouse | Pre-aggregated rollups |
| `marts.fct_trades` | ClickHouse | Enriched mart (dbt) |
| `marts.dim_instruments` | ClickHouse | Reference data (dbt) |
| `marts.rpt_daily_pnl` | ClickHouse | Reporting (dbt) |
| `latest:vwap:*` | Redis | Point lookup, < 1ms |
| `latest:position:*` | Redis | Point lookup, < 1ms |

## Workflow Compilation Steps

The compiler follows these steps when compiling a subgraph:

1. Receive full graph JSON + `target_node_id`
2. Walk backward from target node through edges to extract the relevant subgraph
3. Topologically sort the subgraph
4. For each node, generate a SQLGlot expression tree based on `node_type` + `config`
5. Merge adjacent compatible nodes into single queries (query merging — mandatory)
6. Determine backing store from the source node's table via the query router
7. Inject tenant filter (`WHERE tenant_id = :tid`) into compiled SQL
8. Return `(compiled_sql, backing_store)`
