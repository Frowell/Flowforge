# 0004: Application Treats the Serving Layer as Read-Only

**Status:** Accepted
**Date:** 2025-10-01
**Deciders:** Architecture team

## Context

FlowForge queries data from ClickHouse, Materialize, and Redis. A separate data pipeline (Redpanda, Bytewax, dbt, Airflow) populates these stores. The question was whether the application should also write to the serving layer — e.g., creating materialized views, inserting computed results, or managing table schemas.

## Decision

The application treats the serving layer as **strictly read-only**. No DDL, INSERT, CREATE VIEW, or any write operation against ClickHouse, Materialize, or Redis (except cache writes to Redis for preview results).

The serving layer contract is defined by table schemas that the pipeline maintains. The application reads from whatever the pipeline produces. The pipeline can be replaced, extended, or swapped out without changing the application — as long as the contract is maintained.

## Alternatives Considered

**Application-managed materialized views**: The app could create Materialize views on demand based on user workflows. This would allow truly custom real-time computations. Rejected because it couples the app to Materialize's lifecycle, makes the app responsible for view cleanup, and creates a blast radius where a bad user query could impact the shared Materialize cluster.

**Write-through cache**: The app could write computed results back to ClickHouse for reuse. Rejected because it violates the clean separation between pipeline (writes) and application (reads), and complicates cache invalidation.

## Consequences

- **Positive**: Clean architectural boundary. The pipeline team and app team can work independently.
- **Positive**: The app cannot corrupt the serving layer. Bad queries fail; they don't write bad data.
- **Positive**: The pipeline can be replaced entirely (e.g., swap Bytewax for Flink) without touching the app.
- **Negative**: The app cannot create custom materialized views for user workflows. All real-time views must be pre-defined by the pipeline.
- **Negative**: Preview result caching uses Redis (a write), which is the one exception to the read-only rule.
