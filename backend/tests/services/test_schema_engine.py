"""Schema engine tests — verify output schemas match expected for each node type."""

import pytest

from app.schemas.schema import ColumnSchema
from app.services.schema_engine import SchemaEngine

SAMPLE_COLUMNS = [
    ColumnSchema(name="id", dtype="int64", nullable=False),
    ColumnSchema(name="symbol", dtype="string", nullable=False),
    ColumnSchema(name="price", dtype="float64", nullable=True),
    ColumnSchema(name="quantity", dtype="int64", nullable=True),
]


def make_dag(nodes: list[dict], edges: list[dict]) -> tuple[list[dict], list[dict]]:
    return nodes, edges


class TestFilterTransform:
    def test_filter_passthrough_preserves_all_columns(self):
        engine = SchemaEngine()
        nodes = [
            {
                "id": "src",
                "type": "data_source",
                "data": {
                    "config": {"columns": [c.model_dump() for c in SAMPLE_COLUMNS]}
                },
            },
            {
                "id": "f1",
                "type": "filter",
                "data": {
                    "config": {"column": "symbol", "operator": "=", "value": "AAPL"}
                },
            },
        ]
        edges = [{"source": "src", "target": "f1"}]
        result = engine.validate_dag(nodes, edges)
        assert len(result["f1"]) == len(SAMPLE_COLUMNS)


class TestSelectTransform:
    def test_select_returns_subset_of_columns(self):
        engine = SchemaEngine()
        nodes = [
            {
                "id": "src",
                "type": "data_source",
                "data": {
                    "config": {"columns": [c.model_dump() for c in SAMPLE_COLUMNS]}
                },
            },
            {
                "id": "s1",
                "type": "select",
                "data": {"config": {"columns": ["symbol", "price"]}},
            },
        ]
        edges = [{"source": "src", "target": "s1"}]
        result = engine.validate_dag(nodes, edges)
        assert len(result["s1"]) == 2
        assert result["s1"][0].name == "symbol"
        assert result["s1"][1].name == "price"


class TestGroupByTransform:
    def test_group_by_produces_group_keys_and_aggregates(self):
        engine = SchemaEngine()
        nodes = [
            {
                "id": "src",
                "type": "data_source",
                "data": {
                    "config": {"columns": [c.model_dump() for c in SAMPLE_COLUMNS]}
                },
            },
            {
                "id": "g1",
                "type": "group_by",
                "data": {
                    "config": {
                        "group_columns": ["symbol"],
                        "aggregations": [
                            {
                                "column": "price",
                                "function": "AVG",
                                "alias": "avg_price",
                                "output_dtype": "float64",
                            },
                        ],
                    }
                },
            },
        ]
        edges = [{"source": "src", "target": "g1"}]
        result = engine.validate_dag(nodes, edges)
        assert len(result["g1"]) == 2
        assert result["g1"][0].name == "symbol"
        assert result["g1"][1].name == "avg_price"


class TestPivotTransform:
    def test_pivot_preserves_row_columns(self):
        engine = SchemaEngine()
        nodes = [
            {
                "id": "src",
                "type": "data_source",
                "data": {
                    "config": {"columns": [c.model_dump() for c in SAMPLE_COLUMNS]}
                },
            },
            {
                "id": "p1",
                "type": "pivot",
                "data": {
                    "config": {
                        "row_columns": ["symbol"],
                        "pivot_column": "quarter",
                        "value_column": "price",
                        "aggregation": "SUM",
                    }
                },
            },
        ]
        edges = [{"source": "src", "target": "p1"}]
        result = engine.validate_dag(nodes, edges)
        assert result["p1"][0].name == "symbol"

    def test_pivot_produces_value_column_with_aggregation(self):
        engine = SchemaEngine()
        nodes = [
            {
                "id": "src",
                "type": "data_source",
                "data": {
                    "config": {"columns": [c.model_dump() for c in SAMPLE_COLUMNS]}
                },
            },
            {
                "id": "p1",
                "type": "pivot",
                "data": {
                    "config": {
                        "row_columns": ["symbol"],
                        "pivot_column": "quarter",
                        "value_column": "price",
                        "aggregation": "AVG",
                    }
                },
            },
        ]
        edges = [{"source": "src", "target": "p1"}]
        result = engine.validate_dag(nodes, edges)
        assert len(result["p1"]) == 2
        assert result["p1"][1].name == "price_avg"
        assert result["p1"][1].dtype == "float64"

    def test_pivot_empty_config_returns_empty(self):
        engine = SchemaEngine()
        nodes = [
            {
                "id": "src",
                "type": "data_source",
                "data": {
                    "config": {"columns": [c.model_dump() for c in SAMPLE_COLUMNS]}
                },
            },
            {"id": "p1", "type": "pivot", "data": {"config": {}}},
        ]
        edges = [{"source": "src", "target": "p1"}]
        result = engine.validate_dag(nodes, edges)
        assert result["p1"] == []


class TestCycleDetection:
    def test_cycle_raises_value_error(self):
        engine = SchemaEngine()
        nodes = [
            {"id": "a", "type": "filter", "data": {"config": {}}},
            {"id": "b", "type": "filter", "data": {"config": {}}},
        ]
        edges = [{"source": "a", "target": "b"}, {"source": "b", "target": "a"}]
        with pytest.raises(ValueError, match="cycle"):
            engine.validate_dag(nodes, edges)
