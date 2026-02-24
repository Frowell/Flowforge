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
| H2 | **FIXED 2026-02-23 ([#72](https://github.com/Frowell/Flowforge/pull/72))** ~~WebSocket pub/sub subscribes to all tenants.~~ Replaced global `psubscribe("flowforge:*")` with dynamic per-tenant subscriptions. Subscribe on first client connect, unsubscribe on last disconnect. | `websocket_manager.py` | Phase 4 (Live Data) | [#50](https://github.com/Frowell/Flowforge/issues/50) |
| H3 | **FIXED 2026-02-20 ([#67](https://github.com/Frowell/Flowforge/pull/67))** ~~No query timeouts on Materialize or ClickHouse execution.~~ Added `asyncio.wait_for()` timeout wrapping for ClickHouse and Materialize query execution. | `query_router.py` | Phase 4 (Live Data) | [#51](https://github.com/Frowell/Flowforge/issues/51) |
| H4 | **FIXED 2026-02-23 ([#73](https://github.com/Frowell/Flowforge/pull/73))** ~~Missing FK indexes on Widget and DashboardFilter.~~ Added `index=True` to `widgets.dashboard_id`, `widgets.source_workflow_id`, and `dashboard_filters.dashboard_id`. | `models/dashboard.py` | Phase 3 (Dashboards) | [#52](https://github.com/Frowell/Flowforge/issues/52) |
| H5 | **FIXED 2026-02-23 ([#73](https://github.com/Frowell/Flowforge/pull/73))** ~~`User.email` is globally unique instead of per-tenant.~~ Replaced with `UniqueConstraint("tenant_id", "email")` composite constraint. | `models/user.py` | Phase 5 (RBAC) | [#53](https://github.com/Frowell/Flowforge/issues/53) |
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
| M6 | **FIXED 2026-02-24** ~~Compiler round-trips SQL through serialization.~~ `CompiledSegment` now carries an `expression` field; `_apply_limits` uses the stored AST directly, falling back to parse only when `expression` is `None`. | `workflow_compiler.py` | Phase 2 (Analytical Nodes) |
| M7 | **FIXED 2026-02-24** ~~Duplicate topological sort implementations.~~ Extracted shared `topological_sort()` into `app/core/graph.py` using `collections.deque`. Both `schema_engine.py` and `workflow_compiler.py` import it. | `app/core/graph.py`, `schema_engine.py`, `workflow_compiler.py` | Phase 2 (Analytical Nodes) |
| M8 | **FIXED 2026-02-20 ([#68](https://github.com/Frowell/Flowforge/pull/68))** ~~All preview/widget columns reported as `dtype: "String"`.~~ `BaseQueryService._build_columns_with_types` now maps actual column types from query results. | `base_query_service.py` | Phase 3 (Dashboards) |
| M9 | **FIXED 2026-02-24** ~~`useExecution` stores WebSocket state in local `useState`.~~ Replaced `useState` with TanStack Query cache (`useQuery` + `queryClient.setQueryData`). Status survives unmount and is accessible from any component. `useRef` for execution ID avoids re-renders. | `hooks/useExecution.ts` | Phase 4 (Live Data) |
| M10 | **FIXED 2026-02-24** ~~Every canvas node does `as unknown as WorkflowNodeData` double-cast.~~ Created `TypedNodeProps<T>` generic that parameterizes `NodeProps` with per-node `TypedNodeData<T>`, eliminating all double-casts. | All 17 node components in `features/canvas/nodes/` | Phase 1 (Core Canvas) |
| M11 | **FIXED 2026-02-24** ~~Node config property access is untyped.~~ Added 17 per-node config interfaces in `features/canvas/types/nodeConfigs.ts` with `NodeConfigMap` type. Config access is now type-safe — no more `as string` casts. | All node components, `types/nodeConfigs.ts` | Phase 1 (Core Canvas) |
| M12 | **FIXED 2026-02-24** ~~`WorkflowVersion` lacks `tenant_id` column.~~ Added `TenantMixin` to `WorkflowVersion`. Migration backfills `tenant_id` from parent `Workflow`. Direct version queries now enforce tenant isolation without joins. | `models/workflow.py`, migration `e9f2a3b4c5d6` | Phase 5 (Audit Logging) |
| M13 | **FIXED 2026-02-24** ~~Schema engine global registry not testable in isolation.~~ `SchemaEngine.__init__` now accepts an optional `transforms` dict. Defaults to the module-level registry for backward compatibility. Tests can inject a custom subset without monkeypatching. | `schema_engine.py` | Phase 2 (Analytical Nodes) |
| M14 | **FIXED 2026-02-24** ~~`APIKey.scoped_widget_ids` uses PostgreSQL ARRAY with no index.~~ Added GIN index `ix_api_keys_scoped_widgets` on `scoped_widget_ids` for efficient "which keys grant access to widget X?" queries. | `models/dashboard.py`, migration `e9f2a3b4c5d6` | Phase 4 (Embed) |

## Low

| # | Finding | File(s) | Natural fix phase |
|---|---------|---------|-------------------|
| L1 | **FIXED 2026-02-20 ([#69](https://github.com/Frowell/Flowforge/pull/69))** ~~`redpanda_brokers` setting in config.~~ Removed `redpanda_brokers` from Settings. No pipeline dependency remains. | `config.py` | Any |
| L2 | **FIXED 2026-02-24** ~~`User.hashed_password` is dead schema.~~ Dropped `hashed_password` column from `users` table. Keycloak handles auth — no password flow exists. | `models/user.py`, migration `e9f2a3b4c5d6` | Phase 5 (RBAC) |
| L3 | **FIXED 2026-02-24** ~~Redis `symbol` extraction hardcoded in query router.~~ Extracted `parse_redis_key()` helper that returns structured parts `{"prefix", "type", "symbol"}`. Router calls the helper instead of inline string splitting. | `query_router.py` | Phase 4 (Live Data) |
| L4 | **FIXED 2026-02-24** ~~`Workflow.graph_json` has no size limit.~~ Added application-level validation in workflow create/update/import routes. Configurable `max_graph_json_bytes` setting (default 5 MB). Returns 400 if exceeded. | `config.py`, `routes/workflows.py` | Phase 5 (Polish) |
| L5 | **FIXED 2026-02-24** ~~`AuditLog` lacks indexes on `resource_id` and `user_id`.~~ Added `ix_audit_logs_user_id` and `ix_audit_logs_resource` (composite on `resource_type`, `resource_id`). | `models/audit_log.py`, migration `e9f2a3b4c5d6` | Phase 5 (Audit Logging) |
| L6 | **FIXED 2026-02-20 ([#69](https://github.com/Frowell/Flowforge/pull/69))** ~~`clickhouse_databases` config not used by compiler.~~ Moved to nested `ClickHouseSettings` and documented that it's used by schema discovery only. | `config.py` | Any |
| L7 | **FIXED 2026-02-20 ([#69](https://github.com/Frowell/Flowforge/pull/69))** ~~`database_url` default contains credentials.~~ Removed inline defaults for `database_url`; environment variables are now required with clear error on missing. | `config.py` | Phase 5 (Polish) |
| L8 | **FIXED 2026-02-20 ([#69](https://github.com/Frowell/Flowforge/pull/69))** ~~Settings class is flat (28 settings).~~ Restructured into nested `DatabaseSettings`, `ClickHouseSettings`, `MaterializeSettings`, `RedisSettings`, `AuthSettings`, `PreviewSettings`. | `config.py` | Any |
| L9 | **FIXED 2026-02-20 ([#69](https://github.com/Frowell/Flowforge/pull/69))** ~~`cors_origins` validator imports `json` inside function body.~~ Moved `json` import to top-level. | `config.py` | Any |
| L10 | **FIXED 2026-02-24** ~~`_detect_target` relies on naming conventions.~~ `_detect_target` now accepts an optional `source` parameter from the data_source node config. Uses explicit source-to-target mapping when available, falls back to prefix heuristic for backward compatibility. `DataSourcePanel` persists `source` in config. | `workflow_compiler.py`, `DataSourcePanel.tsx`, `nodeConfigs.ts` | Phase 4 (Live Data) |
| L11 | **FIXED 2026-02-24** ~~Preview service calls compiler private method `_find_ancestors`.~~ Extracted `find_ancestors()` to `app/core/graph.py` alongside `topological_sort`. All three callers (compiler, preview service, widget data service) now import the standalone function. | `app/core/graph.py`, `workflow_compiler.py`, `preview_service.py`, `widget_data_service.py` | Any |

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
