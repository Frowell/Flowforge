# Serving Layer & Query Router

> Parent: [`/workspace/agents.md`](../agents.md) | Architecture (archived): [`/workspace/docs/archive/Application plan.md`](./archive/Application%20plan.md)

## Table Catalog

The application reads from these tables/views — it does NOT create or write to them. The data pipeline populates them independently.

| Table | Store | Freshness | Content |
|-------|-------|-----------|---------|
| `flowforge.raw_trades` | ClickHouse | Warm (seconds) | Raw trade events |
| `flowforge.raw_quotes` | ClickHouse | Warm (seconds) | Raw quote events |
| `metrics.vwap_5min` | ClickHouse | Warm (seconds) | 5-min VWAP windows (Bytewax) |
| `metrics.rolling_volatility` | ClickHouse | Warm (seconds) | Rolling volatility (Bytewax) |
| `metrics.hourly_rollup` | ClickHouse | Cool (minutes) | OHLCV per symbol per hour (MV) |
| `metrics.daily_rollup` | ClickHouse | Cool (minutes) | OHLCV per symbol per day (MV) |
| `marts.fct_trades` | ClickHouse | Cold (hours) | Enriched trade facts (dbt) |
| `marts.dim_instruments` | ClickHouse | Cold (hours) | Instrument reference data (dbt) |
| `marts.rpt_daily_pnl` | ClickHouse | Cold (hours) | Daily P&L report (dbt) |
| `live_positions` | Materialize | Hot (< 100ms) | Real-time net position per symbol |
| `live_quotes` | Materialize | Hot (< 100ms) | Latest bid/ask per symbol |
| `live_pnl` | Materialize | Hot (< 100ms) | Unrealized P&L per symbol |
| `latest:vwap:*` | Redis | Warm (seconds) | Point lookup for latest VWAP (hash per symbol) |
| `latest:position:*` | Redis | Warm (seconds) | Point lookup for latest position (hash per symbol) |
| `latest:volatility:*` | Redis | Warm (seconds) | Point lookup for latest volatility (hash per symbol) |

---

## Query Router Rules

The query router (`backend/app/services/query_router.py`) is the ONLY component that knows about backing stores.

### Automatic Target Detection

The workflow compiler (`workflow_compiler.py`) auto-detects the target backing store from the data source table name. Users never specify the target — they pick a table from the catalog and the compiler routes automatically.

| Table name pattern | Target | Method | Latency target |
|---|---|---|---|
| `latest:*` (e.g., `latest:vwap:*`) | Redis | SCAN + HGETALL | < 1ms |
| `live_*` (e.g., `live_positions`) | Materialize | SQL query | < 10ms |
| Everything else | ClickHouse | SQL query | < 500ms |
| App metadata / catalog | PostgreSQL | ORM query | < 50ms |

Detection is implemented in `WorkflowCompiler._detect_target()`. The target propagates through the DAG — downstream nodes (Filter, Sort, GroupBy) inherit the target from their root data source.

### Redis SCAN_HASH Execution

For Redis-backed data sources, the query router performs:

1. `SCAN` for keys matching the pattern (e.g., `latest:vwap:*`)
2. `HGETALL` on each matching key to retrieve the hash fields
3. Symbol extraction from the key name (e.g., `latest:vwap:AAPL` → `symbol = "AAPL"`)

Redis segments carry no SQL — they use params `{ lookup_type: "SCAN_HASH", pattern: "..." }`.

### Design Decision

See [ADR 0009: Table-Name Pattern Routing](./decisions/0009-table-name-pattern-routing.md) for the full rationale and alternatives considered.

---

## SQL Dialect per Target

| Target | Dialect | Protocol | Client |
|--------|---------|----------|--------|
| ClickHouse | `dialect="clickhouse"` | HTTP (port 8123) | `clickhouse-connect` |
| Materialize | `dialect="postgres"` | PG wire (port 6875) | `asyncpg` |
| PostgreSQL | `dialect="postgres"` | PG wire (port 5432) | `asyncpg` via SQLAlchemy |
| Redis | N/A (key-value) | Redis protocol | `redis-py` |

---

## Live Update Path

The pipeline publishes row data via Redis PUBLISH when flushing to the serving layer. The backend WebSocket manager forwards these messages to connected dashboard clients, which merge rows directly into TanStack Query cache without an HTTP round trip.

| Flow | Publishes to | Channel | Payload |
|------|-------------|---------|---------|
| Raw Sink | ClickHouse + Redis pub/sub | `flowforge:broadcast:table_rows` | `{ type: "table_rows", table, columns, rows }` |
| VWAP | ClickHouse + Redis hash + pub/sub | `flowforge:broadcast:table_rows` | `{ type: "table_rows", table: "vwap_5min", ... }` |
| Volatility | ClickHouse + Redis hash + pub/sub | `flowforge:broadcast:table_rows` | `{ type: "table_rows", table: "rolling_volatility", ... }` |
| Positions | Redis hash + pub/sub | `flowforge:broadcast:table_rows` | `{ type: "table_rows", table: "latest:position:*", ... }` |

End-to-end latency: ~210ms. See [ADR 0010: WebSocket Row Push](./decisions/0010-websocket-row-push.md) and [RFC 0002: Sub-200ms Live Updates](./rfcs/0002-sub-200ms-live-updates.md).

---

## Access Patterns

- **Read-only**: The app NEVER writes to ClickHouse, Materialize, or Redis serving data. These stores are populated by the data pipeline (separate workstream).
- **Parameterized queries**: All user-supplied values are parameterized via SQLGlot — never string-concatenated.
- **Tenant isolation on shared data**: Serving-layer tables have no `tenant_id` column. Isolation is via symbol-based ACL injected at the compiler level (`WHERE symbol IN (:allowed_symbols)`).
