# ADR 0014: Production Configuration Safety Guards

- **Status:** Accepted
- **Date:** 2026-02-11
- **Deciders:** Security audit team

## Context

The `Settings` class (`backend/app/core/config.py`) used
`secret_key: str = "dev-secret-change-in-prod"` as a default. When
`VITE_DEV_AUTH=true`, authentication is bypassed entirely using the dev
secret. If the application deployed to staging or production without an
explicit `SECRET_KEY` environment variable, it would run with auth bypass
enabled — granting any request full access to every tenant.

This is a class of vulnerability where insecure development defaults
silently carry over to production because nothing enforces the boundary.

## Decision

Add a Pydantic `@model_validator(mode="after")` to `Settings` that refuses
to start the application when dev defaults are detected outside the
`development` environment:

```python
@model_validator(mode="after")
def _validate_production_settings(self) -> "Settings":
    is_prod = self.app_env != "development"
    has_dev_secret = self.secret_key == "dev-secret-change-in-prod"
    if is_prod and has_dev_secret:
        raise ValueError(
            f"SECRET_KEY must be set when APP_ENV={self.app_env!r}. "
            "The default dev secret is not allowed outside development."
        )
    return self
```

The check runs at import time when FastAPI instantiates `Settings`. A
missing or default secret key crashes the process before it binds to a port,
making misconfiguration impossible to miss.

Implemented in `backend/app/core/config.py`.

## Alternatives Considered

- **CI lint checking `.env` files** — only catches committed env files; does
  not protect against missing variables in container orchestration.
- **Terraform validation on Secret Manager values** — shifts responsibility
  to infra; the application itself should be self-defending.
- **Runtime middleware that rejects requests** — the server would still
  start and pass health checks, potentially serving traffic before the
  middleware triggers.

## Consequences

**Positive:**
- Fail-fast: misconfigured deployments crash immediately with a clear error
  message instead of silently running with auth bypass.
- Zero runtime overhead — validation runs once at startup.
- Pattern extends naturally to other sensitive defaults (database URLs,
  API keys) by adding checks to the same validator.

**Negative:**
- Local development requires `APP_ENV=development` (already the default in
  `backend/.env`). Developers who unset it will see a startup error — the
  error message explains the fix.
