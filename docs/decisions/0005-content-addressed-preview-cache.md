# 0005: Content-Addressed Preview Cache with Three-Layer Protection

**Status:** Accepted
**Date:** 2025-11-01
**Deciders:** Architecture team

## Context

When a user clicks a node on the canvas, the app shows a data preview (up to 100 rows). Naive implementation fires a query on every click, which is wasteful — users click rapidly between nodes, often revisiting nodes they've already previewed. Additionally, unfiltered previews against billion-row ClickHouse tables could overload the cluster.

## Decision

Three-layer preview protection:

1. **Frontend debounce + cancellation**: 300ms debounce on node clicks. In-flight requests are aborted when the user clicks a different node. Eliminates 60-70% of unnecessary queries.

2. **Content-addressed cache (Redis)**: Cache key is a hash of `(node_id, node_config, upstream_subgraph_configs[], schema_version)` — not the node ID alone. This means identical subgraph configurations share cache hits across users and sessions. Tenant isolation is inherent because compiled SQL includes tenant filters, making the cache key naturally tenant-scoped. TTL: 5 minutes.

3. **Query sandboxing (ClickHouse settings)**: Every preview query is wrapped with `LIMIT 100`, `max_execution_time = 3s`, `max_memory_usage = 100MB`, `max_rows_to_read = 10M`. ClickHouse enforces these server-side. Queries exceeding limits return an error, not a timeout.

## Alternatives Considered

**Session-scoped cache (per-user)**: Simpler but wastes cache. Two users with identical workflows would each execute the same query. Content-addressed caching is naturally deduped.

**No debounce, rely only on caching**: Cache misses still fire queries on rapid clicks. The debounce layer is cheap and prevents unnecessary cache lookups too.

**Client-side caching only (TanStack Query)**: Doesn't protect the backend from redundant queries across different browser sessions.

## Consequences

- **Positive**: Rapid node clicking feels instant — most clicks hit cache or get debounced away.
- **Positive**: Runaway queries are impossible — ClickHouse enforces resource limits server-side.
- **Positive**: Cross-user cache sharing — identical workflows benefit from shared cache hits.
- **Negative**: Cache key computation requires traversing the upstream subgraph, adding complexity to the preview service.
- **Negative**: The 3-second query timeout means some complex previews fail. The frontend must handle this gracefully.
