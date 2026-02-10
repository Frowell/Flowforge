# RFC 0002: Sub-200ms Live Dashboard Updates via WebSocket Row Push

**Status:** Accepted
**Author:** Architecture team
**Date:** 2026-02-10

## Summary

Replace the notification-based invalidate-and-refetch pattern for live dashboard updates with a row-level WebSocket push architecture that achieves sub-200ms end-to-end latency.

## Motivation

Live dashboard widgets showed 1-5 second update latency despite the pipeline generating data continuously. Two bottlenecks:

1. **Batch accumulation (~0.8-5s)**: The raw sink Bytewax flow waited for 50 records before flushing. At 10 trades/s + 50 quotes/s, this took 0.8s-5s depending on topic balance.
2. **Invalidate-and-refetch (~200-500ms)**: Each flush triggered a notification, which caused the frontend to invalidate its TanStack Query cache and do a full HTTP round trip (compile SQL → query ClickHouse → serialize → return all rows).

For a trading dashboard, 1-5 seconds is unacceptable. Market conditions change in milliseconds; a 5-second delay means traders see stale data.

## Detailed Design

### 1. Time-Based Flush in raw_sink

**File:** `pipeline/bytewax/flows/raw_sink.py`

Add `FLUSH_INTERVAL = 0.2` (200ms). Track `last_flush` timestamps. Flush when either condition is met:

```
len(buffer) >= BATCH_SIZE  OR  (len(buffer) > 0 AND elapsed > FLUSH_INTERVAL)
```

This caps worst-case accumulation at 200ms regardless of throughput. At high throughput, the batch-size trigger fires first; at low throughput, the time trigger ensures freshness.

### 2. Row Data in Redis PUBLISH

**File:** `pipeline/bytewax/flows/raw_sink.py`

Replace notification-only messages with row-carrying messages:

```python
# Before (notification only)
{"type": "table_update", "table": "raw_trades"}

# After (includes actual rows)
{
    "type": "table_rows",
    "table": "raw_trades",
    "columns": [
        {"name": "trade_id", "dtype": "String"},
        {"name": "symbol", "dtype": "String"},
        {"name": "price", "dtype": "Float64"},
        ...
    ],
    "rows": [
        {"trade_id": "abc-123", "symbol": "AAPL", "price": 185.42, ...},
        ...
    ]
}
```

Column metadata is defined as module-level constants (`TRADE_COLUMNS`, `QUOTE_COLUMNS`) — no per-message schema discovery.

The same pattern applies to the VWAP and volatility flows, which also broadcast via Redis PUBLISH when they write to Redis hashes.

### 3. Frontend Cache Merge

**File:** `frontend/src/features/dashboards/hooks/useWidgetData.ts`

Replace `queryClient.invalidateQueries()` with `queryClient.setQueryData()`:

```typescript
// On receiving table_rows message via WebSocket:
queryClient.setQueryData(queryKey, (old: WidgetDataResponse | undefined) => {
    if (!old) return old;
    // Only merge on page 0 — other pages stay stable
    if (offset !== 0) return old;

    const filtered = applyClientFilters(msg.rows, activeFilters);
    if (filtered.length === 0) return old;

    const merged = [...filtered, ...old.rows].slice(0, limit);
    return {
        ...old,
        rows: merged,
        total_rows: old.total_rows + filtered.length,
    };
});
```

Key behaviors:
- **Page 0 only**: Only the first page of results gets live updates. Paginated pages remain stable.
- **Client-side filter matching**: `applyClientFilters()` checks `equals` and `in` filter types against the pushed rows. Rows that don't match the widget's active filters are discarded.
- **Bounded growth**: After prepending new rows, the array is sliced to `limit` to prevent unbounded memory growth.
- **total_rows increment**: The count is incremented by the number of new matching rows so pagination controls stay accurate.

### 4. Consistency Backstop

A 30-second `refetchInterval` on live-mode widgets (`auto_refresh_interval: -1`) periodically re-queries the full result set from ClickHouse. This corrects any drift from:
- Missed WebSocket messages (brief disconnection)
- Approximate client-side filtering (complex filter types not handled)
- Count divergence from concurrent page navigation

### 5. No Backend Changes Required

The WebSocket manager already broadcasts any message matching the `:broadcast:` channel pattern. The raw sink publishes to `flowforge:broadcast:table_rows` (previously `flowforge:broadcast:table_update`). No changes to `websocket_manager.py` routing logic.

## Latency Analysis

| Step | Before | After |
|------|--------|-------|
| Batch accumulation | 0.8-5s | 200ms max |
| Redis PUBLISH | ~1ms | ~1ms |
| WebSocket delivery | ~1ms | ~1ms |
| Frontend update | 200-500ms (HTTP round trip) | ~5ms (in-memory merge) |
| **Total** | **1-5.5s** | **~210ms** |

## Message Size Analysis

At 200ms flush intervals with 10 trades/s + 50 quotes/s:
- Trade batch: ~2-10 records per flush → 0.5-2KB JSON
- Quote batch: ~10-25 records per flush → 1-4KB JSON
- Redis PUBLISH overhead: negligible at this message size
- WebSocket frame overhead: 2-14 bytes per frame header

## Alternatives Considered

See ADR 0010 for the full alternatives analysis.

## Open Questions

*All resolved during implementation:*

- ~~Should client-side filtering handle all filter types?~~ No — `equals` and `in` cover 90% of live dashboard use cases. The 30s backstop handles edge cases.
- ~~Should the binary protocol be used for row data?~~ No — JSON payloads are small enough that serialization overhead is negligible. Revisit if throughput increases 10x.
- ~~Should we push only to widgets that match the table?~~ Yes — the frontend checks `msg.table` against the widget's data source table before merging.

## Implementation

Delivered across two PRs:

- **PR #33** (`feat(pipeline): add raw sink with live WebSocket updates`) — raw_sink flow, WebSocket manager broadcast, initial notification-based updates
- **PR #37** (`feat(live): sub-200ms dashboard updates via WebSocket row push`) — time-based flush, row data in PUBLISH, cache merge, client-side filtering, backstop refetch
- **PR #38** (`feat(query): route Redis/Materialize data sources and format cell values`) — multi-target query routing, positions pipeline, cell formatting

Key decisions recorded in:
- [ADR 0009: Table-Name Pattern Routing](../decisions/0009-table-name-pattern-routing.md)
- [ADR 0010: WebSocket Row Push with Client-Side Cache Merge](../decisions/0010-websocket-row-push.md)
