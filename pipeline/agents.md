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

## Rules

- **No imports from `backend/app/`** — the pipeline is independent of the application.
- **No FlowForge dependencies** — pipeline components should only depend on their own requirements (Bytewax, dbt, etc.).
- **Schema stability** — table schemas should not change without updating the schema catalog that FlowForge reads from.
- **Bytewax API** — use Bytewax v0.21+ API (`bytewax.dataflow`, not legacy APIs).
- **dbt conventions** — staging models prefixed `stg_`, intermediate `int_`, marts `fct_`/`dim_`/`rpt_`.
