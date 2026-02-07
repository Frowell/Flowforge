# Admin Features — Agent Rules

> Parent rules: [`/workspace/frontend/agents.md`](../../../agents.md) | Architecture: [`/workspace/planning.md`](../../../../../planning.md)

## Purpose

Admin-only pages accessible to users with the `admin` role. Currently contains the audit log viewer.

## Pages

| Page               | Route          | Role  | Purpose                                    |
| ------------------ | -------------- | ----- | ------------------------------------------ |
| `AuditLogPage.tsx` | `/admin/audit` | admin | Queryable audit trail — who did what, when |

## Rules

- **Admin role required.** All routes in this directory require `admin` role. The router guards access; the backend enforces it via `require_role("admin")`.
- **Read-only views.** Admin pages display data but do not modify it (audit logs are append-only).
- **Standard patterns.** Use TanStack Query for data fetching, Tailwind for styling, same component patterns as the rest of the app.
- **No sensitive data in client.** Admin pages show metadata (who, what, when) but never display raw credentials, tokens, or secrets.
