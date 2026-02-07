"""Materialize async client via PG wire protocol (asyncpg).

Read-only — this application never writes to Materialize.
Used for live data queries dispatched by the query router.

Falls back to mock data in development when Materialize is unreachable.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field

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

    _pool: asyncpg.Pool | None = field(default=None, init=False, repr=False)

    async def create_pool(self) -> None:
        """Create an asyncpg connection pool for SUBSCRIBE and queries."""
        try:
            self._pool = await asyncpg.create_pool(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password,
                min_size=settings.materialize_pool_min_size,
                max_size=settings.materialize_pool_max_size,
            )
            logger.info("materialize_pool_created")
        except Exception as exc:
            if settings.app_env == "development":
                logger.info("materialize_pool_creation_failed_dev", reason=str(exc))
                self._pool = None
            else:
                raise

    async def close_pool(self) -> None:
        """Close the connection pool."""
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
            logger.info("materialize_pool_closed")

    async def execute(self, query: str, params: list | None = None) -> list[dict]:
        """Execute a read-only query and return rows as dicts."""
        try:
            if self._pool is not None:
                async with self._pool.acquire() as conn:
                    rows = await conn.fetch(query, *(params or []))
                    return [dict(row) for row in rows]
            # Fallback to single connection if pool not initialized
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

    async def subscribe(
        self, view_name: str, *, snapshot: bool = False
    ) -> AsyncIterator[tuple[int, int, dict]]:
        """Run SUBSCRIBE TO <view> and yield (mz_timestamp, mz_diff, row) tuples.

        Uses a dedicated connection from the pool. The caller is responsible
        for breaking out of the iterator to release the connection.

        Args:
            view_name: The materialized view to subscribe to.
            snapshot: Whether to include the initial snapshot.
        """
        if self._pool is None:
            raise RuntimeError("Materialize pool not initialized")

        conn: asyncpg.Connection = await self._pool.acquire()
        try:
            snapshot_opt = "true" if snapshot else "false"
            stmt = f"SUBSCRIBE TO {view_name} WITH (SNAPSHOT = {snapshot_opt})"
            # Use a server-side cursor for streaming
            async with conn.transaction():
                async for record in conn.cursor(stmt):
                    row_dict = dict(record)
                    mz_timestamp = row_dict.pop("mz_timestamp", 0)
                    mz_diff = row_dict.pop("mz_diff", 1)
                    yield (int(mz_timestamp), int(mz_diff), row_dict)
        finally:
            await self._pool.release(conn)

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
