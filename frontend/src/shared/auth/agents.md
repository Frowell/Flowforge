# Authentication — Agent Rules

> Parent rules: [`/workspace/frontend/src/shared/agents.md`](../../agents.md) | Architecture: [`/workspace/planning.md`](../../../../../../planning.md)

## Purpose

Keycloak OIDC authentication adapter for Canvas and Dashboard routes. Embed routes use API key auth (handled separately via URL params in `features/embed/`).

## File

| File          | Purpose                                                                        |
| ------------- | ------------------------------------------------------------------------------ |
| `keycloak.ts` | Keycloak OIDC adapter — init, login, logout, token management, user extraction |

## Key Exports

| Function           | Returns            | Purpose                                                       |
| ------------------ | ------------------ | ------------------------------------------------------------- |
| `initKeycloak()`   | `Promise<boolean>` | Initialize OIDC — call once at app startup                    |
| `getCurrentUser()` | `CurrentUser`      | Extract user from JWT: `{ id, tenantId, email, name, roles }` |
| `getAccessToken()` | `Promise<string>`  | Get Bearer token for API requests                             |
| `logout()`         | `void`             | End session and redirect to Keycloak logout                   |
| `hasRole(role)`    | `boolean`          | Check if current user has a specific role                     |

## CurrentUser Interface

```typescript
interface CurrentUser {
  id: string; // Keycloak subject (sub claim)
  tenantId: string; // Custom JWT claim — CRITICAL for multi-tenancy
  email: string;
  name: string;
  roles: string[]; // ["admin"], ["analyst"], ["viewer"], etc.
}
```

## Dev Mode Bypass

When `VITE_DEV_AUTH=true` (set in `frontend/.env`), Keycloak is bypassed entirely:

- `initKeycloak()` returns `true` immediately without contacting Keycloak
- `getCurrentUser()` returns a hardcoded dev user with all roles
- `getAccessToken()` returns `"dev-token"` — the backend recognizes this in dev mode

**VITE_DEV_AUTH must be `false` in production.** The backend rejects dev tokens when `APP_ENV != "development"`.

## Multi-Tenancy

- The Keycloak JWT contains a `tenant_id` custom claim (configured via Keycloak protocol mapper)
- The frontend does NOT send `tenant_id` as a separate header or query parameter
- The backend extracts `tenant_id` from the `Authorization: Bearer` token on every request
- All TanStack Query cache keys are implicitly tenant-scoped (the backend only returns the authenticated tenant's data)
- Tenant switching requires re-authentication through Keycloak

## Rules

- **Never store tokens in localStorage/sessionStorage manually** — Keycloak JS adapter manages token storage and refresh.
- **Never expose `tenantId` in URL paths or query params** for authenticated routes — it comes from the JWT.
- **API client injects tokens** — `shared/query-engine/client.ts` calls `getAccessToken()` automatically. Components never handle tokens directly.
- **Role checks are advisory on the frontend** — the backend enforces roles via `require_role()`. Frontend role checks only control UI visibility (hiding buttons, routes).
