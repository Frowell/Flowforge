# Core Infrastructure — Agent Rules

> Parent rules: [`/workspace/backend/agents.md`](../../agents.md)

## Purpose

This directory contains foundational infrastructure code: configuration, database connections, authentication, external store clients, observability, and middleware. Everything here is consumed by `services/` and `api/routes/` — it does NOT contain business logic.

## File Catalog

| File | Responsibility | External Dependency |
|------|---------------|---------------------|
| `config.py` | `pydantic-settings` Settings singleton | Environment variables |
| `database.py` | Async SQLAlchemy engine, session factory, `TenantMixin` | PostgreSQL |
| `auth.py` | Keycloak OIDC JWT validation, API key validation, dev bypass | Keycloak, PostgreSQL |
| `clickhouse.py` | ClickHouse async HTTP client | ClickHouse (port 8123) |
| `materialize.py` | Materialize asyncpg connection pool + `subscribe()` | Materialize (port 6875) |
| `redis.py` | Redis async client | Redis |
| `logging_config.py` | structlog configuration (JSON in prod, console in dev) | None |
| `metrics.py` | Prometheus metrics registry (`flowforge_*` prefix) | None |
| `middleware.py` | `ObservabilityMiddleware` (request IDs, HTTP metrics) | None |

## Configuration Rules

- **All config via `pydantic-settings`** — the `Settings` class in `config.py` is the single source of truth.
- **Never use `os.getenv()` directly** — always access `settings.<field>`.
- Defaults are development-safe values only. Production values come from environment variables (injected via K8s ConfigMaps or Secret Manager).
- The `Settings` singleton is imported as `from app.core.config import settings`.

## Database & TenantMixin

- `database.py` defines the async SQLAlchemy engine (`create_async_engine`) and session factory (`async_sessionmaker`).
- `TenantMixin` provides a `tenant_id: Mapped[UUID]` column (NOT NULL, indexed) for all tenant-scoped models.
- `get_db()` dependency yields an `AsyncSession` with automatic rollback on error.

## Authentication

Three auth modes, checked in order:

1. **Dev bypass** (`APP_ENV=development`): If no token or `"dev-token"` header, return hardcoded dev user/tenant. **MUST be disabled in production.**
2. **Keycloak OIDC**: Validate JWT against JWKS endpoint, extract `sub` (user ID) and `tenant_id` claim. Used by Canvas and Dashboard routes.
3. **API key**: SHA256 hash lookup in `api_keys` table. Returns tenant_id and scoped widget IDs. Used by Embed routes.

Key functions:
- `get_current_user_id(request) → UUID` — for `created_by`, audit logging
- `get_current_tenant_id(request) → UUID` — for ALL data filtering (**CRITICAL**)
- `get_current_user_claims(request) → dict` — for role checks
- `validate_api_key(key, db) → dict` — for embed auth

## External Store Clients

All clients connect to **read-only** data stores. FlowForge never writes to ClickHouse, Materialize, or Redis data tables.

| Client | Protocol | Port | Connection Pattern |
|--------|----------|------|--------------------|
| ClickHouse | HTTP | 8123 | `clickhouse-connect`, per-request |
| Materialize | PG wire | 6875 | `asyncpg.create_pool()`, pooled, supports `SUBSCRIBE` |
| Redis | Redis protocol | 6379 | `redis.asyncio`, singleton |

### Materialize Pool Lifecycle

- Pool initialized in `app/main.py` lifespan `startup`
- Pool closed in lifespan `shutdown`
- `subscribe(view_name)` runs `SUBSCRIBE TO <view> WITH (SNAPSHOT = false)` and yields `(mz_timestamp, mz_diff, row)` tuples
- Pool may fail to initialize in dev (Materialize is optional via `streaming` profile) — handle gracefully

## Observability

- **structlog**: Async-safe per-request context via `contextvars` (`request_id`, `tenant_id`, `user_id`). JSON output in production, colored console in development.
- **Prometheus**: All metrics defined centrally in `metrics.py` with `flowforge_` prefix. Scraped via `GET /metrics`.
- **Middleware**: `ObservabilityMiddleware` generates a UUID4 `request_id` per HTTP request, binds it to structlog context, returns it as `X-Request-ID` response header, and records HTTP metrics (duration, status code).

## Rules

- **Never import from `services/` or `api/`** — this directory is a leaf dependency. Information flows upward: `core/ → services/ → api/routes/`.
- **Never store business logic here** — auth token validation is infrastructure; role enforcement (`require_role()`) is defined here but applied in routes.
- **All clients must be async** — no synchronous I/O except Alembic migrations (which use `database_url_sync`).
- **No secrets in defaults** — `secret_key`, passwords, and client secrets default to empty or dev-only values.
