# 0010: WebSocket Row Push with Client-Side Cache Merge

**Status:** Accepted
**Date:** 2026-02-10
**Deciders:** Architecture team

## Context

Live dashboard updates previously used an invalidate-and-refetch pattern:

1. Pipeline batch-flushes data to ClickHouse (triggered every 50 records, ~1-5s)
2. Pipeline publishes a notification-only message to Redis pub/sub: `{ type: "table_update", table: "raw_trades" }`
3. Backend WebSocket manager forwards the notification to all connected dashboard clients
4. Frontend receives notification, calls `queryClient.invalidateQueries()` on matching widget queries
5. TanStack Query refetches: compiles SQL, queries ClickHouse, returns all rows over HTTP

This produced 1-5.5 seconds of end-to-end latency — too slow for a live trading dashboard. The bottlenecks were batch accumulation (count-based, no time limit) and the full HTTP round trip per update.

## Decision

Replace the invalidate-and-refetch pattern with **WebSocket row push and client-side cache merge**:

1. **Time-based flush**: The raw sink Bytewax flow flushes every 200ms OR at 50 records, whichever comes first. This caps batch accumulation at 200ms regardless of throughput.

2. **Row data in PUBLISH**: The Redis PUBLISH message includes the actual rows, not just a notification:
   ```json
   { "type": "table_rows", "table": "raw_trades", "columns": [...], "rows": [...] }
   ```

3. **Cache merge on the frontend**: Instead of `invalidateQueries()`, the frontend uses `queryClient.setQueryData()` to prepend new rows directly into the existing TanStack Query cache. No HTTP round trip.

4. **Client-side filter matching**: Live-mode widgets apply `equals`/`in` filters client-side to determine which pushed rows belong in the widget. This is approximate (doesn't cover all filter types) but correct for the common case (symbol/side filters).

5. **Consistency backstop**: A 30-second `refetchInterval` on live-mode widgets corrects any drift from approximate client-side filtering.

End-to-end latency: ~210ms (200ms flush + ~1ms Redis + ~1ms WebSocket + ~5ms render).

## Alternatives Considered

**Reduce batch size only**: Lowering the batch threshold from 50 to 5 records would reduce accumulation time but still require the full refetch round trip (~200-500ms). Combined latency would be 300-600ms.

**Server-side incremental query**: On notification, the backend queries only records newer than the client's last-seen timestamp and pushes the delta via WebSocket. Eliminated the client-side filtering problem but added backend complexity (tracking per-widget watermarks) and still required a ClickHouse query per update.

**Materialize SUBSCRIBE for all tables**: Use Materialize's built-in change streaming for raw_trades/raw_quotes. Would achieve sub-100ms latency but requires Materialize to maintain materialized views for high-volume raw tables — expensive at 60+ records/second per symbol.

**WebSocket binary protocol (Protobuf/MessagePack)**: More compact than JSON for row data. Rejected for now because JSON row payloads are small (0.5-2KB at 200ms flush intervals) and the complexity of a binary protocol isn't justified at current throughput.

## Consequences

- **Positive**: Sub-200ms end-to-end latency for live dashboard updates.
- **Positive**: No HTTP round trip per update — eliminates the refetch that was the largest latency contributor.
- **Positive**: ClickHouse load reduced — live widgets no longer re-query the entire result set on every pipeline flush.
- **Positive**: The 30-second backstop ensures eventual consistency even if the WebSocket push misses an update.
- **Negative**: Client-side filter matching is approximate. Filters beyond `equals`/`in` (e.g., regex, range) aren't applied client-side. The 30s backstop corrects this, but there's a brief window where a widget might show a row that doesn't match a complex filter.
- **Negative**: Redis PUBLISH messages are larger (include row data instead of just a table name). At current throughput (~60 records/s, 200ms flush), message size is 0.5-2KB — negligible for Redis.
- **Negative**: The pipeline must serialize row data to JSON for the PUBLISH message, adding ~1ms of serialization overhead per flush.
