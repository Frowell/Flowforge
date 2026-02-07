# Query Engine (API Client) — Agent Rules

> Parent rules: [`/workspace/frontend/src/shared/agents.md`](../../agents.md) | Architecture: [`/workspace/planning.md`](../../../../../../planning.md)

## Purpose

Centralized HTTP client for all backend API communication. Handles auth token injection, error translation, and request/response serialization.

## File Catalog

| File        | Purpose                                                                  |
| ----------- | ------------------------------------------------------------------------ |
| `client.ts` | `APIClient` class — GET, POST, PATCH, DELETE with Bearer token injection |
| `types.ts`  | Request/response TypeScript types mirroring backend Pydantic schemas     |

## APIClient

The `APIClient` class wraps `fetch()` and:

1. **Injects auth** — calls `getAccessToken()` from `shared/auth/keycloak.ts` and sets `Authorization: Bearer <token>` on every request
2. **Serializes** — JSON-encodes request bodies, JSON-decodes responses
3. **Handles errors** — non-2xx responses throw structured errors with status code and detail message
4. **Supports cancellation** — `AbortSignal` parameter for cancellable requests (used by data preview)

All endpoints are prefixed with `/api/v1/`.

## Types

`types.ts` mirrors the backend Pydantic schemas:

| TypeScript Type   | Backend Schema      | Used By                |
| ----------------- | ------------------- | ---------------------- |
| `Workflow`        | `WorkflowResponse`  | Canvas, workflow hooks |
| `WorkflowCreate`  | `WorkflowCreate`    | Canvas save            |
| `Dashboard`       | `DashboardResponse` | Dashboard hooks        |
| `Widget`          | `WidgetResponse`    | Widget hooks           |
| `PreviewRequest`  | `PreviewRequest`    | Data preview           |
| `PreviewResponse` | `PreviewResponse`   | Data preview           |
| `TableSchema`     | `TableSchema`       | Schema registry        |

**Keep these in sync with the backend Pydantic schemas.** When a field is added to a backend schema, add it to the corresponding TypeScript type.

## Usage Pattern

Components never call `fetch()` or `APIClient` directly. They use TanStack Query hooks:

```typescript
// In a hook file (e.g., useWorkflow.ts)
import { apiClient } from "@/shared/query-engine/client";

export function useWorkflows() {
  return useQuery({
    queryKey: ["workflows"],
    queryFn: () => apiClient.get<WorkflowListResponse>("/api/v1/workflows"),
  });
}
```

## Rules

- **Never call `fetch()` in components** — always go through TanStack Query hooks that use `APIClient`.
- **Never store API responses in Zustand** — TanStack Query is the cache for server data.
- **Error handling** — API errors should propagate to TanStack Query's `onError`, which triggers toast notifications. Do not silently swallow errors.
- **Base URL from config** — the client reads `VITE_API_BASE_URL` or defaults to same-origin. Never hardcode `localhost:8000`.
- **Embed mode** — embed routes use API key auth instead of Bearer tokens. The client detects embed context and injects the API key as a query parameter.
