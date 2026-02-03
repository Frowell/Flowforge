"""ClickHouse async client.

Read-only — this application never writes to ClickHouse.
Used for analytical queries dispatched by the query router.

NOTE: ClickHouse is not yet in the devcontainer. In development mode,
the client returns mock data. All code using this client must be mockable for testing.
"""

import random
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.core.config import settings


def _generate_mock_data(query: str) -> list[dict]:
    """Generate mock data for development mode.

    Returns sample rows that look realistic for demo purposes.
    """
    # Generate 10-50 sample rows
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
    """

    host: str
    port: int
    database: str
    user: str
    password: str

    async def execute(self, query: str, params: dict | None = None) -> list[dict]:
        """Execute a read-only query and return rows as dicts.

        All queries must be built via SQLGlot — never string concatenation.
        In development mode, returns mock data.
        """
        if settings.app_env == "development":
            # Return mock data for development
            return _generate_mock_data(query)

        # TODO: Implement with asynch or clickhouse-connect
        raise NotImplementedError("ClickHouse client not yet implemented")

    async def fetch_schema(self, table: str) -> list[dict]:
        """Fetch column metadata from system.columns for a given table."""
        if settings.app_env == "development":
            # Return mock schema for development
            return [
                {"name": "id", "type": "Int64", "comment": "Primary key"},
                {"name": "timestamp", "type": "DateTime", "comment": "Event timestamp"},
                {"name": "value", "type": "Float64", "comment": "Numeric value"},
                {"name": "category", "type": "String", "comment": "Category label"},
                {"name": "metric", "type": "Float64", "comment": "Metric value"},
                {"name": "count", "type": "Int64", "comment": "Count"},
                {"name": "name", "type": "String", "comment": "Name"},
                {"name": "status", "type": "String", "comment": "Status"},
            ]
        query = (
            "SELECT name, type, comment "
            "FROM system.columns "
            "WHERE database = {database:String} AND table = {table:String}"
        )
        return await self.execute(query, {"database": self.database, "table": table})

    async def ping(self) -> bool:
        """Health check."""
        if settings.app_env == "development":
            return True
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
