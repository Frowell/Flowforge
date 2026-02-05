"""Materialize async client via PG wire protocol (asyncpg).

Read-only — this application never writes to Materialize.
Used for live data queries dispatched by the query router.

NOTE: Materialize is not yet in the devcontainer. All code using this
client must be mockable for testing.
"""

from dataclasses import dataclass

import asyncpg  # type: ignore[import-untyped]

from app.core.config import settings


@dataclass
class MaterializeClient:
    """Async Materialize client via PG wire protocol.

    Materialize speaks the PostgreSQL wire protocol, so we use asyncpg
    for connections. All queries are read-only.
    """

    host: str
    port: int
    database: str
    user: str
    password: str

    async def execute(self, query: str, params: list | None = None) -> list[dict]:
        """Execute a read-only query and return rows as dicts."""
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

    async def ping(self) -> bool:
        """Health check."""
        try:
            await self.execute("SELECT 1")
            return True
        except Exception:
            return False


def get_materialize_client() -> MaterializeClient:
    return MaterializeClient(
        host=settings.materialize_host,
        port=settings.materialize_port,
        database=settings.materialize_database,
        user=settings.materialize_user,
        password=settings.materialize_password,
    )
