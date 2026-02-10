# 0002: Multi-Tenant Architecture from Day One

**Status:** Accepted
**Date:** 2025-10-01
**Deciders:** Architecture team

## Context

FlowForge needed to decide between single-tenant (one deployment per customer) and multi-tenant (shared deployment, data isolation via `tenant_id`). The application stores workflow metadata in PostgreSQL and queries analytical data from ClickHouse/Materialize/Redis.

## Decision

Multi-tenant from day one. Every tenant-scoped resource is isolated by a `tenant_id` UUID column. Tenant identity is derived exclusively from Keycloak JWT claims — never from client-supplied headers, URL parameters, or query strings.

Key rules:
- Every PostgreSQL query on tenant-scoped tables includes `WHERE tenant_id = :tenant_id`
- Missing tenant filter = security bug
- Cross-tenant access returns 404 (not 403) to prevent tenant enumeration
- Cache keys (Redis) include `tenant_id`
- WebSocket channels are tenant-scoped on the backend

## Alternatives Considered

**Single-tenant per deployment**: Simpler isolation but dramatically increases operational cost. Each customer would need their own infrastructure stack.

**Schema-per-tenant (PostgreSQL schemas)**: Strong isolation but complicates migrations — every schema must be migrated independently. Doesn't work for ClickHouse/Materialize which don't have equivalent schema isolation.

**Row-level security (PostgreSQL RLS)**: Considered as an additional layer but not used as the primary mechanism. Application-level filtering is more explicit and easier to test. RLS could be added later as defense-in-depth.

## Consequences

- **Positive**: Single deployment serves all tenants. Lower operational overhead.
- **Positive**: Tenant isolation is explicit in code and testable — every service method takes `tenant_id` as a parameter.
- **Negative**: Every query, cache key, and WebSocket channel must be tenant-aware. Missing a filter is a data leak.
- **Negative**: Cross-tenant queries (admin analytics across all tenants) require special handling.
