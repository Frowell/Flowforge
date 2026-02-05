"""ClickHouse async client.

Read-only — this application never writes to ClickHouse.
Used for analytical queries dispatched by the query router.

Uses clickhouse-connect for HTTP protocol queries.
Falls back to mock data in development when ClickHouse is unreachable.
"""

import random
from dataclasses import dataclass
from datetime import datetime, timedelta

import clickhouse_connect  # type: ignore[import-untyped]
import structlog

from app.core.config import settings

logger = structlog.stdlib.get_logger("flowforge.clickhouse")


def _generate_mock_data(query: str) -> list[dict]:
    """Generate mock data for development mode.

    Returns sample rows that look realistic for demo purposes.
    """
    num_rows = random.randint(10, 50)
    rows = []

    base_date = datetime.now() - timedelta(days=30)

    for i in range(num_rows):
        row = {
            "id": i + 1,
            "timestamp": (base_date + timedelta(hours=i * 6)).isoformat(),
            "value": round(random.uniform(100, 1000), 2),
            "category": random.choice(["A", "B", "C", "D"]),
            "metric": round(random.uniform(0, 100), 1),
            "count": random.randint(1, 100),
            "name": f"Item {i + 1}",
            "status": random.choice(["active", "pending", "completed"]),
        }
        rows.append(row)

    return rows


@dataclass
class ClickHouseClient:
    """Async ClickHouse client wrapper.

    Provides a read-only interface to ClickHouse for:
    - Analytical queries compiled by the workflow compiler
    - Schema discovery from system.columns

    Uses clickhouse-connect HTTP protocol. Falls back to mock data
    in development if ClickHouse is not reachable.
    """

    host: str
    port: int
    database: str
    user: str
    password: str

    def _get_client(self) -> clickhouse_connect.driver.Client:  # type: ignore[name-defined]
        """Create a clickhouse-connect client."""
        return clickhouse_connect.get_client(
            host=self.host,
            port=self.port,
            database=self.database,
            username=self.user,
            password=self.password,
        )

    async def execute(self, query: str, params: dict | None = None) -> list[dict]:
        """Execute a read-only query and return rows as dicts.

        All queries must be built via SQLGlot — never string concatenation.
        In development mode, falls back to mock data if ClickHouse is unreachable.
        """
        try:
            client = self._get_client()
            result = client.query(query, parameters=params)
            columns = result.column_names
            return [dict(zip(columns, row, strict=False)) for row in result.result_rows]
        except Exception as exc:
            if settings.app_env == "development":
                logger.info(
                    "clickhouse_fallback_mock",
                    reason=str(exc),
                    query=query[:100],
                )
                return _generate_mock_data(query)
            raise

    async def fetch_schema(self, table: str) -> list[dict]:
        """Fetch column metadata from system.columns for a given table."""
        if "." in table:
            db, tbl = table.split(".", 1)
        else:
            db = self.database
            tbl = table

        query = (
            "SELECT name, type, comment "
            "FROM system.columns "
            "WHERE database = {database:String} AND table = {table:String}"
        )
        return await self.execute(query, {"database": db, "table": tbl})

    async def ping(self) -> bool:
        """Health check."""
        try:
            client = self._get_client()
            result = client.query("SELECT 1")
            return len(result.result_rows) > 0
        except Exception as exc:
            if settings.app_env == "development":
                logger.info("clickhouse_ping_failed_dev", reason=str(exc))
                return True
            return False


def get_clickhouse_client() -> ClickHouseClient:
    return ClickHouseClient(
        host=settings.clickhouse_host,
        port=settings.clickhouse_port,
        database=settings.clickhouse_database,
        user=settings.clickhouse_user,
        password=settings.clickhouse_password,
    )
