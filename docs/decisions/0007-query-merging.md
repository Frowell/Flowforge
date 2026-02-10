# 0007: Mandatory Query Merging for Adjacent Compatible Nodes

**Status:** Accepted
**Date:** 2025-11-01
**Deciders:** Architecture team

## Context

A typical canvas workflow has sequences of compatible SQL operations: Filter -> Select -> Sort, or Filter -> GroupBy -> Sort. Without optimization, each node would generate a separate query, and the system would execute them sequentially with intermediate result materialization.

## Decision

**Query merging is mandatory.** The workflow compiler identifies sequences of adjacent nodes that can be expressed as a single SQL query and merges them. For example:

- `Filter -> Select -> Sort` = one `SELECT ... WHERE ... ORDER BY` query
- `Filter -> GroupBy -> Sort` = one `SELECT ... WHERE ... GROUP BY ... ORDER BY` query

The merge boundary is defined by node type compatibility. Nodes that change the query structure (Join, Union) or require separate execution (output nodes) break the merge chain.

## Alternatives Considered

**No merging (one query per node)**: Simplest to implement but generates unnecessary roundtrips. A 5-node linear workflow would execute 5 queries instead of 1. ClickHouse is fast but not free — network overhead and query planning add up.

**Optional merging (optimization hint)**: Let the compiler decide when to merge based on heuristics. Rejected because it makes behavior unpredictable — the same workflow could generate different numbers of queries depending on optimizer decisions, making debugging harder.

**CTE-based composition**: Express each node as a CTE (`WITH`), let the database optimizer merge them. ClickHouse's CTE optimization is limited compared to PostgreSQL, so this doesn't reliably reduce execution cost.

## Consequences

- **Positive**: Dramatically fewer queries. Most linear workflows compile to 1-3 queries regardless of node count.
- **Positive**: ClickHouse processes the entire pipeline in one pass, leveraging its columnar scan optimizations.
- **Negative**: The compiler must track merge state across nodes, adding complexity to `workflow_compiler.py`.
- **Negative**: Debugging compiled SQL is harder when multiple nodes are merged — a bug in the Sort merge logic looks like a Filter bug in the output.
