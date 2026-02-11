# Tech Debt Registry

> Discovered: 2026-02-11 (codebase audit)
> Updated: 2026-02-11

Items are prioritized by severity: **Critical** (silent wrong data or production incident), **High** (will degrade at scale or block features), **Medium** (code quality / maintainability), **Low** (style or minor inefficiency).

Mark items `FIXED` with date and PR when resolved. Do not delete — the history is useful.

---

## Critical

| # | Finding | File(s) | Natural fix phase |
|---|---------|---------|-------------------|
| C1 | **Pivot node has no compiler rule.** Schema engine registers `pivot_transform`, so the canvas shows pivot as valid. Compiler silently skips it — no `elif node_type == "pivot"` branch. Users get results without the pivot applied. Silent wrong data. | `schema_engine.py:145-173`, `workflow_compiler.py` (missing branch) | Phase 2 (Analytical Nodes) |
| C2 | **Widget data has no ClickHouse resource limits.** Preview service applies `max_execution_time`, `max_memory_usage`, `max_rows_to_read`. Widget data service has none. A dashboard widget can run unbounded queries against ClickHouse, degrading the cluster for all tenants. | `widget_data_service.py:133-155` (compare `preview_service.py:192-197`) | Phase 3 (Dashboards) |
| C3 | **Filter values are all cast to strings.** `_apply_filter` wraps every value in `exp.Literal.string(str(value))`. `WHERE price > '100'` uses string comparison, not numeric. ClickHouse may coerce; Materialize/PG won't. | `workflow_compiler.py:434` | Phase 1 (Core Canvas) |
| C4 | **Unrecognized filter operators silently become `=`.** Fallback `else` branch defaults to `exp.EQ`. No error, no warning. Users apply "greater than" and get "equals." | `workflow_compiler.py:486-487` | Phase 1 (Core Canvas) |
| C5 | **Join/Union hardcode ClickHouse target.** Both set `target="clickhouse"` regardless of input targets. Joining two Materialize views sends the query to ClickHouse where the tables don't exist. | `workflow_compiler.py:293-294, 312-313` | Phase 2 (Analytical Nodes) |

## High

| # | Finding | File(s) | Natural fix phase |
|---|---------|---------|-------------------|
| H1 | **Redis SCAN has no key limit or pipelining.** Scans ALL matching keys, then sequential `HGETALL` on each. Unbounded memory and O(n) sequential calls. A broad `latest:*` pattern spikes Redis latency for all tenants. | `query_router.py:139-161` | Phase 4 (Live Data) |
| H2 | **WebSocket pub/sub subscribes to all tenants.** Every backend instance runs `psubscribe("flowforge:*")`, deserializing messages for tenants with zero local connections. Wastes CPU proportional to tenant count. | `websocket_manager.py:185` | Phase 4 (Live Data) |
| H3 | **No query timeouts on Materialize or ClickHouse execution.** Router's `_execute_materialize` and `_execute_clickhouse` have no `statement_timeout` or async cancellation. Hung query blocks the worker indefinitely. | `query_router.py` (execute methods) | Phase 4 (Live Data) |
| H4 | **Missing FK indexes on Widget and DashboardFilter.** `Widget.source_workflow_id`, `Widget.dashboard_id`, `DashboardFilter.dashboard_id` — all lack indexes. Dashboard loading and cascade deletes degrade to table scans. | `models/dashboard.py:53-57, 79` | Phase 3 (Dashboards) |
| H5 | **`User.email` is globally unique instead of per-tenant.** `unique=True` prevents the same email across tenants. Should be `UniqueConstraint("email", "tenant_id")`. | `models/user.py:27` | Phase 5 (RBAC) |
| H6 | **Join schema disagrees with compiled SQL.** Schema engine drops duplicate column names from right side; compiled SQL returns both via `SELECT *` with aliases. Frontend shows fewer columns than query returns. | `schema_engine.py:105-110` vs `workflow_compiler.py` join compilation | Phase 2 (Analytical Nodes) |
| H7 | **WebSocket gauge math is inconsistent.** `connect` increments once, `subscribe_to_channel` doesn't increment, but `disconnect` decrements per call. Gauge can go negative. | `websocket_manager.py` (connect/disconnect/subscribe methods) | Phase 4 (Live Data) |
| H8 | **`_broadcast_to_channel` leaks stale entries in `_ws_channels`.** Dead WebSockets are removed from the channel set but not from `_ws_channels`. Only `disconnect_all` cleans both sides. Memory leak over time. | `websocket_manager.py:146-147` | Phase 4 (Live Data) |
| H9 | **No heartbeat/ping on WebSocket connections.** CLAUDE.md mentions heartbeat handling but no implementation exists. Stale TCP connections aren't detected until a message send fails. | `websocket_manager.py` | Phase 4 (Live Data) |

## Medium

| # | Finding | File(s) | Natural fix phase |
|---|---------|---------|-------------------|
| M1 | **Preview and widget data services are ~70% duplicated.** Cache key computation, SQL wrapping, `_cache_get`/`_cache_set`, `dtype: "String"` mapping — all copy-pasted. Fixes to one are missed in the other (C2 proves this). Extract shared base or composed service. | `preview_service.py`, `widget_data_service.py` | Phase 3 (Dashboards) |
| M2 | **`useDataPreview` hand-rolls TanStack Query.** 130 lines of `useState`/`useEffect`/`setTimeout`/`AbortController` instead of `useQuery` with `signal` and `keepPreviousData`. Contradicts the project's own stated patterns. | `hooks/useDataPreview.ts` | Phase 1 (Core Canvas) |
| M3 | **Schema engine recomputes on node drag.** `useSchemaEngine` depends on `nodes` array reference, which changes on every position update. Should depend on `{id, type, config}` only — position is irrelevant. 50-node canvas fires propagation 60x/sec during drag. | `hooks/useSchemaEngine.ts:19-39` | Phase 1 (Core Canvas) |
| M4 | **Duplicate query key constants.** `WORKFLOWS_KEY` and `VERSIONS_KEY` defined identically in `useWorkflow.ts` and `useWorkflowVersions.ts`. One changes without the other and cache invalidation silently breaks. | `hooks/useWorkflow.ts:10-11`, `hooks/useWorkflowVersions.ts:9-10` | Phase 1 (Core Canvas) |
| M5 | **`assert isinstance` in production code.** Both services use `assert` for SQLGlot type narrowing. Stripped with `python -O`. Should be `if not isinstance: raise TypeError`. | `preview_service.py:182`, `widget_data_service.py:137` | Any |
| M6 | **Compiler round-trips SQL through serialization.** Merge step builds expression objects, serializes to SQL strings in `CompiledSegment`, then `_apply_limits` parses back. Redundant work and dialect edge-case risk. | `workflow_compiler.py:851-861` | Phase 2 (Analytical Nodes) |
| M7 | **Duplicate topological sort implementations.** Schema engine and compiler each have independent Kahn's algorithm. Both use `list.pop(0)` (O(n) per pop). Should share one implementation using `collections.deque`. | `schema_engine.py:307-337`, `workflow_compiler.py:112-135` | Phase 2 (Analytical Nodes) |
| M8 | **All preview/widget columns reported as `dtype: "String"`.** Loses type information the frontend needs for number formatting, date parsing, and correct sorting. | `preview_service.py:101`, `widget_data_service.py:161` | Phase 3 (Dashboards) |
| M9 | **`useExecution` stores WebSocket state in local `useState`.** Status lost on unmount. Other components can't access execution status without prop-drilling. Should use TanStack Query cache or Zustand. | `hooks/useExecution.ts:12-13` | Phase 4 (Live Data) |
| M10 | **Every canvas node does `as unknown as WorkflowNodeData` double-cast.** React Flow generics not properly configured. Should use `NodeProps<WorkflowNodeData>`. | All 16 node components in `features/canvas/nodes/` | Phase 1 (Core Canvas) |
| M11 | **Node config property access is untyped.** `nodeData.config?.column as string \| undefined` with no per-node-type config type definitions. No compile-time safety on config shape. | All node components | Phase 1 (Core Canvas) |
| M12 | **`WorkflowVersion` lacks `tenant_id` column.** Relies on FK join through `Workflow` for tenant scoping. Direct version queries (audit log lookups) can't enforce tenant isolation without the join. | `models/workflow.py:52-71` | Phase 5 (Audit Logging) |
| M13 | **Schema engine global registry not testable in isolation.** Module-level `_transforms` dict populated at import time. Can't inject a custom subset for unit tests without monkeypatching. | `schema_engine.py:22` | Phase 2 (Analytical Nodes) |
| M14 | **`APIKey.scoped_widget_ids` uses PostgreSQL ARRAY.** Needs GIN index for "which keys grant access to widget X?" queries. Junction table would be more normalized and indexable. | `models/dashboard.py:101` | Phase 4 (Embed) |

## Low

| # | Finding | File(s) | Natural fix phase |
|---|---------|---------|-------------------|
| L1 | **`redpanda_brokers` setting in config.** Violates "no pipeline dependencies" rule. Used only for health checks. Either remove the health check or acknowledge the exception. | `config.py:67`, `routes/health.py:123` | Any |
| L2 | **`User.hashed_password` is dead schema.** NOT NULL column with no password auth flow. Keycloak handles auth. Adds migration burden and security audit surface. | `models/user.py:28` | Phase 5 (RBAC) |
| L3 | **Redis `symbol` extraction hardcoded in query router.** Assumes `latest:type:SYMBOL` key format. Domain-specific fintech logic in a generic routing layer. | `query_router.py:156-159` | Phase 4 (Live Data) |
| L4 | **`Workflow.graph_json` has no size limit.** A workflow with hundreds of nodes and large configs could produce megabytes of JSONB. Combined with `WorkflowVersion` storing full copies, `workflow_versions` table grows fast. | `models/workflow.py:37` | Phase 5 (Polish) |
| L5 | **`AuditLog` lacks indexes on `resource_id` and `user_id`.** Only has `(tenant_id, created_at)` composite. "All events for this workflow" and "all actions by this user" are common queries with no index. | `models/audit_log.py:39-46` | Phase 5 (Audit Logging) |
| L6 | **`clickhouse_databases` config not used by compiler.** Setting exists for schema discovery but compiler hardcodes `("clickhouse", "clickhouse")` as default target. | `config.py:54`, `workflow_compiler.py:404-410` | Any |
| L7 | **`database_url` default contains credentials.** Dev-only defaults committed to source. No production guard like `secret_key` has. | `config.py:36-37` | Phase 5 (Polish) |
| L8 | **Settings class is flat (28 settings).** No nested grouping (e.g., `ClickhouseSettings`). Will become unwieldy as settings grow. | `config.py` | Any |
| L9 | **`cors_origins` validator imports `json` inside function body.** Inconsistent with top-level imports in the rest of the file. | `config.py:96-99` | Any |
| L10 | **`_detect_target` relies on naming conventions.** A ClickHouse table named `live_analytics` would route to Materialize. No validation against actual schema registry. | `workflow_compiler.py:404-410` | Phase 4 (Live Data) |
| L11 | **Preview service calls compiler private method `_find_ancestors`.** Tight coupling — refactoring compiler internals breaks preview cache key computation. | `preview_service.py:133`, `widget_data_service.py:191` | Any |

---

## Inline TODO convention

For localized findings, add a comment at the site:

```python
# TODO(debt): <registry-id> — <one-line description>
```

Example:
```python
# TODO(debt): C3 — filter values cast to string; should use typed literals
val_expr = exp.Literal.string(str(value))
```

This makes findings discoverable via `grep -r "TODO(debt)"` and links back to this registry.
