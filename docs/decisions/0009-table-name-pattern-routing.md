# 0009: Table-Name Pattern Routing for Multi-Store Query Dispatch

**Status:** Accepted
**Date:** 2026-02-10
**Deciders:** Backend team

## Context

The workflow compiler translates canvas DAGs into SQL segments, and the query router dispatches each segment to the appropriate backing store (ClickHouse, Materialize, or Redis). Previously, the compiler hardcoded `target="clickhouse"` for all segments regardless of data source. This meant Redis-backed data sources (`latest:vwap:*`, `latest:position:*`, `latest:volatility:*`) and Materialize-backed views (`live_positions`, `live_pnl`, `live_quotes`) were incorrectly sent to ClickHouse, returning empty results or errors.

The system needed a way to determine the correct backing store for each compiled segment without requiring users to manually specify it — users pick tables from the schema catalog and shouldn't need to know which database holds the data.

## Decision

The workflow compiler auto-detects the target backing store from the **data source table name pattern**:

| Pattern | Target | Dialect | Method |
|---------|--------|---------|--------|
| `latest:*` | Redis | *(none — no SQL)* | SCAN + HGETALL |
| `live_*` | Materialize | `postgres` | SQL query |
| Everything else | ClickHouse | `clickhouse` | SQL query |

Detection happens in `_detect_target()` at compile time. The target propagates through the DAG alongside expression trees — downstream nodes (Filter, Sort, GroupBy, etc.) inherit their root data source's target. For joins where inputs come from different backing stores, each branch compiles to its own segment with the correct target.

Redis segments carry no SQL. Instead they carry params `{ lookup_type: "SCAN_HASH", pattern: "latest:vwap:*" }`. The query router performs a Redis `SCAN` for matching keys, then `HGETALL` on each key to retrieve hash fields. The symbol identifier is extracted from the key name (e.g., `latest:vwap:AAPL` → `symbol = "AAPL"`).

## Alternatives Considered

**Explicit target annotation on data source nodes**: Users select the backing store when configuring a data source node. Rejected because it leaks infrastructure details into the user experience. Users think in tables, not databases.

**Schema registry metadata**: The schema registry could tag each table with its backing store during discovery. The compiler would look up the tag. Viable but adds a runtime dependency on the registry during compilation. Table name patterns are deterministic and don't require a lookup.

**Query router decides at execution time**: Keep the compiler target-unaware and let the router inspect the SQL to determine the target. Rejected because Redis segments don't have SQL — the compiler must know at compile time to generate the correct params instead of a SQL string.

**Convention-free mapping table**: A static configuration file mapping table names to backing stores. Rejected because it requires manual updates when new tables are added. The prefix convention (`latest:*`, `live_*`) is self-documenting and scales without configuration.

## Consequences

- **Positive**: Users pick any table from the catalog and get correct results. No infrastructure knowledge required.
- **Positive**: Adding new tables to the pipeline requires no application changes — if the pipeline writes to `latest:spread:*`, the compiler routes it to Redis automatically.
- **Positive**: Redis hash lookups return sub-millisecond results for point data (VWAP, positions, volatility), matching the latency expectations for live dashboards.
- **Negative**: The prefix convention is implicit. A pipeline that writes to Redis without the `latest:` prefix would be misrouted to ClickHouse. This is mitigated by the pipeline's documented naming conventions.
- **Negative**: Redis segments bypass query merging (no SQL to merge). A Filter node downstream of a Redis source cannot push down the filter — all rows are fetched and filtering happens client-side. This is acceptable because Redis hash datasets are small (10-50 keys).
