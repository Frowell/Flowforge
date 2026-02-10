# 0001: Use SQLGlot for Query Compilation Instead of DataFrames

**Status:** Accepted
**Date:** 2025-10-01
**Deciders:** Architecture team

## Context

FlowForge compiles visual canvas workflows into executable queries against ClickHouse, Materialize, and Redis. The two main approaches were:

1. **DataFrame execution** (Pandas/Polars) — pull data into Python, transform in memory, return results
2. **SQL compilation** (SQLGlot) — translate the canvas DAG into SQL, push execution to the backing store

The canvas supports 17+ node types (filter, join, group_by, pivot, window functions, etc.) that must compose arbitrarily.

## Decision

Use **SQLGlot** to compile canvas workflows into SQL. Pandas/Polars are only used for formatting preview results and test fixtures — never for query execution.

SQLGlot provides:
- AST-based SQL generation with dialect-specific output (ClickHouse, PostgreSQL)
- Parameterized value injection (prevents SQL injection without string concatenation)
- Composable expression trees that map naturally to the canvas DAG
- Query merging: adjacent compatible nodes (Filter -> Select -> Sort) collapse into a single SQL query

## Alternatives Considered

**Pandas/Polars DataFrames**: Simpler to implement initially, but doesn't scale. Pulling millions of rows from ClickHouse into Python memory defeats the purpose of an analytical database. Also prevents query merging — each node would be a separate roundtrip.

**Raw SQL string templates**: Faster to prototype but impossible to merge queries, prone to SQL injection, and painful to maintain across dialects.

**SQLAlchemy Core expressions**: Viable but lacks ClickHouse dialect support and the AST manipulation capabilities needed for query merging.

## Consequences

- **Positive**: Queries execute where the data lives (ClickHouse). Preview of 100 rows from a billion-row table scans only what's needed. Query merging reduces roundtrips.
- **Positive**: SQL injection is structurally prevented — values are always parameterized through the AST.
- **Negative**: SQLGlot has a learning curve. Contributors must understand AST manipulation, not just SQL strings.
- **Negative**: Some node types (e.g., Formula with complex expressions) require careful AST construction.
