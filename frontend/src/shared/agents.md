# Shared Frontend — Agent Rules

> Parent rules: [`/workspace/frontend/agents.md`](../../agents.md) | Architecture: [`/workspace/planning.md`](../../../../planning.md)

## Charts (`components/charts/`)

- **Single source of truth** — every chart component (BarChart, LineChart, Candlestick, ScatterPlot, KPICard, PivotTable) lives here and only here.
- Props interface: accept `data` + `config` as required props, with optional `interactive` (boolean) and `onDrillDown` (callback) props.
- **Responsive**: charts fill their container — never set fixed pixel dimensions. The parent (canvas preview, widget card, embed viewport) controls size.
- **No per-mode variants**: do not create `CanvasBarChart`, `DashboardBarChart`, `EmbedBarChart`. One component, used everywhere.
- Shared chart type definitions in `charts/types.ts`.

## Schema (`schema/`)

| File | Purpose |
|---|---|
| `registry.ts` | Schema catalog cache — wraps TanStack Query, fetches from `/api/v1/schema` |
| `propagation.ts` | Synchronous schema propagation engine — computes output schemas for entire DAG |
| `types.ts` | `ColumnSchema`, `TableSchema`, `NodeSchemaTransform` type definitions |

- `propagation.ts` must be synchronous and fast (< 10ms for 50 nodes).
- Must produce identical results to `backend/app/services/schema_engine.py`.
- `registry.ts` uses TanStack Query for caching/refetching — never stores schemas in Zustand.

## Query Engine (`query-engine/`)

| File | Purpose |
|---|---|
| `client.ts` | Single HTTP fetch wrapper with auth injection (session token or API key) |
| `types.ts` | Request/response type definitions matching backend Pydantic schemas |

- All API calls flow through this client.
- Components never call `fetch()` directly — they use TanStack Query hooks that use this client.
- Base URL and auth tokens injected from config/context.

## Auth (`auth/`)

- `keycloak.ts` — Keycloak OIDC adapter.
- `getCurrentUser()` returns `{ id, email, name, roles, tenantId }`. The `tenantId` is extracted from the JWT `tenant_id` claim.
- The `getAccessToken()` function returns the JWT bearer token. The backend extracts `tenant_id` from this token on every request — the frontend does NOT send tenant ID separately.
- Tenant isolation is enforced server-side. The frontend simply renders whatever data the backend returns for the authenticated tenant.

## WebSocket (`websocket/`)

- `manager.ts` — WebSocket connection manager.
- Auto-reconnect with exponential backoff on disconnect.
- Handles two message types:
  1. **Execution status**: pending → running → complete/error per node
  2. **Live data**: streaming results from Materialize-backed sources
- Redis pub/sub on the backend ensures messages reach the correct client regardless of which backend instance handles the WebSocket.
- WebSocket channels are tenant-scoped on the backend. The frontend does not need to pass tenant context explicitly — the backend derives it from the connection's auth token.
