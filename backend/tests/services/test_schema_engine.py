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


class TestSortTransform:
    def test_sort_passthrough_preserves_all_columns(self):
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
                "id": "srt",
                "type": "sort",
                "data": {
                    "config": {
                        "sort_by": [{"column": "price", "direction": "desc"}],
                    }
                },
            },
        ]
        edges = [{"source": "src", "target": "srt"}]
        result = engine.validate_dag(nodes, edges)
        assert len(result["srt"]) == len(SAMPLE_COLUMNS)
        assert [c.name for c in result["srt"]] == [c.name for c in SAMPLE_COLUMNS]


class TestRenameTransform:
    def test_rename_output_has_renamed_columns(self):
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
                "id": "ren",
                "type": "rename",
                "data": {
                    "config": {
                        "rename_map": {"price": "trade_price", "symbol": "ticker"},
                    }
                },
            },
        ]
        edges = [{"source": "src", "target": "ren"}]
        result = engine.validate_dag(nodes, edges)
        assert len(result["ren"]) == len(SAMPLE_COLUMNS)
        names = [c.name for c in result["ren"]]
        assert "trade_price" in names
        assert "ticker" in names
        assert "price" not in names
        assert "symbol" not in names

    def test_rename_preserves_dtype(self):
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
                "id": "ren",
                "type": "rename",
                "data": {"config": {"rename_map": {"price": "trade_price"}}},
            },
        ]
        edges = [{"source": "src", "target": "ren"}]
        result = engine.validate_dag(nodes, edges)
        renamed_col = next(c for c in result["ren"] if c.name == "trade_price")
        assert renamed_col.dtype == "float64"


class TestDataSourceTransform:
    def test_data_source_outputs_config_columns(self):
        engine = SchemaEngine()
        columns = [
            {"name": "id", "dtype": "int64", "nullable": False},
            {"name": "name", "dtype": "string", "nullable": True},
        ]
        nodes = [
            {
                "id": "src",
                "type": "data_source",
                "data": {"config": {"columns": columns}},
            },
        ]
        result = engine.validate_dag(nodes, [])
        assert len(result["src"]) == 2
        assert result["src"][0].name == "id"
        assert result["src"][1].name == "name"

    def test_data_source_empty_columns(self):
        engine = SchemaEngine()
        nodes = [
            {"id": "src", "type": "data_source", "data": {"config": {"columns": []}}},
        ]
        result = engine.validate_dag(nodes, [])
        assert result["src"] == []


class TestFormulaTransform:
    def test_formula_adds_computed_column(self):
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
                "id": "frm",
                "type": "formula",
                "data": {
                    "config": {
                        "output_column": "notional",
                        "output_dtype": "float64",
                    }
                },
            },
        ]
        edges = [{"source": "src", "target": "frm"}]
        result = engine.validate_dag(nodes, edges)
        assert len(result["frm"]) == len(SAMPLE_COLUMNS) + 1
        assert result["frm"][-1].name == "notional"
        assert result["frm"][-1].dtype == "float64"
        assert result["frm"][-1].nullable is True


class TestUniqueTransform:
    def test_unique_passthrough_preserves_all_columns(self):
        engine = SchemaEngine()
        nodes = [
            {
                "id": "src",
                "type": "data_source",
                "data": {
                    "config": {"columns": [c.model_dump() for c in SAMPLE_COLUMNS]}
                },
            },
            {"id": "unq", "type": "unique", "data": {"config": {}}},
        ]
        edges = [{"source": "src", "target": "unq"}]
        result = engine.validate_dag(nodes, edges)
        assert len(result["unq"]) == len(SAMPLE_COLUMNS)


class TestSampleTransform:
    def test_sample_passthrough_preserves_all_columns(self):
        engine = SchemaEngine()
        nodes = [
            {
                "id": "src",
                "type": "data_source",
                "data": {
                    "config": {"columns": [c.model_dump() for c in SAMPLE_COLUMNS]}
                },
            },
            {"id": "smp", "type": "sample", "data": {"config": {"count": 10}}},
        ]
        edges = [{"source": "src", "target": "smp"}]
        result = engine.validate_dag(nodes, edges)
        assert len(result["smp"]) == len(SAMPLE_COLUMNS)


class TestMultiNodeDAG:
    def test_source_filter_select_sort_validates_correctly(self):
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
                "id": "flt",
                "type": "filter",
                "data": {
                    "config": {"column": "symbol", "operator": "=", "value": "AAPL"}
                },
            },
            {
                "id": "sel",
                "type": "select",
                "data": {"config": {"columns": ["symbol", "price"]}},
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
        ]
        edges = [
            {"source": "src", "target": "flt"},
            {"source": "flt", "target": "sel"},
            {"source": "sel", "target": "srt"},
        ]
        result = engine.validate_dag(nodes, edges)
        # After select, only symbol and price remain
        assert len(result["sel"]) == 2
        # Sort is passthrough
        assert len(result["srt"]) == 2
        assert result["srt"][0].name == "symbol"
        assert result["srt"][1].name == "price"


class TestDisconnectedNodes:
    def test_disconnected_nodes_handled_gracefully(self):
        engine = SchemaEngine()
        nodes = [
            {
                "id": "src1",
                "type": "data_source",
                "data": {
                    "config": {
                        "columns": [{"name": "a", "dtype": "string", "nullable": False}]
                    }
                },
            },
            {
                "id": "src2",
                "type": "data_source",
                "data": {
                    "config": {
                        "columns": [{"name": "b", "dtype": "int64", "nullable": True}]
                    }
                },
            },
        ]
        # No edges — both are independent
        result = engine.validate_dag(nodes, [])
        assert len(result["src1"]) == 1
        assert len(result["src2"]) == 1
        assert result["src1"][0].name == "a"
        assert result["src2"][0].name == "b"


class TestUnknownNodeType:
    def test_unknown_node_type_raises_value_error(self):
        engine = SchemaEngine()
        nodes = [
            {"id": "x", "type": "nonexistent_node", "data": {"config": {}}},
        ]
        with pytest.raises(ValueError, match="Unknown node type"):
            engine.validate_dag(nodes, [])


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
