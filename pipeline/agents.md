# Pipeline — Agent Rules

> Parent rules: [`/workspace/agents.md`](../agents.md) | Serving layer: [`/workspace/docs/serving-layer.md`](../docs/serving-layer.md)

## Purpose

The data pipeline generates synthetic market data and transforms it into the serving layer that FlowForge reads from. This is a **separate workstream** from the main application — it populates ClickHouse, Materialize, and Redis with data that FlowForge queries.

## Critical Boundary

**FlowForge does NOT own this pipeline.** The application treats the serving layer as read-only. The pipeline can be replaced, extended, or swapped out without changing the application — as long as the serving layer contract is maintained.

## Component Catalog

| Directory | Component | Technology | Purpose |
|-----------|-----------|------------|---------|
| `generator/` | Data Generator | Python | Synthetic trades + quotes → Redpanda topics |
| `bytewax/flows/vwap.py` | VWAP Flow | Bytewax | 5-min VWAP windows → ClickHouse + Redis |
| `bytewax/flows/volatility.py` | Volatility Flow | Bytewax | Rolling 1h/24h volatility → ClickHouse + Redis |
| `bytewax/flows/positions.py` | Positions Flow | Bytewax | Net position per symbol → Redis |
| `bytewax/flows/raw_sink.py` | Raw Sink | Bytewax | Raw trades + quotes → ClickHouse + Redis broadcast |
| `bytewax/flows/anomaly.py` | Anomaly Flow | Bytewax | Spread/volume/price anomaly detection → alerts |
| `dbt/` | Batch Transforms | dbt | Staging → intermediate → mart models in ClickHouse |
| `airflow/` | Orchestration | Airflow | dbt DAG scheduling |

## Serving Layer Contract

The pipeline provides data to these stores that FlowForge reads:

| Store | Tables/Keys | Freshness |
|-------|-------------|-----------|
| ClickHouse | `raw_trades`, `raw_quotes`, `vwap_5min`, `rolling_volatility`, `hourly_rollup`, `daily_rollup`, `fct_trades`, `dim_instruments`, `rpt_daily_pnl` | Seconds to hours |
| Materialize | `live_positions`, `live_quotes`, `live_pnl` | Sub-second |
| Redis | `latest:vwap:*`, `latest:position:*` | Seconds |

## Live Update Path (Raw Sink → Dashboard WebSocket)

The raw sink flow connects the streaming pipeline to the FlowForge dashboard in real time:

```
Generator → Redpanda topics → raw_sink batch flush → ClickHouse INSERT
                                                    → Redis PUBLISH "flowforge:broadcast:table_update"
                                                         ↓
                                                    Backend WebSocket manager (catches :broadcast:)
                                                         ↓
                                                    ALL connected dashboard clients
                                                         ↓
                                                    useWidgetData invalidates → re-fetches from ClickHouse
```

- **Batch size**: 50 records per flush. At 10 trades/s + 50 quotes/s, updates fire roughly every 1-5 seconds.
- **Redis channel**: `flowforge:broadcast:table_update` — not tenant-scoped because the pipeline has no tenant context. The WebSocket manager broadcasts to all connected clients.
- **Frontend**: Widgets in "live" mode (`auto_refresh_interval: -1`) listen for `table_update` messages and invalidate their TanStack Query cache.

## Rules

- **No imports from `backend/app/`** — the pipeline is independent of the application.
- **No FlowForge dependencies** — pipeline components should only depend on their own requirements (Bytewax, dbt, etc.).
- **Schema stability** — table schemas should not change without updating the schema catalog that FlowForge reads from.
- **Bytewax API** — use Bytewax v0.21+ API (`bytewax.dataflow`, not legacy APIs).
- **dbt conventions** — staging models prefixed `stg_`, intermediate `int_`, marts `fct_`/`dim_`/`rpt_`.
