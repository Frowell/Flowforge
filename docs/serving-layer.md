# Serving Layer & Query Router

> Parent: [`/workspace/agents.md`](../agents.md) | Architecture: [`/workspace/Application plan.md`](../Application%20plan.md)

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
| `latest:vwap:*` | Redis | Warm (seconds) | Point lookup for latest VWAP |
| `latest:position:*` | Redis | Warm (seconds) | Point lookup for latest position |

---

## Query Router Rules

The query router (`backend/app/services/query_router.py`) is the ONLY component that knows about backing stores.

| Query intent | Target | Latency target |
|---|---|---|
| Live data (positions, P&L) | Materialize | < 10ms |
| Point lookup (latest quote) | Redis | < 1ms |
| Ad-hoc analytical query | ClickHouse | < 500ms |
| Historical time-range query | ClickHouse rollups | < 500ms |
| App metadata / catalog | PostgreSQL | < 50ms |

Canvas nodes express intent (e.g., "I need the positions table with realtime freshness"), NOT destination. The router dispatches.

---

## SQL Dialect per Target

| Target | Dialect | Protocol | Client |
|--------|---------|----------|--------|
| ClickHouse | `dialect="clickhouse"` | HTTP (port 8123) | `clickhouse-connect` |
| Materialize | `dialect="postgres"` | PG wire (port 6875) | `asyncpg` |
| PostgreSQL | `dialect="postgres"` | PG wire (port 5432) | `asyncpg` via SQLAlchemy |
| Redis | N/A (key-value) | Redis protocol | `redis-py` |

---

## Access Patterns

- **Read-only**: The app NEVER writes to ClickHouse, Materialize, or Redis serving data. These stores are populated by the data pipeline (separate workstream).
- **Parameterized queries**: All user-supplied values are parameterized via SQLGlot — never string-concatenated.
- **Tenant isolation on shared data**: Serving-layer tables have no `tenant_id` column. Isolation is via symbol-based ACL injected at the compiler level (`WHERE symbol IN (:allowed_symbols)`).
