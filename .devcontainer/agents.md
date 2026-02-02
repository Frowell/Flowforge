# DevContainer — Agent Rules

> Parent rules: [`/workspace/agents.md`](../agents.md) | Architecture: [`/workspace/planning.md`](../planning.md)

## Current Services

| Service | Image | Purpose |
|---|---|---|
| `app` | Python 3.12 + Node 22 | Application runtime (backend + frontend dev servers) |
| `db` | PostgreSQL 16 | App metadata (workflows, dashboards, widgets, users) |
| `redis` | Redis 7 | Cache (schema registry), pub/sub (WebSocket fan-out) |
| `pgadmin` | pgAdmin (optional) | Database administration UI |

## Services Not Yet Added

- **ClickHouse** and **Materialize** are not yet in the devcontainer.
- All code that interacts with these services **must be mockable** — services should accept injected clients that can be replaced with test doubles.
- Tests must never require running ClickHouse or Materialize instances.

## Environment Variables

- Defined in `docker-compose.yml` and passed to the `app` service.
- Consumed via `pydantic-settings` `Settings` class in `backend/app/core/config.py`.
- **Never** hardcode connection strings, ports, or credentials in application code.

### Keycloak Tenant Configuration

- When Keycloak is added to the devcontainer, the realm must be configured to include a `tenant_id` custom claim in JWT tokens (via a Keycloak protocol mapper).
- Dev seed data should create at least two tenants with sample users, workflows, and dashboards in each to enable cross-tenant isolation testing.
- The development Keycloak realm export should be version-controlled in `.devcontainer/keycloak/` for reproducible setups.

## Adding a New Service

When adding a new backing service (e.g., ClickHouse):

1. Add the service to `docker-compose.yml` with appropriate image, ports, and volumes.
2. Add connection environment variables to the `app` service's `environment` block.
3. Add corresponding fields to the `Settings` class in `backend/app/core/config.py`.
4. Create an async client wrapper in `backend/app/core/` (e.g., `clickhouse.py`).
5. Add seed data or initialization to `post-create.sh` if needed.
6. Update this file to document the new service.
