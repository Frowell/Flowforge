# WebSocket Manager — Agent Rules

> Parent rules: [`/workspace/frontend/src/shared/agents.md`](../../agents.md)

## Purpose

WebSocket connection manager for real-time execution status updates and live data streaming from the backend.

## File

| File         | Purpose                                                                          |
| ------------ | -------------------------------------------------------------------------------- |
| `manager.ts` | `WebSocketManager` class — connection lifecycle, message routing, auto-reconnect |

## Connection Lifecycle

```
1. connect()          → Open WebSocket to ws://<host>/ws/dashboard/<id>
2. subscribe(channel) → Send { action: "subscribe", channel } to server
3. onMessage(type, handler) → Register handler for message type
4. Auto-reconnect     → Exponential backoff on disconnect (max 10 attempts)
5. disconnect()       → Clean close, cancel reconnect timer
```

## Message Types

| Type               | Direction       | Payload                          | Use Case                              |
| ------------------ | --------------- | -------------------------------- | ------------------------------------- |
| `execution_status` | Server → Client | `{ node_id, status, progress }`  | Node status during workflow execution |
| `live_data`        | Server → Client | `{ view_name, rows, timestamp }` | Materialize SUBSCRIBE or poll results |
| `subscribe`        | Client → Server | `{ action, channel }`            | Subscribe to a Redis pub/sub channel  |
| `unsubscribe`      | Client → Server | `{ action, channel }`            | Unsubscribe from a channel            |

## Auto-Reconnect

- Exponential backoff: `min(1000 * 2^attempt, 30000)` ms
- Max 10 reconnect attempts before giving up
- On reconnect, re-subscribes to all previously subscribed channels
- Connection state change notifies all registered `ConnectionHandler` callbacks

## Multi-Tenancy

- WebSocket channels are tenant-scoped **on the backend** (Redis pub/sub channel names include `tenant_id`)
- The frontend does NOT pass tenant context explicitly — the backend derives it from the WebSocket connection's auth token
- Different tenants on the same backend instance receive only their own messages

## Integration with TanStack Query

Live data messages should trigger TanStack Query cache invalidation:

```typescript
// When live data arrives, invalidate the relevant query
wsManager.onMessage("live_data", (data) => {
  queryClient.invalidateQueries({ queryKey: ["widget-data", widgetId] });
});
```

## Rules

- **Single instance per session.** Do not create multiple WebSocketManager instances — use a singleton or React context.
- **No business logic in the manager.** The manager routes messages to handlers. Processing logic belongs in hooks or stores.
- **Graceful degradation.** If WebSocket fails to connect, the app falls back to polling via TanStack Query's `refetchInterval`.
- **Clean up on unmount.** Components that subscribe to channels must unsubscribe in their cleanup/effect teardown.
