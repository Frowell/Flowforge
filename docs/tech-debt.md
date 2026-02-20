# Tech Debt Registry

> Discovered: 2026-02-11 (codebase audit)
> Updated: 2026-02-20

Items are prioritized by severity: **Critical** (silent wrong data or production incident), **High** (will degrade at scale or block features), **Medium** (code quality / maintainability), **Low** (style or minor inefficiency).

Mark items `FIXED` with date and PR when resolved. Do not delete — the history is useful.

---

## Critical

| # | Finding | File(s) | Natural fix phase | Issue |
|---|---------|---------|-------------------|-------|
| C1 | **FIXED 2026-02-20 ([#60](https://github.com/Frowell/Flowforge/pull/60))** ~~Pivot node has no compiler rule.~~ Compiler now has `_apply_pivot` method and `pivot` branch in `_build_and_merge`. | `workflow_compiler.py` | Phase 2 (Analytical Nodes) | [#44](https://github.com/Frowell/Flowforge/issues/44) |
| C2 | **FIXED 2026-02-20** ~~Widget data has no ClickHouse resource limits.~~ Widget data service now appends ClickHouse `SETTINGS max_execution_time=30, max_memory_usage=500MB, max_rows_to_read=50M` to all ClickHouse-targeted queries, mirroring the preview service pattern with higher limits suitable for dashboard workloads. | `widget_data_service.py` | Phase 3 (Dashboards) | [#45](https://github.com/Frowell/Flowforge/issues/45) |
| C3 | **FIXED 2026-02-11 ([#58](https://github.com/Frowell/Flowforge/pull/58))** ~~Filter values are all cast to strings.~~ Filter values now use typed SQL literals based on column dtype from the schema engine. | `workflow_compiler.py` | Phase 1 (Core Canvas) | [#46](https://github.com/Frowell/Flowforge/issues/46) |
| C4 | **FIXED 2026-02-11 ([#58](https://github.com/Frowell/Flowforge/pull/58))** ~~Unrecognized filter operators silently become `=`.~~ Unknown operators now raise `ValueError`. | `workflow_compiler.py` | Phase 1 (Core Canvas) | [#47](https://github.com/Frowell/Flowforge/issues/47) |
| C5 | **FIXED 2026-02-20 ([#63](https://github.com/Frowell/Flowforge/pull/63))** ~~Join/Union hardcode ClickHouse target.~~ Join and union now inherit target from upstream parents via `_resolve_multi_parent_target`. Cross-store joins/unions are rejected at compile time. | `workflow_compiler.py` | Phase 2 (Analytical Nodes) | [#48](https://github.com/Frowell/Flowforge/issues/48) |

## High

| # | Finding | File(s) | Natural fix phase | Issue |
|---|---------|---------|-------------------|-------|
| H1 | **FIXED 2026-02-20 ([#67](https://github.com/Frowell/Flowforge/pull/67))** ~~Redis SCAN has no key limit or pipelining.~~ Added configurable `REDIS_SCAN_LIMIT` and pipeline batching for `HGETALL` calls. | `query_router.py` | Phase 4 (Live Data) | [#49](https://github.com/Frowell/Flowforge/issues/49) |
| H2 | **WebSocket pub/sub subscribes to all tenants.** Every backend instance runs `psubscribe("flowforge:*")`, deserializing messages for tenants with zero local connections. Wastes CPU proportional to tenant count. | `websocket_manager.py:185` | Phase 4 (Live Data) | [#50](https://github.com/Frowell/Flowforge/issues/50) |
| H3 | **FIXED 2026-02-20 ([#67](https://github.com/Frowell/Flowforge/pull/67))** ~~No query timeouts on Materialize or ClickHouse execution.~~ Added `asyncio.wait_for()` timeout wrapping for ClickHouse and Materialize query execution. | `query_router.py` | Phase 4 (Live Data) | [#51](https://github.com/Frowell/Flowforge/issues/51) |
| H4 | **Missing FK indexes on Widget and DashboardFilter.** `Widget.source_workflow_id`, `Widget.dashboard_id`, `DashboardFilter.dashboard_id` — all lack indexes. Dashboard loading and cascade deletes degrade to table scans. | `models/dashboard.py:53-57, 79` | Phase 3 (Dashboards) | [#52](https://github.com/Frowell/Flowforge/issues/52) |
| H5 | **`User.email` is globally unique instead of per-tenant.** `unique=True` prevents the same email across tenants. Should be `UniqueConstraint("email", "tenant_id")`. | `models/user.py:27` | Phase 5 (RBAC) | [#53](https://github.com/Frowell/Flowforge/issues/53) |
| H6 | **FIXED 2026-02-20** ~~Join schema disagrees with compiled SQL.~~ `_apply_join` now builds an explicit SELECT list matching the schema engine's dedup logic instead of `SELECT *`. All left columns included; only right columns not already in the left set are added. | `workflow_compiler.py` | Phase 2 (Analytical Nodes) | [#54](https://github.com/Frowell/Flowforge/issues/54) |
| H7 | **FIXED 2026-02-20 ([#65](https://github.com/Frowell/Flowforge/pull/65))** ~~WebSocket gauge math is inconsistent.~~ Fixed gauge increment/decrement symmetry in connect/disconnect lifecycle. | `websocket_manager.py` | Phase 4 (Live Data) | [#55](https://github.com/Frowell/Flowforge/issues/55) |
| H8 | **FIXED 2026-02-20 ([#65](https://github.com/Frowell/Flowforge/pull/65))** ~~`_broadcast_to_channel` leaks stale entries in `_ws_channels`.~~ Dead WebSockets are now cleaned from `_ws_channels` during broadcast, preventing memory leaks. | `websocket_manager.py` | Phase 4 (Live Data) | [#56](https://github.com/Frowell/Flowforge/issues/56) |
| H9 | **FIXED 2026-02-20 ([#65](https://github.com/Frowell/Flowforge/pull/65))** ~~No heartbeat/ping on WebSocket connections.~~ Added periodic heartbeat loop (30s interval) that pings connected clients and removes stale connections. | `websocket_manager.py` | Phase 4 (Live Data) | [#57](https://github.com/Frowell/Flowforge/issues/57) |

## Medium

| # | Finding | File(s) | Natural fix phase |
|---|---------|---------|-------------------|
| M1 | **FIXED 2026-02-20 ([#68](https://github.com/Frowell/Flowforge/pull/68))** ~~Preview and widget data services are ~70% duplicated.~~ Extracted shared `BaseQueryService` with cache ops, SQL wrapping, and dtype mapping. Both services now inherit from it. | `base_query_service.py`, `preview_service.py`, `widget_data_service.py` | Phase 3 (Dashboards) |
| M2 | **FIXED 2026-02-20 ([#66](https://github.com/Frowell/Flowforge/pull/66))** ~~`useDataPreview` hand-rolls TanStack Query.~~ Rewrote to use `useQuery` with `signal`, `keepPreviousData`, and debounced query key. | `hooks/useDataPreview.ts` | Phase 1 (Core Canvas) |
| M3 | **FIXED 2026-02-20 ([#66](https://github.com/Frowell/Flowforge/pull/66))** ~~Schema engine recomputes on node drag.~~ Added structural data memoization (`useMemo` on `{id, type, config}`) so schema propagation only fires on config changes, not position updates. | `hooks/useSchemaEngine.ts` | Phase 1 (Core Canvas) |
| M4 | **FIXED 2026-02-20 ([#66](https://github.com/Frowell/Flowforge/pull/66))** ~~Duplicate query key constants.~~ Extracted shared `queryKeys.ts` module imported by both hooks. | `hooks/queryKeys.ts`, `hooks/useWorkflow.ts`, `hooks/useWorkflowVersions.ts` | Phase 1 (Core Canvas) |
| M5 | **FIXED 2026-02-20 ([#68](https://github.com/Frowell/Flowforge/pull/68))** ~~`assert isinstance` in production code.~~ Replaced `assert` with explicit `if not isinstance: raise TypeError` checks in both services. | `preview_service.py`, `widget_data_service.py` | Any |
| M6 | **Compiler round-trips SQL through serialization.** Merge step builds expression objects, serializes to SQL strings in `CompiledSegment`, then `_apply_limits` parses back. Redundant work and dialect edge-case risk. | `workflow_compiler.py:851-861` | Phase 2 (Analytical Nodes) |
| M7 | **Duplicate topological sort implementations.** Schema engine and compiler each have independent Kahn's algorithm. Both use `list.pop(0)` (O(n) per pop). Should share one implementation using `collections.deque`. | `schema_engine.py:307-337`, `workflow_compiler.py:112-135` | Phase 2 (Analytical Nodes) |
| M8 | **FIXED 2026-02-20 ([#68](https://github.com/Frowell/Flowforge/pull/68))** ~~All preview/widget columns reported as `dtype: "String"`.~~ `BaseQueryService._build_columns_with_types` now maps actual column types from query results. | `base_query_service.py` | Phase 3 (Dashboards) |
| M9 | **`useExecution` stores WebSocket state in local `useState`.** Status lost on unmount. Other components can't access execution status without prop-drilling. Should use TanStack Query cache or Zustand. | `hooks/useExecution.ts:12-13` | Phase 4 (Live Data) |
| M10 | **Every canvas node does `as unknown as WorkflowNodeData` double-cast.** React Flow generics not properly configured. Should use `NodeProps<WorkflowNodeData>`. | All 16 node components in `features/canvas/nodes/` | Phase 1 (Core Canvas) |
| M11 | **Node config property access is untyped.** `nodeData.config?.column as string \| undefined` with no per-node-type config type definitions. No compile-time safety on config shape. | All node components | Phase 1 (Core Canvas) |
| M12 | **`WorkflowVersion` lacks `tenant_id` column.** Relies on FK join through `Workflow` for tenant scoping. Direct version queries (audit log lookups) can't enforce tenant isolation without the join. | `models/workflow.py:52-71` | Phase 5 (Audit Logging) |
| M13 | **Schema engine global registry not testable in isolation.** Module-level `_transforms` dict populated at import time. Can't inject a custom subset for unit tests without monkeypatching. | `schema_engine.py:22` | Phase 2 (Analytical Nodes) |
| M14 | **`APIKey.scoped_widget_ids` uses PostgreSQL ARRAY.** Needs GIN index for "which keys grant access to widget X?" queries. Junction table would be more normalized and indexable. | `models/dashboard.py:101` | Phase 4 (Embed) |

## Low

| # | Finding | File(s) | Natural fix phase |
|---|---------|---------|-------------------|
| L1 | **FIXED 2026-02-20 ([#69](https://github.com/Frowell/Flowforge/pull/69))** ~~`redpanda_brokers` setting in config.~~ Removed `redpanda_brokers` from Settings. No pipeline dependency remains. | `config.py` | Any |
| L2 | **`User.hashed_password` is dead schema.** NOT NULL column with no password auth flow. Keycloak handles auth. Adds migration burden and security audit surface. | `models/user.py:28` | Phase 5 (RBAC) |
| L3 | **Redis `symbol` extraction hardcoded in query router.** Assumes `latest:type:SYMBOL` key format. Domain-specific fintech logic in a generic routing layer. | `query_router.py:156-159` | Phase 4 (Live Data) |
| L4 | **`Workflow.graph_json` has no size limit.** A workflow with hundreds of nodes and large configs could produce megabytes of JSONB. Combined with `WorkflowVersion` storing full copies, `workflow_versions` table grows fast. | `models/workflow.py:37` | Phase 5 (Polish) |
| L5 | **`AuditLog` lacks indexes on `resource_id` and `user_id`.** Only has `(tenant_id, created_at)` composite. "All events for this workflow" and "all actions by this user" are common queries with no index. | `models/audit_log.py:39-46` | Phase 5 (Audit Logging) |
| L6 | **FIXED 2026-02-20 ([#69](https://github.com/Frowell/Flowforge/pull/69))** ~~`clickhouse_databases` config not used by compiler.~~ Moved to nested `ClickHouseSettings` and documented that it's used by schema discovery only. | `config.py` | Any |
| L7 | **FIXED 2026-02-20 ([#69](https://github.com/Frowell/Flowforge/pull/69))** ~~`database_url` default contains credentials.~~ Removed inline defaults for `database_url`; environment variables are now required with clear error on missing. | `config.py` | Phase 5 (Polish) |
| L8 | **FIXED 2026-02-20 ([#69](https://github.com/Frowell/Flowforge/pull/69))** ~~Settings class is flat (28 settings).~~ Restructured into nested `DatabaseSettings`, `ClickHouseSettings`, `MaterializeSettings`, `RedisSettings`, `AuthSettings`, `PreviewSettings`. | `config.py` | Any |
| L9 | **FIXED 2026-02-20 ([#69](https://github.com/Frowell/Flowforge/pull/69))** ~~`cors_origins` validator imports `json` inside function body.~~ Moved `json` import to top-level. | `config.py` | Any |
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
# TODO(debt): C1 — pivot node has no compiler rule
```

This makes findings discoverable via `grep -r "TODO(debt)"` and links back to this registry.
