"""Materialize async client via PG wire protocol (asyncpg).

Read-only — this application never writes to Materialize.
Used for live data queries dispatched by the query router.

Falls back to mock data in development when Materialize is unreachable.
"""

from dataclasses import dataclass

import asyncpg  # type: ignore[import-untyped]
import structlog

from app.core.config import settings

logger = structlog.stdlib.get_logger("flowforge.materialize")


@dataclass
class MaterializeClient:
    """Async Materialize client via PG wire protocol.

    Materialize speaks the PostgreSQL wire protocol, so we use asyncpg
    for connections. All queries are read-only.
    Falls back to empty results in development if unreachable.
    """

    host: str
    port: int
    database: str
    user: str
    password: str

    async def execute(self, query: str, params: list | None = None) -> list[dict]:
        """Execute a read-only query and return rows as dicts."""
        try:
            conn = await asyncpg.connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password,
            )
            try:
                rows = await conn.fetch(query, *(params or []))
                return [dict(row) for row in rows]
            finally:
                await conn.close()
        except Exception as exc:
            if settings.app_env == "development":
                logger.info(
                    "materialize_fallback_mock",
                    reason=str(exc),
                    query=query[:100],
                )
                return []
            raise

    async def ping(self) -> bool:
        """Health check."""
        try:
            await self.execute("SELECT 1")
            return True
        except Exception as exc:
            if settings.app_env == "development":
                logger.info("materialize_ping_failed_dev", reason=str(exc))
                return False
            return False


def get_materialize_client() -> MaterializeClient:
    return MaterializeClient(
        host=settings.materialize_host,
        port=settings.materialize_port,
        database=settings.materialize_database,
        user=settings.materialize_user,
        password=settings.materialize_password,
    )
