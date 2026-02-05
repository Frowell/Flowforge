"""End-to-end test with real ClickHouse.

Requires a running ClickHouse instance at localhost:8123.
Skipped automatically in regular CI; run with `pytest -m integration`.
"""

import pytest

from app.services.schema_engine import SchemaEngine
from app.services.workflow_compiler import WorkflowCompiler

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def clickhouse_client():
    """Provide a ClickHouse client, skip if unavailable."""
    try:
        import clickhouse_connect

        client = clickhouse_connect.get_client(host="localhost", port=8123)
        # Verify connection
        result = client.query("SELECT 1")
        if result.first_row[0] != 1:
            pytest.skip("ClickHouse connection failed")
        return client
    except Exception as e:
        pytest.skip(f"ClickHouse not available: {e}")


@pytest.fixture(scope="module")
def sample_trades_table(clickhouse_client):
    """Create a temporary table with sample trade data."""
    table_name = "test_trades_e2e"
    clickhouse_client.command(f"DROP TABLE IF EXISTS {table_name}")
    clickhouse_client.command(f"""
        CREATE TABLE {table_name} (
            trade_id String,
            symbol String,
            side String,
            price Float64,
            quantity Int64,
            trade_time DateTime
        ) ENGINE = Memory
    """)

    # Insert sample data
    clickhouse_client.command(f"""
        INSERT INTO {table_name} VALUES
        ('t1', 'AAPL', 'BUY', 150.50, 100, '2024-01-15 10:30:00'),
        ('t2', 'AAPL', 'SELL', 151.00, 50, '2024-01-15 10:31:00'),
        ('t3', 'MSFT', 'BUY', 380.25, 200, '2024-01-15 10:32:00'),
        ('t4', 'MSFT', 'BUY', 381.00, 150, '2024-01-15 10:33:00'),
        ('t5', 'GOOG', 'BUY', 140.00, 300, '2024-01-15 10:34:00'),
        ('t6', 'GOOG', 'SELL', 141.50, 100, '2024-01-15 10:35:00')
    """)

    yield table_name

    # Cleanup
    clickhouse_client.command(f"DROP TABLE IF EXISTS {table_name}")


class TestClickHouseE2E:
    """End-to-end tests executing compiled SQL against real ClickHouse."""

    def test_compile_and_execute_filter(self, clickhouse_client, sample_trades_table):
        """Filter node correctly filters rows in ClickHouse."""
        compiler = WorkflowCompiler(schema_engine=SchemaEngine())

        nodes = [
            {
                "id": "src",
                "type": "data_source",
                "data": {
                    "config": {
                        "table": sample_trades_table,
                        "columns": [
                            {"name": "trade_id", "dtype": "string"},
                            {"name": "symbol", "dtype": "string"},
                            {"name": "side", "dtype": "string"},
                            {"name": "price", "dtype": "float64"},
                            {"name": "quantity", "dtype": "int64"},
                        ],
                    }
                },
            },
            {
                "id": "flt",
                "type": "filter",
                "data": {
                    "config": {
                        "column": "symbol",
                        "operator": "=",
                        "value": "AAPL",
                    }
                },
            },
            {"id": "out", "type": "table_output", "data": {"config": {}}},
        ]
        edges = [
            {"source": "src", "target": "flt"},
            {"source": "flt", "target": "out"},
        ]

        segments = compiler.compile(nodes, edges)
        assert len(segments) == 1

        result = clickhouse_client.query(segments[0].sql)
        rows = list(result.named_results())

        assert len(rows) == 2  # Only AAPL trades
        assert all(row["symbol"] == "AAPL" for row in rows)

    def test_compile_and_execute_group_by(self, clickhouse_client, sample_trades_table):
        """GroupBy node correctly aggregates in ClickHouse."""
        compiler = WorkflowCompiler(schema_engine=SchemaEngine())

        nodes = [
            {
                "id": "src",
                "type": "data_source",
                "data": {
                    "config": {
                        "table": sample_trades_table,
                        "columns": [
                            {"name": "symbol", "dtype": "string"},
                            {"name": "quantity", "dtype": "int64"},
                        ],
                    }
                },
            },
            {
                "id": "grp",
                "type": "group_by",
                "data": {
                    "config": {
                        "group_columns": ["symbol"],
                        "aggregations": [
                            {
                                "column": "quantity",
                                "function": "SUM",
                                "alias": "total_quantity",
                            },
                        ],
                    }
                },
            },
            {"id": "out", "type": "table_output", "data": {"config": {}}},
        ]
        edges = [
            {"source": "src", "target": "grp"},
            {"source": "grp", "target": "out"},
        ]

        segments = compiler.compile(nodes, edges)
        assert len(segments) == 1

        result = clickhouse_client.query(segments[0].sql)
        rows = {row["symbol"]: row["total_quantity"] for row in result.named_results()}

        # Expected totals:
        # AAPL: 100 + 50 = 150
        # MSFT: 200 + 150 = 350
        # GOOG: 300 + 100 = 400
        assert rows["AAPL"] == 150
        assert rows["MSFT"] == 350
        assert rows["GOOG"] == 400

    def test_compile_and_execute_filter_then_sort(
        self, clickhouse_client, sample_trades_table
    ):
        """Filter → Sort pipeline executes correctly."""
        compiler = WorkflowCompiler(schema_engine=SchemaEngine())

        nodes = [
            {
                "id": "src",
                "type": "data_source",
                "data": {
                    "config": {
                        "table": sample_trades_table,
                        "columns": [
                            {"name": "trade_id", "dtype": "string"},
                            {"name": "symbol", "dtype": "string"},
                            {"name": "side", "dtype": "string"},
                            {"name": "price", "dtype": "float64"},
                        ],
                    }
                },
            },
            {
                "id": "flt",
                "type": "filter",
                "data": {
                    "config": {
                        "column": "side",
                        "operator": "=",
                        "value": "BUY",
                    }
                },
            },
            {
                "id": "srt",
                "type": "sort",
                "data": {
                    "config": {
                        "sort_by": [{"column": "price", "direction": "desc"}],
                    }
                },
            },
            {"id": "out", "type": "table_output", "data": {"config": {}}},
        ]
        edges = [
            {"source": "src", "target": "flt"},
            {"source": "flt", "target": "srt"},
            {"source": "srt", "target": "out"},
        ]

        segments = compiler.compile(nodes, edges)
        assert len(segments) == 1

        result = clickhouse_client.query(segments[0].sql)
        rows = list(result.named_results())

        # Only BUY trades, sorted by price descending
        assert len(rows) == 4
        assert all(row["side"] == "BUY" for row in rows)
        prices = [row["price"] for row in rows]
        assert prices == sorted(prices, reverse=True)
