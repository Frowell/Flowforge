# Alembic Migrations — Agent Rules

> Parent rules: [`/workspace/backend/agents.md`](../agents.md)

## Generating Migrations

- Generate via `make migrate-new` (or `alembic revision --autogenerate -m "description"`).
- **Never** hand-edit DDL or write raw SQL in migration files unless autogenerate cannot handle the change.

## Migration Requirements

- Every migration must include both `upgrade()` and `downgrade()` functions.
- Use descriptive revision messages: `"add widget config_overrides column"`, not `"update"`.
- Test both upgrade and downgrade paths.

## Scope

- Migrations apply to **PostgreSQL only** — application metadata tables.
- Never write migrations for ClickHouse, Materialize, or Redis.

## Adding New Models

When adding a new SQLAlchemy model:

1. Create the model in `app/models/`.
2. Import the model in `alembic/env.py` so autogenerate detects it.
3. Run `make migrate-new` to generate the migration.
4. Review the generated migration for correctness.
5. Apply with `make migrate-up`.

## Multi-Tenancy Migration Rules

- All tenant-scoped tables (`users`, `workflows`, `dashboards`, `api_keys`) MUST have a `tenant_id UUID NOT NULL` column.
- Every `tenant_id` column MUST have an index (for query performance on filtered reads).
- Consider composite indexes on `(tenant_id, id)` or `(tenant_id, created_at)` for common query patterns.
- When adding `tenant_id` to existing tables, the migration must provide a default value for existing rows or use a data migration to backfill.
- Child tables that inherit tenant scope from a parent (`widgets` via `dashboards`, `dashboard_filters` via `dashboards`) do NOT get their own `tenant_id` column.
- PostgreSQL Row-Level Security (RLS) policies should be added as a defense-in-depth backstop: `CREATE POLICY tenant_isolation ON <table> USING (tenant_id = current_setting('app.current_tenant')::uuid)`. These are safety nets — the application layer is the primary enforcement mechanism.
