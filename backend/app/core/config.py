"""Application configuration via pydantic-settings.

All config is sourced from environment variables. Never use os.getenv() directly.
"""

import json

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """PostgreSQL configuration — app metadata only."""

    model_config = SettingsConfigDict(env_prefix="")

    database_url: str
    database_url_sync: str

    @field_validator("database_url", "database_url_sync")
    @classmethod
    def validate_database_url_not_empty(cls, v: str, info) -> str:
        if not v or not v.strip():
            raise ValueError(
                f"{info.field_name.upper()} must be set via environment variable. "
                "No default is provided for security reasons."
            )
        return v


class ClickHouseSettings(BaseSettings):
    """ClickHouse configuration — analytical queries (read-only)."""

    model_config = SettingsConfigDict(env_prefix="")

    clickhouse_host: str = "localhost"
    clickhouse_port: int = 8123
    clickhouse_database: str = "default"
    clickhouse_user: str = "default"
    clickhouse_password: str = ""
    # Used by schema discovery to enumerate databases for catalog.
    # Not used by workflow compiler — compiler uses table-level routing.
    clickhouse_databases: list[str] = ["flowforge", "metrics"]


class MaterializeSettings(BaseSettings):
    """Materialize configuration — live data queries (read-only, PG wire protocol)."""

    model_config = SettingsConfigDict(env_prefix="")

    materialize_host: str = "localhost"
    materialize_port: int = 6875
    materialize_database: str = "materialize"
    materialize_user: str = "materialize"
    materialize_password: str = ""
    materialize_subscribe_enabled: bool = True
    materialize_pool_min_size: int = 2
    materialize_pool_max_size: int = 10


class RedisSettings(BaseSettings):
    """Redis configuration — cache, pub/sub."""

    model_config = SettingsConfigDict(env_prefix="")

    redis_url: str = "redis://redis:6379/0"


class AuthSettings(BaseSettings):
    """Keycloak OIDC SSO authentication configuration."""

    model_config = SettingsConfigDict(env_prefix="")

    keycloak_url: str = "http://keycloak:8080"
    keycloak_realm: str = "flowforge"
    keycloak_client_id: str = "flowforge-app"
    keycloak_client_secret: str = ""


class PreviewSettings(BaseSettings):
    """Query execution and preview settings."""

    model_config = SettingsConfigDict(env_prefix="")

    # Schema registry cache TTL (seconds)
    schema_cache_ttl: int = 300

    # Widget data cache TTLs (seconds)
    widget_cache_ttl_clickhouse: int = 300  # 5 min for analytical queries
    widget_cache_ttl_materialize: int = 30  # 30 sec for live data

    # Query execution timeouts (seconds)
    clickhouse_query_timeout: int = 30  # max execution time for ClickHouse queries
    materialize_query_timeout: int = 10  # max execution time for Materialize queries


class Settings(BaseSettings):
    """FlowForge application settings.

    Environment variables are the single source of truth.
    Defaults are development-safe values only.
    """

    model_config = SettingsConfigDict(env_file=".env")

    app_env: str = "development"
    secret_key: str = "dev-secret-change-in-prod"

    @model_validator(mode="after")
    def _validate_production_settings(self) -> "Settings":
        """Refuse to start with dev defaults in non-development environments.

        Prevents accidental deployment with auth bypass enabled.
        """
        is_prod = self.app_env != "development"
        has_dev_secret = self.secret_key == "dev-secret-change-in-prod"
        if is_prod and has_dev_secret:
            raise ValueError(
                f"SECRET_KEY must be set when APP_ENV={self.app_env!r}. "
                "The default dev secret is not allowed outside development."
            )
        return self

    # Nested settings groups
    database: DatabaseSettings = DatabaseSettings()
    clickhouse: ClickHouseSettings = ClickHouseSettings()
    materialize: MaterializeSettings = MaterializeSettings()
    redis: RedisSettings = RedisSettings()
    auth: AuthSettings = AuthSettings()
    preview: PreviewSettings = PreviewSettings()

    # CORS
    cors_origins: list[str] = ["http://localhost:5173"]

    # Observability
    log_level: str = "INFO"
    metrics_enabled: bool = True

    # Dev-mode auth bypass (only used when app_env == "development" and no auth header)
    dev_user_id: str = "00000000-0000-0000-0000-000000000001"
    dev_tenant_id: str = "00000000-0000-0000-0000-000000000002"

    # Embed rate limiting
    embed_rate_limit_default: int = 100  # requests per second per API key
    embed_rate_limit_window: int = 1  # window size in seconds

    # Redis scan limits
    redis_scan_limit: int = 1000  # max keys to process in SCAN_HASH operations
    redis_pipeline_batch_size: int = 100  # batch size for pipelined HGETALL

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return json.loads(v)
        return v


settings = Settings()
