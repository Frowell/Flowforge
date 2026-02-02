"""ClickHouse async client.

Read-only — this application never writes to ClickHouse.
Used for analytical queries dispatched by the query router.

NOTE: ClickHouse is not yet in the devcontainer. All code using this
client must be mockable for testing.
"""

from dataclasses import dataclass

from app.core.config import settings


@dataclass
class ClickHouseClient:
    """Async ClickHouse client wrapper.

    Provides a read-only interface to ClickHouse for:
    - Analytical queries compiled by the workflow compiler
    - Schema discovery from system.columns
    """

    host: str
    port: int
    database: str
    user: str
    password: str

    async def execute(self, query: str, params: dict | None = None) -> list[dict]:
        """Execute a read-only query and return rows as dicts.

        All queries must be built via SQLGlot — never string concatenation.
        """
        # TODO: Implement with asynch or clickhouse-connect
        raise NotImplementedError("ClickHouse client not yet implemented")

    async def fetch_schema(self, table: str) -> list[dict]:
        """Fetch column metadata from system.columns for a given table."""
        query = (
            "SELECT name, type, comment "
            "FROM system.columns "
            "WHERE database = {database:String} AND table = {table:String}"
        )
        return await self.execute(query, {"database": self.database, "table": table})

    async def ping(self) -> bool:
        """Health check."""
        try:
            await self.execute("SELECT 1")
            return True
        except Exception:
            return False


def get_clickhouse_client() -> ClickHouseClient:
    return ClickHouseClient(
        host=settings.clickhouse_host,
        port=settings.clickhouse_port,
        database=settings.clickhouse_database,
        user=settings.clickhouse_user,
        password=settings.clickhouse_password,
    )
