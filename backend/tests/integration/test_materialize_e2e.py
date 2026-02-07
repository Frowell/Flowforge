"""End-to-end test with real Materialize.

Requires a running Materialize instance at localhost:6875.
Skipped automatically in regular CI; run with `pytest -m integration`.
"""

import asyncio

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def materialize_client():
    """Provide a Materialize client, skip if unavailable."""
    try:
        import asyncpg

        loop = asyncio.new_event_loop()
        conn = loop.run_until_complete(
            asyncpg.connect(
                host="localhost",
                port=6875,
                user="materialize",
                database="materialize",
            )
        )
        result = loop.run_until_complete(conn.fetchval("SELECT 1"))
        if result != 1:
            pytest.skip("Materialize connection failed")
        loop.run_until_complete(conn.close())
        loop.close()
        return True
    except Exception as e:
        pytest.skip(f"Materialize not available: {e}")


class TestMaterializeE2E:
    """End-to-end tests against a real Materialize instance."""

    def test_ping(self, materialize_client):
        """Materialize responds to basic query."""
        import asyncpg

        async def _ping():
            conn = await asyncpg.connect(
                host="localhost",
                port=6875,
                user="materialize",
                database="materialize",
            )
            try:
                result = await conn.fetchval("SELECT 1")
                assert result == 1
            finally:
                await conn.close()

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(_ping())
        finally:
            loop.close()

    def test_query_system_tables(self, materialize_client):
        """Can query Materialize system catalog."""
        import asyncpg

        async def _query():
            conn = await asyncpg.connect(
                host="localhost",
                port=6875,
                user="materialize",
                database="materialize",
            )
            try:
                rows = await conn.fetch(
                    "SELECT name FROM mz_schemas WHERE name = 'public'"
                )
                assert len(rows) >= 1
            finally:
                await conn.close()

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(_query())
        finally:
            loop.close()

    def test_query_materialized_views(self, materialize_client):
        """Can list existing materialized views."""
        import asyncpg

        async def _query():
            conn = await asyncpg.connect(
                host="localhost",
                port=6875,
                user="materialize",
                database="materialize",
            )
            try:
                rows = await conn.fetch(
                    "SELECT o.name FROM mz_objects o "
                    "JOIN mz_schemas s ON o.schema_id = s.id "
                    "WHERE s.name = 'public' "
                    "AND o.type = 'materialized-view'"
                )
                # May be empty if init-materialize has not run; that is OK
                assert isinstance(rows, list)
            finally:
                await conn.close()

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(_query())
        finally:
            loop.close()
