# FlowForge — Open Architectural Issues

Issues identified during planning.md review that need deeper discussion before or during implementation. These are not blocking Phase 0/1 but should be resolved before their respective phases.

---

## 4. Data Preview Execution Model — RESOLVED

**Status:** Decided — three-layer solution

### Layer 1: Frontend Debounce + Cancellation

Don't fire on click. Fire 300ms after the last click. If the user clicks away within that window, cancel. If a request is already in flight and the user clicks a different node, abort the previous request.

```
User clicks Filter node
  → 300ms timer starts
  → User clicks Group By node (150ms later)
  → Filter timer cancelled, Group By timer starts
  → 300ms passes, no new click
  → Frontend sends preview request for Group By
  → User clicks Join node while Group By query is in flight
  → Frontend aborts Group By request, starts 300ms timer for Join
```

This alone eliminates 60-70% of unnecessary queries.

### Layer 2: Content-Addressed Cache on the Backend

The cache key isn't the node ID — it's a hash of the entire subgraph configuration from source to that node. If nothing in the upstream path has changed, the preview result is the same.

```
Cache key = hash(
    node_id,
    node_config,                    # this node's filter/sort/formula config
    upstream_subgraph_configs[],    # recursively, every upstream node's config
    schema_version                  # invalidates when pipeline pushes new data
)
```

This means:

- Click Filter, get result, click Group By, get result, click Filter again → cache hit, instant response, no query
- Change the Filter condition, click Filter → cache miss, new query (because node_config changed)
- Change Source A's table selection → every downstream node's cache invalidates (because upstream config changed)

Cache lives in Redis with a TTL. Per-session scoping isn't necessary because the content-addressed key already handles it — two different users with identical workflows would share the cache hit, which is fine since they're querying the same data. Tenant isolation is enforced because the compiled SQL already includes the tenant filter, so the cache key naturally differs across tenants.

### Layer 3: Query Constraints

Every preview query is sandboxed:

```sql
SELECT *
FROM (
    -- compiled subgraph query goes here
) AS preview
LIMIT 100
SETTINGS
    max_execution_time = 3,
    max_memory_usage = 100000000,  -- 100MB cap
    max_rows_to_read = 10000000    -- scan cap: 10M rows
```

ClickHouse enforces these server-side. If a preview would scan a billion-row table unfiltered, it hits the row scan cap and returns an error rather than pegging the server for 30 seconds. The frontend shows "Preview unavailable — add a filter to reduce data volume" instead of spinning forever.

### Backend Endpoint

```
POST /api/v1/executions/preview

Request:
{
    "workflow_id": "wf_abc",
    "target_node_id": "filter_1",
    "graph": { "nodes": [...], "edges": [...] }  // current canvas state
}

Response:
{
    "columns": [
        { "name": "symbol", "type": "string" },
        { "name": "price", "type": "float64" },
        { "name": "quantity", "type": "int64" }
    ],
    "rows": [ ... ],           // up to 100 rows
    "total_estimate": 284700,  // approximate row count (from ClickHouse)
    "execution_ms": 47,
    "cache_hit": true
}
```

The `graph` field is the full current canvas state, not just the target node. The backend needs the whole thing to compile the subgraph and compute the cache key. This also means unsaved config changes trigger correct previews — you don't need to save the workflow before previewing.

### Lifecycle Summary

```
User clicks node
  │
  ▼
Frontend: debounce 300ms, cancel any in-flight preview request
  │
  ▼
Frontend: send preview request with full graph + target node ID
  │
  ▼
Backend: compile subgraph (source → target node)
  │
  ▼
Backend: compute cache key (hash of subgraph configs)
  │
  ├─ Cache hit → return cached rows immediately
  │
  ├─ Cache miss →
  │     Compile to SQL with LIMIT 100 + execution constraints
  │     Execute against ClickHouse / Materialize
  │     Store result in Redis (TTL 5 minutes)
  │     Return rows
  │
  └─ Query timeout / scan cap exceeded →
        Return error with message ("add a filter to reduce data volume")
```

---

## 5. No Result Pagination / LIMIT Strategy

**Severity:** Must resolve by Phase 1

**Problem:** Preview results are limited to 100 rows, but the plan doesn't address:

- How LIMIT is applied — at the SQL level (efficient) or after fetching full results (wasteful)?
- Whether cursor-based pagination is supported for table view output nodes that users want to scroll through.
- What happens when a user's workflow produces millions of rows — is there a hard cap?
- How LIMIT interacts with GROUP BY (should grouping happen before or after the limit?).

**Recommendation:** Always push LIMIT into the compiled SQL. For table output nodes, support cursor-based pagination with `OFFSET`/`LIMIT` or ClickHouse's `WITH TOTALS`. Define a hard cap (e.g., 10,000 rows for preview, configurable per output node for dashboard widgets).

---

## 6. Pivot Node Referenced but Never Planned

**Severity:** Low — cosmetic inconsistency

**Problem:** The schema transform contract in planning.md lists "Pivot" as a node type with `group keys + pivoted value columns` output, but the Pivot node does not appear in any implementation phase. The Phase 3 "Pivot Table" is an output/visualization node, not a transform node.

**Options:**
1. Add a Pivot transform node to Phase 2 that restructures data (wide ↔ long). The Pivot Table output node in Phase 3 would then consume its output.
2. Remove Pivot from the schema transform contract and handle pivoting only in the Pivot Table output node's rendering logic (not as a SQL transform).
3. Defer to a later phase as an advanced transform.

---

## 7. No Multi-Tenancy Model

**Severity:** Must resolve before production

**Problem:** planning.md defines a `created_by` column on workflows and dashboards but doesn't describe:

- Is this a single-tenant or multi-tenant application?
- Can users see each other's workflows/dashboards?
- Is there a workspace/organization concept?
- How does Keycloak realm structure map to application tenancy?
- Are serving layer tables shared across tenants or per-tenant?

**Recommendation:** For MVP, single-tenant with Keycloak role-based access (admin/analyst/viewer). Post-MVP, add a `tenant_id` column with Keycloak realm or group mapping. Row-level security in PostgreSQL can enforce tenant isolation.

---

## 8. Workflow Versioning Belongs Earlier Than Phase 5

**Severity:** Medium — tech debt risk

**Problem:** Workflow versioning is listed in Phase 5 (Templates + Polish), but dashboards depend on workflow output nodes. If a user modifies a workflow, all widgets referencing it change immediately. Without versioning:

- There's no way to revert a broken widget
- No audit trail of what changed
- Collaborative editing is dangerous (one user's change breaks another's dashboard)

**Recommendation:** Introduce basic versioning (snapshot `graph_json` on save, show version history, allow rollback) in Phase 2 or 3 alongside dashboards. Full branching/diffing can wait for Phase 5.

---

## 9. No Result Caching Strategy

**Severity:** Must resolve by Phase 3 (dashboards)

**Problem:** When a dashboard loads with 8 widgets, each widget compiles and executes its subgraph independently. If multiple widgets share upstream nodes, the same queries execute multiple times. Additionally:

- No TTL or invalidation strategy for cached results
- No guidance on where to cache (Redis? In-memory?)
- Dashboard refresh intervals (5s, 30s, 1m) compound the problem at scale

**Options:**
1. **Query-level dedup:** Hash compiled SQL, cache results in Redis with configurable TTL. Widgets sharing the same subgraph hit cache.
2. **Subgraph-level dedup:** Identify common subgraphs across widgets on the same dashboard, compile once, share results.
3. **No caching for MVP:** Accept redundant queries, optimize later. Viable if ClickHouse can handle the load.

---

## 10. No Rate Limiting on Embed

**Severity:** Must resolve by Phase 4 (embed)

**Problem:** Embed mode uses API key auth but planning.md doesn't mention rate limiting. An embedded widget on a high-traffic customer portal could generate thousands of requests per second, each triggering a full query compilation and execution.

**Recommendation:**
- Per-API-key rate limits (e.g., 100 req/s default, configurable)
- Response caching with short TTL (10-30s) keyed by API key + filter params
- 429 Too Many Requests response with Retry-After header
- Consider a CDN-friendly cache layer for embed responses

---

## 11. No Observability Plan

**Severity:** Medium — needed before production

**Problem:** No mention of logging, metrics, tracing, or alerting anywhere in planning.md. For a real-time streaming BI tool processing financial data, observability is critical.

**Minimum needs:**
- Structured logging (JSON, correlation IDs per request/WebSocket session)
- Query execution metrics (compilation time, execution time, result size, backing store targeted)
- WebSocket connection metrics (active connections, message throughput, reconnection rate)
- Schema registry health (cache hit rate, stale schema detection)
- Dashboard load time (time to first widget render, time to all widgets loaded)

**Recommended stack:** OpenTelemetry for traces/metrics, structured JSON logging to stdout, Prometheus endpoint for scraping, Grafana dashboards.

---

## 12. Phase 0 Claims ClickHouse/Materialize in DevContainer but They're Not There

**Severity:** Low — Phase 0 scoping

**Problem:** Phase 0 deliverable says "Devcontainer with PostgreSQL, Redis, ClickHouse, and Materialize (dev instances)" and "Seed ClickHouse with sample market data." The current devcontainer only has PostgreSQL and Redis. ClickHouse and Materialize are documented as "not yet added" in `.devcontainer/agents.md`.

**Options:**
1. Add ClickHouse and Materialize to devcontainer now (adds ~2GB to container image, requires seed data scripts).
2. Keep them out of devcontainer, mock in tests, add when Phase 1 integration testing requires them.
3. Use ClickHouse Local (embedded, no server) for development and testing. Lighter weight than a full ClickHouse server.

**Recommendation:** Option 2 for now — all ClickHouse/Materialize interactions are already designed to be mockable. Add them to devcontainer when Phase 1 schema registry integration testing begins, along with seed data for sample market data tables.
