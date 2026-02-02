"""Application configuration via pydantic-settings.

All config is sourced from environment variables. Never use os.getenv() directly.
"""

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """FlowForge application settings.

    Environment variables are the single source of truth.
    Defaults are development-safe values only.
    """

    app_env: str = "development"
    secret_key: str = "dev-secret-change-in-prod"

    # PostgreSQL — app metadata only (workflows, dashboards, widgets, users)
    database_url: str = "postgresql+asyncpg://flowforge:flowforge@db:5432/flowforge"
    database_url_sync: str = "postgresql://flowforge:flowforge@db:5432/flowforge"

    # Redis — cache, pub/sub
    redis_url: str = "redis://redis:6379/0"

    # Keycloak — OIDC SSO authentication
    keycloak_url: str = "http://keycloak:8080"
    keycloak_realm: str = "flowforge"
    keycloak_client_id: str = "flowforge-app"
    keycloak_client_secret: str = ""

    # ClickHouse — analytical queries (read-only)
    clickhouse_host: str = "localhost"
    clickhouse_port: int = 8123
    clickhouse_database: str = "default"
    clickhouse_user: str = "default"
    clickhouse_password: str = ""

    # CORS
    cors_origins: list[str] = ["http://localhost:5173"]

    # Schema registry cache TTL (seconds)
    schema_cache_ttl: int = 300

    # Widget data cache TTLs (seconds)
    widget_cache_ttl_clickhouse: int = 300   # 5 min for analytical queries
    widget_cache_ttl_materialize: int = 30   # 30 sec for live data

    # Observability
    log_level: str = "INFO"
    metrics_enabled: bool = True

    # Dev-mode auth bypass (only used when app_env == "development" and no auth header)
    dev_user_id: str = "00000000-0000-0000-0000-000000000001"
    dev_tenant_id: str = "00000000-0000-0000-0000-000000000002"

    # Embed rate limiting
    embed_rate_limit_default: int = 100      # requests per second per API key
    embed_rate_limit_window: int = 1         # window size in seconds

    model_config = {"env_file": ".env"}

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            import json

            return json.loads(v)
        return v


settings = Settings()
