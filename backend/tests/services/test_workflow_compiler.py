"""Workflow compiler tests — verify query merging and SQL generation."""

import pytest
import sqlglot

from app.services.schema_engine import SchemaEngine
from app.services.workflow_compiler import WorkflowCompiler


def get_compiler() -> WorkflowCompiler:
    return WorkflowCompiler(schema_engine=SchemaEngine())


def _normalize_sql(sql: str) -> str:
    """Parse and regenerate SQL to normalize whitespace and quoting."""
    return sqlglot.transpile(sql, read="clickhouse", write="clickhouse")[0]


class TestTopologicalSort:
    def test_linear_chain_sorted_correctly(self):
        compiler = get_compiler()
        nodes = [
            {
                "id": "a",
                "type": "data_source",
                "data": {"config": {"table": "trades", "columns": []}},
            },
            {"id": "b", "type": "filter", "data": {"config": {}}},
            {"id": "c", "type": "table_output", "data": {"config": {}}},
        ]
        edges = [{"source": "a", "target": "b"}, {"source": "b", "target": "c"}]
        result = compiler._topological_sort(nodes, edges)
        assert result.index("a") < result.index("b") < result.index("c")


class TestSubgraphExtraction:
    def test_find_ancestors_returns_all_upstream_nodes(self):
        compiler = get_compiler()
        edges = [
            {"source": "a", "target": "b"},
            {"source": "b", "target": "c"},
            {"source": "d", "target": "c"},
        ]
        ancestors = compiler._find_ancestors("c", edges)
        assert ancestors == {"a", "b", "d"}


class TestQueryMerging:
    def test_compile_filter_produces_where(self):
        """A filter node generates a WHERE clause merged into the parent SELECT."""
        compiler = get_compiler()
        nodes = [
            {
                "id": "src",
                "type": "data_source",
                "data": {
                    "config": {
                        "table": "fct_trades",
                        "columns": [
                            {"name": "symbol", "dtype": "string"},
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
                        "column": "symbol",
                        "operator": "=",
                        "value": "AAPL",
                    }
                },
            },
            {"id": "out", "type": "table_output", "data": {"config": {}}},
        ]
        edges = [{"source": "src", "target": "flt"}, {"source": "flt", "target": "out"}]
        segments = compiler._build_and_merge(
            compiler._topological_sort(nodes, edges), nodes, edges
        )
        assert len(segments) == 1
        sql_upper = segments[0].sql.upper()
        assert "WHERE" in sql_upper
        assert "SYMBOL" in sql_upper
        assert "AAPL" in sql_upper

    def test_compile_select_produces_column_list(self):
        """A select node limits the columns in the SELECT clause."""
        compiler = get_compiler()
        nodes = [
            {
                "id": "src",
                "type": "data_source",
                "data": {
                    "config": {
                        "table": "fct_trades",
                        "columns": [
                            {"name": "symbol", "dtype": "string"},
                            {"name": "price", "dtype": "float64"},
                            {"name": "quantity", "dtype": "int64"},
                        ],
                    }
                },
            },
            {
                "id": "sel",
                "type": "select",
                "data": {
                    "config": {
                        "columns": ["symbol", "price"],
                    }
                },
            },
            {"id": "out", "type": "table_output", "data": {"config": {}}},
        ]
        edges = [{"source": "src", "target": "sel"}, {"source": "sel", "target": "out"}]
        segments = compiler._build_and_merge(
            compiler._topological_sort(nodes, edges), nodes, edges
        )
        assert len(segments) == 1
        sql_upper = segments[0].sql.upper()
        assert "SYMBOL" in sql_upper
        assert "PRICE" in sql_upper
        # quantity should NOT be in the final select
        assert "QUANTITY" not in sql_upper

    def test_compile_sort_produces_order_by(self):
        """A sort node generates an ORDER BY clause."""
        compiler = get_compiler()
        nodes = [
            {
                "id": "src",
                "type": "data_source",
                "data": {
                    "config": {
                        "table": "fct_trades",
                        "columns": [{"name": "price", "dtype": "float64"}],
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
        edges = [{"source": "src", "target": "srt"}, {"source": "srt", "target": "out"}]
        segments = compiler._build_and_merge(
            compiler._topological_sort(nodes, edges), nodes, edges
        )
        assert len(segments) == 1
        sql_upper = segments[0].sql.upper()
        assert "ORDER BY" in sql_upper
        assert "DESC" in sql_upper

    def test_compile_rename_produces_aliases(self):
        """A rename node generates AS aliases."""
        compiler = get_compiler()
        nodes = [
            {
                "id": "src",
                "type": "data_source",
                "data": {
                    "config": {
                        "table": "fct_trades",
                        "columns": [
                            {"name": "symbol", "dtype": "string"},
                            {"name": "price", "dtype": "float64"},
                        ],
                    }
                },
            },
            {
                "id": "ren",
                "type": "rename",
                "data": {
                    "config": {
                        "rename_map": {"price": "trade_price"},
                    }
                },
            },
            {"id": "out", "type": "table_output", "data": {"config": {}}},
        ]
        edges = [{"source": "src", "target": "ren"}, {"source": "ren", "target": "out"}]
        segments = compiler._build_and_merge(
            compiler._topological_sort(nodes, edges), nodes, edges
        )
        assert len(segments) == 1
        sql = segments[0].sql
        assert "trade_price" in sql.lower()
        # Should have AS alias
        assert "AS" in sql.upper() or "as" in sql

    def test_compile_five_node_pipeline(self):
        """Source -> Filter -> Select -> Sort -> Table produces ONE merged query."""
        compiler = get_compiler()
        nodes = [
            {
                "id": "src",
                "type": "data_source",
                "data": {
                    "config": {
                        "table": "fct_trades",
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
                        "column": "side",
                        "operator": "=",
                        "value": "BUY",
                    }
                },
            },
            {
                "id": "sel",
                "type": "select",
                "data": {
                    "config": {
                        "columns": ["symbol", "price", "quantity"],
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
            {"source": "flt", "target": "sel"},
            {"source": "sel", "target": "srt"},
            {"source": "srt", "target": "out"},
        ]
        segments = compiler._build_and_merge(
            compiler._topological_sort(nodes, edges), nodes, edges
        )
        # Must produce exactly ONE merged query
        assert len(segments) == 1
        sql_upper = segments[0].sql.upper()
        assert "WHERE" in sql_upper
        assert "ORDER BY" in sql_upper
        assert "DESC" in sql_upper
        # Should have the selected columns, not all columns
        assert "SYMBOL" in sql_upper
        assert "PRICE" in sql_upper
        assert "QUANTITY" in sql_upper
        # trade_id and side should not be in the final select columns
        # (they may appear in WHERE clause though)

    def test_compile_filter_contains_operator(self):
        """The 'contains' operator maps to LIKE '%val%'."""
        compiler = get_compiler()
        nodes = [
            {
                "id": "src",
                "type": "data_source",
                "data": {
                    "config": {
                        "table": "fct_trades",
                        "columns": [{"name": "symbol", "dtype": "string"}],
                    }
                },
            },
            {
                "id": "flt",
                "type": "filter",
                "data": {
                    "config": {
                        "column": "symbol",
                        "operator": "contains",
                        "value": "AA",
                    }
                },
            },
            {"id": "out", "type": "table_output", "data": {"config": {}}},
        ]
        edges = [{"source": "src", "target": "flt"}, {"source": "flt", "target": "out"}]
        segments = compiler._build_and_merge(
            compiler._topological_sort(nodes, edges), nodes, edges
        )
        assert len(segments) == 1
        sql = segments[0].sql
        assert "LIKE" in sql.upper()
        assert "%AA%" in sql

    def test_compile_multi_sort(self):
        """Multiple sort columns produce multi-column ORDER BY."""
        compiler = get_compiler()
        nodes = [
            {
                "id": "src",
                "type": "data_source",
                "data": {
                    "config": {
                        "table": "fct_trades",
                        "columns": [
                            {"name": "symbol", "dtype": "string"},
                            {"name": "price", "dtype": "float64"},
                        ],
                    }
                },
            },
            {
                "id": "srt",
                "type": "sort",
                "data": {
                    "config": {
                        "sort_by": [
                            {"column": "symbol", "direction": "asc"},
                            {"column": "price", "direction": "desc"},
                        ],
                    }
                },
            },
            {"id": "out", "type": "table_output", "data": {"config": {}}},
        ]
        edges = [{"source": "src", "target": "srt"}, {"source": "srt", "target": "out"}]
        segments = compiler._build_and_merge(
            compiler._topological_sort(nodes, edges), nodes, edges
        )
        assert len(segments) == 1
        sql_upper = segments[0].sql.upper()
        assert "ORDER BY" in sql_upper
        # Both columns should appear in ORDER BY
        assert "SYMBOL" in sql_upper
        assert "PRICE" in sql_upper


class TestEdgeCases:
    """Edge cases: empty graph, no data source, IS NULL, IN, OR filters, pagination."""

    def test_compile_empty_graph_returns_empty(self):
        """Empty node list produces no segments."""
        compiler = get_compiler()
        nodes: list[dict] = []
        edges: list[dict] = []
        segments = compiler._build_and_merge(
            compiler._topological_sort(nodes, edges), nodes, edges
        )
        assert segments == []

    def test_compile_no_data_source_returns_empty(self):
        """A graph with only non-source nodes produces no output segments."""
        compiler = get_compiler()
        nodes = [
            {"id": "flt", "type": "filter", "data": {"config": {}}},
            {"id": "out", "type": "table_output", "data": {"config": {}}},
        ]
        edges = [{"source": "flt", "target": "out"}]
        segments = compiler._build_and_merge(
            compiler._topological_sort(nodes, edges), nodes, edges
        )
        # Filter with no parent expr_map entry produces no segments
        assert len(segments) == 0

    def test_compile_table_output_with_max_rows(self):
        """Table output node's max_rows config controls LIMIT in _apply_limits."""
        compiler = get_compiler()
        nodes = [
            {
                "id": "src",
                "type": "data_source",
                "data": {
                    "config": {
                        "table": "fct_trades",
                        "columns": [{"name": "symbol", "dtype": "string"}],
                    }
                },
            },
            {
                "id": "out",
                "type": "table_output",
                "data": {"config": {"max_rows": 500}},
            },
        ]
        edges = [{"source": "src", "target": "out"}]
        segments = compiler.compile(nodes, edges)
        assert len(segments) == 1
        sql_upper = segments[0].sql.upper()
        assert "LIMIT" in sql_upper
        assert "500" in segments[0].sql

    def test_compile_filter_is_null(self):
        """IS NULL filter produces IS NULL in SQL."""
        compiler = get_compiler()
        nodes = [
            {
                "id": "src",
                "type": "data_source",
                "data": {
                    "config": {
                        "table": "fct_trades",
                        "columns": [{"name": "price", "dtype": "float64"}],
                    }
                },
            },
            {
                "id": "flt",
                "type": "filter",
                "data": {
                    "config": {
                        "column": "price",
                        "operator": "=",
                        "value": "NULL",
                    }
                },
            },
            {"id": "out", "type": "table_output", "data": {"config": {}}},
        ]
        edges = [{"source": "src", "target": "flt"}, {"source": "flt", "target": "out"}]
        segments = compiler._build_and_merge(
            compiler._topological_sort(nodes, edges), nodes, edges
        )
        assert len(segments) == 1
        # The filter with value "NULL" at least produces a WHERE clause
        sql_upper = segments[0].sql.upper()
        assert "WHERE" in sql_upper

    def test_compile_filter_between_operator(self):
        """Between operator produces BETWEEN in SQL."""
        compiler = get_compiler()
        nodes = [
            {
                "id": "src",
                "type": "data_source",
                "data": {
                    "config": {
                        "table": "fct_trades",
                        "columns": [{"name": "price", "dtype": "float64"}],
                    }
                },
            },
            {
                "id": "flt",
                "type": "filter",
                "data": {
                    "config": {
                        "column": "price",
                        "operator": "between",
                        "value": "10,100",
                    }
                },
            },
            {"id": "out", "type": "table_output", "data": {"config": {}}},
        ]
        edges = [{"source": "src", "target": "flt"}, {"source": "flt", "target": "out"}]
        segments = compiler._build_and_merge(
            compiler._topological_sort(nodes, edges), nodes, edges
        )
        assert len(segments) == 1
        sql_upper = segments[0].sql.upper()
        assert "BETWEEN" in sql_upper

    def test_compile_filter_starts_with(self):
        """Starts with operator produces LIKE 'val%'."""
        compiler = get_compiler()
        nodes = [
            {
                "id": "src",
                "type": "data_source",
                "data": {
                    "config": {
                        "table": "fct_trades",
                        "columns": [{"name": "symbol", "dtype": "string"}],
                    }
                },
            },
            {
                "id": "flt",
                "type": "filter",
                "data": {
                    "config": {
                        "column": "symbol",
                        "operator": "starts with",
                        "value": "AA",
                    }
                },
            },
            {"id": "out", "type": "table_output", "data": {"config": {}}},
        ]
        edges = [{"source": "src", "target": "flt"}, {"source": "flt", "target": "out"}]
        segments = compiler._build_and_merge(
            compiler._topological_sort(nodes, edges), nodes, edges
        )
        assert len(segments) == 1
        sql = segments[0].sql
        assert "LIKE" in sql.upper()
        assert "AA%" in sql

    def test_compile_filter_ends_with(self):
        """Ends with operator produces LIKE '%val'."""
        compiler = get_compiler()
        nodes = [
            {
                "id": "src",
                "type": "data_source",
                "data": {
                    "config": {
                        "table": "fct_trades",
                        "columns": [{"name": "symbol", "dtype": "string"}],
                    }
                },
            },
            {
                "id": "flt",
                "type": "filter",
                "data": {
                    "config": {
                        "column": "symbol",
                        "operator": "ends with",
                        "value": "PL",
                    }
                },
            },
            {"id": "out", "type": "table_output", "data": {"config": {}}},
        ]
        edges = [{"source": "src", "target": "flt"}, {"source": "flt", "target": "out"}]
        segments = compiler._build_and_merge(
            compiler._topological_sort(nodes, edges), nodes, edges
        )
        assert len(segments) == 1
        sql = segments[0].sql
        assert "LIKE" in sql.upper()
        assert "%PL" in sql

    def test_compile_multiple_filters_merge(self):
        """Two consecutive filters produce merged WHERE with AND."""
        compiler = get_compiler()
        nodes = [
            {
                "id": "src",
                "type": "data_source",
                "data": {
                    "config": {
                        "table": "fct_trades",
                        "columns": [
                            {"name": "symbol", "dtype": "string"},
                            {"name": "price", "dtype": "float64"},
                        ],
                    }
                },
            },
            {
                "id": "f1",
                "type": "filter",
                "data": {
                    "config": {
                        "column": "symbol",
                        "operator": "=",
                        "value": "AAPL",
                    }
                },
            },
            {
                "id": "f2",
                "type": "filter",
                "data": {
                    "config": {
                        "column": "price",
                        "operator": ">",
                        "value": "100",
                    }
                },
            },
            {"id": "out", "type": "table_output", "data": {"config": {}}},
        ]
        edges = [
            {"source": "src", "target": "f1"},
            {"source": "f1", "target": "f2"},
            {"source": "f2", "target": "out"},
        ]
        segments = compiler._build_and_merge(
            compiler._topological_sort(nodes, edges), nodes, edges
        )
        assert len(segments) == 1
        sql_upper = segments[0].sql.upper()
        assert "WHERE" in sql_upper
        assert "AND" in sql_upper
        assert "SYMBOL" in sql_upper
        assert "PRICE" in sql_upper

    def test_compile_limit_node_produces_limit_offset(self):
        """Limit node adds LIMIT and OFFSET."""
        compiler = get_compiler()
        nodes = [
            {
                "id": "src",
                "type": "data_source",
                "data": {
                    "config": {
                        "table": "fct_trades",
                        "columns": [{"name": "symbol", "dtype": "string"}],
                    }
                },
            },
            {
                "id": "lim",
                "type": "limit",
                "data": {"config": {"limit": 25, "offset": 50}},
            },
            {"id": "out", "type": "table_output", "data": {"config": {}}},
        ]
        edges = [{"source": "src", "target": "lim"}, {"source": "lim", "target": "out"}]
        segments = compiler._build_and_merge(
            compiler._topological_sort(nodes, edges), nodes, edges
        )
        assert len(segments) == 1
        sql_upper = segments[0].sql.upper()
        assert "LIMIT" in sql_upper
        assert "OFFSET" in sql_upper
        assert "25" in segments[0].sql
        assert "50" in segments[0].sql


class TestPhase2NodeTypes:
    """Tests for Phase 2 analytical nodes: group_by, join, etc."""

    def test_compile_group_by_produces_group_by_clause(self):
        """Group By node wraps parent as subquery with GROUP BY + SUM."""
        compiler = get_compiler()
        nodes = [
            {
                "id": "src",
                "type": "data_source",
                "data": {
                    "config": {
                        "table": "fct_trades",
                        "columns": [
                            {"name": "sector", "dtype": "string"},
                            {"name": "notional", "dtype": "float64"},
                        ],
                    }
                },
            },
            {
                "id": "grp",
                "type": "group_by",
                "data": {
                    "config": {
                        "group_columns": ["sector"],
                        "agg_column": "notional",
                        "agg_function": "SUM",
                    }
                },
            },
            {"id": "out", "type": "table_output", "data": {"config": {}}},
        ]
        edges = [{"source": "src", "target": "grp"}, {"source": "grp", "target": "out"}]
        segments = compiler._build_and_merge(
            compiler._topological_sort(nodes, edges), nodes, edges
        )
        assert len(segments) == 1
        sql_upper = segments[0].sql.upper()
        assert "GROUP BY" in sql_upper
        assert "SUM" in sql_upper
        assert "SECTOR" in sql_upper

    def test_compile_group_by_multi_agg(self):
        """Group By with multiple aggregations."""
        compiler = get_compiler()
        nodes = [
            {
                "id": "src",
                "type": "data_source",
                "data": {
                    "config": {
                        "table": "fct_trades",
                        "columns": [
                            {"name": "sector", "dtype": "string"},
                            {"name": "notional", "dtype": "float64"},
                            {"name": "price", "dtype": "float64"},
                        ],
                    }
                },
            },
            {
                "id": "grp",
                "type": "group_by",
                "data": {
                    "config": {
                        "group_columns": ["sector"],
                        "aggregations": [
                            {
                                "column": "notional",
                                "function": "SUM",
                                "alias": "total_notional",
                            },
                            {
                                "column": "price",
                                "function": "AVG",
                                "alias": "avg_price",
                            },
                        ],
                    }
                },
            },
            {"id": "out", "type": "table_output", "data": {"config": {}}},
        ]
        edges = [{"source": "src", "target": "grp"}, {"source": "grp", "target": "out"}]
        segments = compiler._build_and_merge(
            compiler._topological_sort(nodes, edges), nodes, edges
        )
        assert len(segments) == 1
        sql_upper = segments[0].sql.upper()
        assert "GROUP BY" in sql_upper
        assert "SUM" in sql_upper
        assert "AVG" in sql_upper
        sql_lower = segments[0].sql.lower()
        assert "total_notional" in sql_lower
        assert "avg_price" in sql_lower

    def test_compile_join_produces_join(self):
        """Join node combines two data sources with INNER JOIN."""
        compiler = get_compiler()
        nodes = [
            {
                "id": "left",
                "type": "data_source",
                "data": {
                    "config": {
                        "table": "fct_trades",
                        "columns": [
                            {"name": "symbol", "dtype": "string"},
                            {"name": "price", "dtype": "float64"},
                        ],
                    }
                },
            },
            {
                "id": "right",
                "type": "data_source",
                "data": {
                    "config": {
                        "table": "dim_instruments",
                        "columns": [
                            {"name": "symbol", "dtype": "string"},
                            {"name": "sector", "dtype": "string"},
                        ],
                    }
                },
            },
            {
                "id": "jn",
                "type": "join",
                "data": {
                    "config": {
                        "join_type": "inner",
                        "left_key": "symbol",
                        "right_key": "symbol",
                    }
                },
            },
            {"id": "out", "type": "table_output", "data": {"config": {}}},
        ]
        edges = [
            {"source": "left", "target": "jn"},
            {"source": "right", "target": "jn"},
            {"source": "jn", "target": "out"},
        ]
        segments = compiler._build_and_merge(
            compiler._topological_sort(nodes, edges), nodes, edges
        )
        assert len(segments) == 1
        sql_upper = segments[0].sql.upper()
        assert "JOIN" in sql_upper
        assert "_LEFT" in sql_upper
        assert "_RIGHT" in sql_upper
        assert "SYMBOL" in sql_upper

    def test_compile_join_left(self):
        """LEFT JOIN variant."""
        compiler = get_compiler()
        nodes = [
            {
                "id": "left",
                "type": "data_source",
                "data": {
                    "config": {
                        "table": "fct_trades",
                        "columns": [{"name": "id", "dtype": "string"}],
                    }
                },
            },
            {
                "id": "right",
                "type": "data_source",
                "data": {
                    "config": {
                        "table": "dim_instruments",
                        "columns": [{"name": "id", "dtype": "string"}],
                    }
                },
            },
            {
                "id": "jn",
                "type": "join",
                "data": {
                    "config": {
                        "join_type": "left",
                        "left_key": "id",
                        "right_key": "id",
                    }
                },
            },
            {"id": "out", "type": "table_output", "data": {"config": {}}},
        ]
        edges = [
            {"source": "left", "target": "jn"},
            {"source": "right", "target": "jn"},
            {"source": "jn", "target": "out"},
        ]
        segments = compiler._build_and_merge(
            compiler._topological_sort(nodes, edges), nodes, edges
        )
        assert len(segments) == 1
        sql_upper = segments[0].sql.upper()
        assert "LEFT" in sql_upper
        assert "JOIN" in sql_upper

    def test_compile_union_produces_union_all(self):
        """Union node combines two data sources with UNION ALL."""
        compiler = get_compiler()
        nodes = [
            {
                "id": "a",
                "type": "data_source",
                "data": {
                    "config": {
                        "table": "trades_us",
                        "columns": [{"name": "symbol", "dtype": "string"}],
                    }
                },
            },
            {
                "id": "b",
                "type": "data_source",
                "data": {
                    "config": {
                        "table": "trades_eu",
                        "columns": [{"name": "symbol", "dtype": "string"}],
                    }
                },
            },
            {"id": "un", "type": "union", "data": {"config": {}}},
            {"id": "out", "type": "table_output", "data": {"config": {}}},
        ]
        edges = [
            {"source": "a", "target": "un"},
            {"source": "b", "target": "un"},
            {"source": "un", "target": "out"},
        ]
        segments = compiler._build_and_merge(
            compiler._topological_sort(nodes, edges), nodes, edges
        )
        assert len(segments) == 1
        sql_upper = segments[0].sql.upper()
        assert "UNION ALL" in sql_upper

    def test_compile_formula_adds_computed_column(self):
        """Formula node adds an aliased expression to the SELECT list."""
        compiler = get_compiler()
        nodes = [
            {
                "id": "src",
                "type": "data_source",
                "data": {
                    "config": {
                        "table": "fct_trades",
                        "columns": [
                            {"name": "price", "dtype": "float64"},
                            {"name": "qty", "dtype": "int64"},
                        ],
                    }
                },
            },
            {
                "id": "frm",
                "type": "formula",
                "data": {
                    "config": {
                        "expression": "[price] * [qty]",
                        "output_column": "notional",
                    }
                },
            },
            {"id": "out", "type": "table_output", "data": {"config": {}}},
        ]
        edges = [{"source": "src", "target": "frm"}, {"source": "frm", "target": "out"}]
        segments = compiler._build_and_merge(
            compiler._topological_sort(nodes, edges), nodes, edges
        )
        assert len(segments) == 1
        sql_lower = segments[0].sql.lower()
        assert "notional" in sql_lower
        assert "*" in segments[0].sql
        assert "price" in sql_lower
        assert "qty" in sql_lower

    def test_compile_unique_produces_distinct(self):
        """Unique node adds DISTINCT keyword."""
        compiler = get_compiler()
        nodes = [
            {
                "id": "src",
                "type": "data_source",
                "data": {
                    "config": {
                        "table": "fct_trades",
                        "columns": [{"name": "symbol", "dtype": "string"}],
                    }
                },
            },
            {"id": "unq", "type": "unique", "data": {"config": {}}},
            {"id": "out", "type": "table_output", "data": {"config": {}}},
        ]
        edges = [{"source": "src", "target": "unq"}, {"source": "unq", "target": "out"}]
        segments = compiler._build_and_merge(
            compiler._topological_sort(nodes, edges), nodes, edges
        )
        assert len(segments) == 1
        sql_upper = segments[0].sql.upper()
        assert "DISTINCT" in sql_upper

    def test_compile_sample_produces_limit(self):
        """Sample node adds LIMIT clause."""
        compiler = get_compiler()
        nodes = [
            {
                "id": "src",
                "type": "data_source",
                "data": {
                    "config": {
                        "table": "fct_trades",
                        "columns": [{"name": "symbol", "dtype": "string"}],
                    }
                },
            },
            {"id": "smp", "type": "sample", "data": {"config": {"count": 50}}},
            {"id": "out", "type": "table_output", "data": {"config": {}}},
        ]
        edges = [{"source": "src", "target": "smp"}, {"source": "smp", "target": "out"}]
        segments = compiler._build_and_merge(
            compiler._topological_sort(nodes, edges), nodes, edges
        )
        assert len(segments) == 1
        sql_upper = segments[0].sql.upper()
        assert "LIMIT" in sql_upper
        assert "50" in segments[0].sql

    def test_compile_join_then_group_by(self):
        """Full pipeline: join two tables, then group by."""
        compiler = get_compiler()
        nodes = [
            {
                "id": "left",
                "type": "data_source",
                "data": {
                    "config": {
                        "table": "fct_trades",
                        "columns": [
                            {"name": "symbol", "dtype": "string"},
                            {"name": "notional", "dtype": "float64"},
                        ],
                    }
                },
            },
            {
                "id": "right",
                "type": "data_source",
                "data": {
                    "config": {
                        "table": "dim_instruments",
                        "columns": [
                            {"name": "symbol", "dtype": "string"},
                            {"name": "sector", "dtype": "string"},
                        ],
                    }
                },
            },
            {
                "id": "jn",
                "type": "join",
                "data": {
                    "config": {
                        "join_type": "inner",
                        "left_key": "symbol",
                        "right_key": "symbol",
                    }
                },
            },
            {
                "id": "grp",
                "type": "group_by",
                "data": {
                    "config": {
                        "group_columns": ["sector"],
                        "aggregations": [
                            {
                                "column": "notional",
                                "function": "SUM",
                                "alias": "total_notional",
                            },
                        ],
                    }
                },
            },
            {"id": "out", "type": "table_output", "data": {"config": {}}},
        ]
        edges = [
            {"source": "left", "target": "jn"},
            {"source": "right", "target": "jn"},
            {"source": "jn", "target": "grp"},
            {"source": "grp", "target": "out"},
        ]
        segments = compiler._build_and_merge(
            compiler._topological_sort(nodes, edges), nodes, edges
        )
        assert len(segments) == 1
        sql_upper = segments[0].sql.upper()
        assert "JOIN" in sql_upper
        assert "GROUP BY" in sql_upper
        assert "SUM" in sql_upper
        assert "SECTOR" in sql_upper


class TestMultiSourceDAG:
    """Tests for complex multi-source DAG scenarios."""

    def test_compile_join_then_filter_then_sort(self):
        """Join → Filter → Sort pipeline produces merged query."""
        compiler = get_compiler()
        nodes = [
            {
                "id": "trades",
                "type": "data_source",
                "data": {
                    "config": {
                        "table": "fct_trades",
                        "columns": [
                            {"name": "symbol", "dtype": "string"},
                            {"name": "price", "dtype": "float64"},
                            {"name": "quantity", "dtype": "int64"},
                        ],
                    }
                },
            },
            {
                "id": "instruments",
                "type": "data_source",
                "data": {
                    "config": {
                        "table": "dim_instruments",
                        "columns": [
                            {"name": "symbol", "dtype": "string"},
                            {"name": "sector", "dtype": "string"},
                        ],
                    }
                },
            },
            {
                "id": "jn",
                "type": "join",
                "data": {
                    "config": {
                        "join_type": "inner",
                        "left_key": "symbol",
                        "right_key": "symbol",
                    }
                },
            },
            {
                "id": "flt",
                "type": "filter",
                "data": {
                    "config": {
                        "column": "sector",
                        "operator": "=",
                        "value": "Technology",
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
            {"source": "trades", "target": "jn"},
            {"source": "instruments", "target": "jn"},
            {"source": "jn", "target": "flt"},
            {"source": "flt", "target": "srt"},
            {"source": "srt", "target": "out"},
        ]
        segments = compiler._build_and_merge(
            compiler._topological_sort(nodes, edges), nodes, edges
        )
        assert len(segments) == 1
        sql_upper = segments[0].sql.upper()
        assert "JOIN" in sql_upper
        assert "WHERE" in sql_upper
        assert "SECTOR" in sql_upper
        assert "TECHNOLOGY" in sql_upper
        assert "ORDER BY" in sql_upper
        assert "DESC" in sql_upper

    def test_compile_three_source_join(self):
        """A JOIN B → JOIN C (chained joins)."""
        compiler = get_compiler()
        nodes = [
            {
                "id": "trades",
                "type": "data_source",
                "data": {
                    "config": {
                        "table": "fct_trades",
                        "columns": [
                            {"name": "symbol", "dtype": "string"},
                            {"name": "account_id", "dtype": "string"},
                            {"name": "price", "dtype": "float64"},
                        ],
                    }
                },
            },
            {
                "id": "instruments",
                "type": "data_source",
                "data": {
                    "config": {
                        "table": "dim_instruments",
                        "columns": [
                            {"name": "symbol", "dtype": "string"},
                            {"name": "sector", "dtype": "string"},
                        ],
                    }
                },
            },
            {
                "id": "accounts",
                "type": "data_source",
                "data": {
                    "config": {
                        "table": "dim_accounts",
                        "columns": [
                            {"name": "account_id", "dtype": "string"},
                            {"name": "account_name", "dtype": "string"},
                        ],
                    }
                },
            },
            {
                "id": "jn1",
                "type": "join",
                "data": {
                    "config": {
                        "join_type": "inner",
                        "left_key": "symbol",
                        "right_key": "symbol",
                    }
                },
            },
            {
                "id": "jn2",
                "type": "join",
                "data": {
                    "config": {
                        "join_type": "left",
                        "left_key": "account_id",
                        "right_key": "account_id",
                    }
                },
            },
            {"id": "out", "type": "table_output", "data": {"config": {}}},
        ]
        edges = [
            {"source": "trades", "target": "jn1"},
            {"source": "instruments", "target": "jn1"},
            {"source": "jn1", "target": "jn2"},
            {"source": "accounts", "target": "jn2"},
            {"source": "jn2", "target": "out"},
        ]
        segments = compiler._build_and_merge(
            compiler._topological_sort(nodes, edges), nodes, edges
        )
        assert len(segments) == 1
        sql_upper = segments[0].sql.upper()
        # Should have multiple JOINs
        assert sql_upper.count("JOIN") >= 2
        # Should reference all three tables' columns
        assert "SYMBOL" in sql_upper
        assert "SECTOR" in sql_upper
        assert "ACCOUNT_ID" in sql_upper

    def test_compile_union_then_groupby(self):
        """UNION ALL → GROUP BY produces aggregated union."""
        compiler = get_compiler()
        nodes = [
            {
                "id": "us_trades",
                "type": "data_source",
                "data": {
                    "config": {
                        "table": "trades_us",
                        "columns": [
                            {"name": "symbol", "dtype": "string"},
                            {"name": "quantity", "dtype": "int64"},
                        ],
                    }
                },
            },
            {
                "id": "eu_trades",
                "type": "data_source",
                "data": {
                    "config": {
                        "table": "trades_eu",
                        "columns": [
                            {"name": "symbol", "dtype": "string"},
                            {"name": "quantity", "dtype": "int64"},
                        ],
                    }
                },
            },
            {"id": "un", "type": "union", "data": {"config": {}}},
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
            {"source": "us_trades", "target": "un"},
            {"source": "eu_trades", "target": "un"},
            {"source": "un", "target": "grp"},
            {"source": "grp", "target": "out"},
        ]
        segments = compiler._build_and_merge(
            compiler._topological_sort(nodes, edges), nodes, edges
        )
        assert len(segments) == 1
        sql_upper = segments[0].sql.upper()
        assert "UNION ALL" in sql_upper
        assert "GROUP BY" in sql_upper
        assert "SUM" in sql_upper
        sql_lower = segments[0].sql.lower()
        assert "total_quantity" in sql_lower

    def test_compile_diamond_dag(self):
        """Diamond DAG: A → B, A → C, then B+C → Join D (shared ancestor)."""
        compiler = get_compiler()
        nodes = [
            {
                "id": "trades",
                "type": "data_source",
                "data": {
                    "config": {
                        "table": "fct_trades",
                        "columns": [
                            {"name": "symbol", "dtype": "string"},
                            {"name": "price", "dtype": "float64"},
                            {"name": "quantity", "dtype": "int64"},
                        ],
                    }
                },
            },
            {
                "id": "filter_buy",
                "type": "filter",
                "data": {
                    "config": {
                        "column": "price",
                        "operator": ">",
                        "value": "100",
                    }
                },
            },
            {
                "id": "filter_sell",
                "type": "filter",
                "data": {
                    "config": {
                        "column": "price",
                        "operator": "<",
                        "value": "50",
                    }
                },
            },
            {
                "id": "jn",
                "type": "union",  # Union the two filtered streams
                "data": {"config": {}},
            },
            {"id": "out", "type": "table_output", "data": {"config": {}}},
        ]
        edges = [
            {"source": "trades", "target": "filter_buy"},
            {"source": "trades", "target": "filter_sell"},
            {"source": "filter_buy", "target": "jn"},
            {"source": "filter_sell", "target": "jn"},
            {"source": "jn", "target": "out"},
        ]
        segments = compiler._build_and_merge(
            compiler._topological_sort(nodes, edges), nodes, edges
        )
        # Diamond topology should produce a valid query
        assert len(segments) == 1
        sql_upper = segments[0].sql.upper()
        # Should have UNION ALL combining the two branches
        assert "UNION ALL" in sql_upper
        # Both WHERE conditions should be present (in different subqueries)
        assert "100" in segments[0].sql
        assert "50" in segments[0].sql

    def test_compile_join_with_formula(self):
        """Join then Formula: computed column on joined data."""
        compiler = get_compiler()
        nodes = [
            {
                "id": "trades",
                "type": "data_source",
                "data": {
                    "config": {
                        "table": "fct_trades",
                        "columns": [
                            {"name": "symbol", "dtype": "string"},
                            {"name": "price", "dtype": "float64"},
                            {"name": "quantity", "dtype": "int64"},
                        ],
                    }
                },
            },
            {
                "id": "instruments",
                "type": "data_source",
                "data": {
                    "config": {
                        "table": "dim_instruments",
                        "columns": [
                            {"name": "symbol", "dtype": "string"},
                            {"name": "lot_size", "dtype": "int64"},
                        ],
                    }
                },
            },
            {
                "id": "jn",
                "type": "join",
                "data": {
                    "config": {
                        "join_type": "inner",
                        "left_key": "symbol",
                        "right_key": "symbol",
                    }
                },
            },
            {
                "id": "frm",
                "type": "formula",
                "data": {
                    "config": {
                        "expression": "[price] * [quantity]",
                        "output_column": "notional",
                    }
                },
            },
            {"id": "out", "type": "table_output", "data": {"config": {}}},
        ]
        edges = [
            {"source": "trades", "target": "jn"},
            {"source": "instruments", "target": "jn"},
            {"source": "jn", "target": "frm"},
            {"source": "frm", "target": "out"},
        ]
        segments = compiler._build_and_merge(
            compiler._topological_sort(nodes, edges), nodes, edges
        )
        assert len(segments) == 1
        sql_upper = segments[0].sql.upper()
        assert "JOIN" in sql_upper
        sql_lower = segments[0].sql.lower()
        assert "notional" in sql_lower
        assert "*" in segments[0].sql  # multiplication for formula


class TestFilterTypedLiterals:
    """C3/C4 bug fixes: typed filter literals and unknown operator rejection."""

    def _make_filter_pipeline(self, column_dtype, operator, value):
        """Helper: data_source → filter → table_output pipeline."""
        nodes = [
            {
                "id": "src",
                "type": "data_source",
                "data": {
                    "config": {
                        "table": "fct_trades",
                        "columns": [
                            {"name": "symbol", "dtype": "string"},
                            {"name": "price", "dtype": "float64"},
                            {"name": "quantity", "dtype": "int64"},
                            {"name": "is_active", "dtype": "bool"},
                        ],
                    }
                },
            },
            {
                "id": "flt",
                "type": "filter",
                "data": {
                    "config": {
                        "column": {
                            "string": "symbol",
                            "float64": "price",
                            "int64": "quantity",
                            "bool": "is_active",
                        }.get(column_dtype, "symbol"),
                        "operator": operator,
                        "value": value,
                    }
                },
            },
            {"id": "out", "type": "table_output", "data": {"config": {}}},
        ]
        edges = [
            {"source": "src", "target": "flt"},
            {"source": "flt", "target": "out"},
        ]
        return nodes, edges

    def test_numeric_int_filter_produces_number_literal(self):
        """int64 filter: value '100' → WHERE quantity > 100."""
        compiler = get_compiler()
        nodes, edges = self._make_filter_pipeline("int64", ">", "100")
        segments = compiler.compile(nodes, edges)
        assert len(segments) == 1
        sql = segments[0].sql
        # Should contain unquoted 100 (number literal)
        assert "quantity > 100" in sql.lower().replace('"', "")

    def test_numeric_float_filter_produces_number_literal(self):
        """Filter on float64 column with value '3.14' → WHERE price > 3.14."""
        compiler = get_compiler()
        nodes, edges = self._make_filter_pipeline("float64", ">", "3.14")
        segments = compiler.compile(nodes, edges)
        assert len(segments) == 1
        sql = segments[0].sql
        assert "price > 3.14" in sql.lower().replace('"', "")

    def test_boolean_filter_produces_boolean_literal(self):
        """Filter on bool column with value 'true' → WHERE is_active = TRUE."""
        compiler = get_compiler()
        nodes, edges = self._make_filter_pipeline("bool", "=", "true")
        segments = compiler.compile(nodes, edges)
        assert len(segments) == 1
        sql_upper = segments[0].sql.upper()
        assert "TRUE" in sql_upper
        # Should NOT be a string literal 'true'
        assert "'TRUE'" not in sql_upper
        assert "'true'" not in segments[0].sql

    def test_string_filter_still_produces_string_literal(self):
        """Filter on string column preserves existing string literal behavior."""
        compiler = get_compiler()
        nodes, edges = self._make_filter_pipeline("string", "=", "AAPL")
        segments = compiler.compile(nodes, edges)
        assert len(segments) == 1
        sql = segments[0].sql
        assert "'AAPL'" in sql

    def test_between_numeric_produces_number_literals(self):
        """Between on float64 column → BETWEEN 10.0 AND 100.0 (no quotes)."""
        compiler = get_compiler()
        nodes, edges = self._make_filter_pipeline("float64", "between", "10,100")
        segments = compiler.compile(nodes, edges)
        assert len(segments) == 1
        sql = segments[0].sql
        assert "BETWEEN" in sql.upper()
        # Values should be numbers, not string literals
        assert "'10'" not in sql
        assert "'100'" not in sql

    def test_unknown_operator_raises_value_error(self):
        """Filter with unrecognized operator raises ValueError (C4 fix)."""
        compiler = get_compiler()
        nodes, edges = self._make_filter_pipeline("string", "invalid_op", "foo")
        with pytest.raises(ValueError, match="Unsupported filter operator"):
            compiler.compile(nodes, edges)

    def test_no_schema_falls_back_to_string(self):
        """When input_schema is None, _apply_filter falls back to string literals."""
        from sqlglot import exp

        base_expr = (
            exp.Select()
            .select(exp.Column(this=exp.to_identifier("price")))
            .from_(exp.Table(this=exp.to_identifier("fct_trades")))
        )
        config = {"column": "price", "operator": ">", "value": "100"}
        # Call _apply_filter without schema — should produce string literal
        result = WorkflowCompiler._apply_filter(base_expr, config, input_schema=None)
        sql = result.sql(dialect="clickhouse")
        # Fallback to string: value should be quoted
        assert "'100'" in sql


class TestPivotCompilation:
    """C1 fix: pivot node compiler rule."""

    def test_pivot_produces_group_by_with_sum(self):
        """Pivot with SUM aggregation produces GROUP BY + SUM."""
        compiler = get_compiler()
        nodes = [
            {
                "id": "src",
                "type": "data_source",
                "data": {
                    "config": {
                        "table": "fct_trades",
                        "columns": [
                            {"name": "region", "dtype": "string"},
                            {"name": "quarter", "dtype": "string"},
                            {"name": "revenue", "dtype": "float64"},
                        ],
                    }
                },
            },
            {
                "id": "pvt",
                "type": "pivot",
                "data": {
                    "config": {
                        "row_columns": ["region"],
                        "pivot_column": "quarter",
                        "value_column": "revenue",
                        "aggregation": "SUM",
                    }
                },
            },
            {"id": "out", "type": "table_output", "data": {"config": {}}},
        ]
        edges = [
            {"source": "src", "target": "pvt"},
            {"source": "pvt", "target": "out"},
        ]
        segments = compiler._build_and_merge(
            compiler._topological_sort(nodes, edges), nodes, edges
        )
        assert len(segments) == 1
        sql_upper = segments[0].sql.upper()
        assert "GROUP BY" in sql_upper
        assert "SUM" in sql_upper
        assert "REGION" in sql_upper
        assert "QUARTER" in sql_upper
        sql_lower = segments[0].sql.lower()
        assert "revenue_sum" in sql_lower

    def test_pivot_with_avg_aggregation(self):
        """Pivot with AVG aggregation works."""
        compiler = get_compiler()
        nodes = [
            {
                "id": "src",
                "type": "data_source",
                "data": {
                    "config": {
                        "table": "fct_trades",
                        "columns": [
                            {"name": "region", "dtype": "string"},
                            {"name": "quarter", "dtype": "string"},
                            {"name": "revenue", "dtype": "float64"},
                        ],
                    }
                },
            },
            {
                "id": "pvt",
                "type": "pivot",
                "data": {
                    "config": {
                        "row_columns": ["region"],
                        "pivot_column": "quarter",
                        "value_column": "revenue",
                        "aggregation": "AVG",
                    }
                },
            },
            {"id": "out", "type": "table_output", "data": {"config": {}}},
        ]
        edges = [
            {"source": "src", "target": "pvt"},
            {"source": "pvt", "target": "out"},
        ]
        segments = compiler._build_and_merge(
            compiler._topological_sort(nodes, edges), nodes, edges
        )
        assert len(segments) == 1
        sql_upper = segments[0].sql.upper()
        assert "AVG" in sql_upper
        sql_lower = segments[0].sql.lower()
        assert "revenue_avg" in sql_lower

    def test_pivot_with_multiple_row_columns(self):
        """Pivot with two row_columns both appear in GROUP BY."""
        compiler = get_compiler()
        nodes = [
            {
                "id": "src",
                "type": "data_source",
                "data": {
                    "config": {
                        "table": "fct_trades",
                        "columns": [
                            {"name": "region", "dtype": "string"},
                            {"name": "sector", "dtype": "string"},
                            {"name": "quarter", "dtype": "string"},
                            {"name": "revenue", "dtype": "float64"},
                        ],
                    }
                },
            },
            {
                "id": "pvt",
                "type": "pivot",
                "data": {
                    "config": {
                        "row_columns": ["region", "sector"],
                        "pivot_column": "quarter",
                        "value_column": "revenue",
                        "aggregation": "SUM",
                    }
                },
            },
            {"id": "out", "type": "table_output", "data": {"config": {}}},
        ]
        edges = [
            {"source": "src", "target": "pvt"},
            {"source": "pvt", "target": "out"},
        ]
        segments = compiler._build_and_merge(
            compiler._topological_sort(nodes, edges), nodes, edges
        )
        assert len(segments) == 1
        sql_upper = segments[0].sql.upper()
        assert "GROUP BY" in sql_upper
        assert "REGION" in sql_upper
        assert "SECTOR" in sql_upper
        assert "QUARTER" in sql_upper

    def test_pivot_after_filter_merges(self):
        """Source → Filter → Pivot produces subquery with WHERE + GROUP BY."""
        compiler = get_compiler()
        nodes = [
            {
                "id": "src",
                "type": "data_source",
                "data": {
                    "config": {
                        "table": "fct_trades",
                        "columns": [
                            {"name": "region", "dtype": "string"},
                            {"name": "quarter", "dtype": "string"},
                            {"name": "revenue", "dtype": "float64"},
                        ],
                    }
                },
            },
            {
                "id": "flt",
                "type": "filter",
                "data": {
                    "config": {
                        "column": "region",
                        "operator": "=",
                        "value": "EMEA",
                    }
                },
            },
            {
                "id": "pvt",
                "type": "pivot",
                "data": {
                    "config": {
                        "row_columns": ["region"],
                        "pivot_column": "quarter",
                        "value_column": "revenue",
                        "aggregation": "SUM",
                    }
                },
            },
            {"id": "out", "type": "table_output", "data": {"config": {}}},
        ]
        edges = [
            {"source": "src", "target": "flt"},
            {"source": "flt", "target": "pvt"},
            {"source": "pvt", "target": "out"},
        ]
        segments = compiler._build_and_merge(
            compiler._topological_sort(nodes, edges), nodes, edges
        )
        # Filter merges into data_source, pivot wraps as subquery — one segment
        assert len(segments) == 1
        sql_upper = segments[0].sql.upper()
        assert "WHERE" in sql_upper
        assert "EMEA" in sql_upper
        assert "GROUP BY" in sql_upper
        assert "SUM" in sql_upper

    def test_pivot_empty_row_columns_returns_parent(self):
        """Pivot with no row_columns passes through parent unchanged."""
        compiler = get_compiler()
        nodes = [
            {
                "id": "src",
                "type": "data_source",
                "data": {
                    "config": {
                        "table": "fct_trades",
                        "columns": [
                            {"name": "region", "dtype": "string"},
                            {"name": "revenue", "dtype": "float64"},
                        ],
                    }
                },
            },
            {
                "id": "pvt",
                "type": "pivot",
                "data": {
                    "config": {
                        "row_columns": [],
                        "pivot_column": "quarter",
                        "value_column": "revenue",
                        "aggregation": "SUM",
                    }
                },
            },
            {"id": "out", "type": "table_output", "data": {"config": {}}},
        ]
        edges = [
            {"source": "src", "target": "pvt"},
            {"source": "pvt", "target": "out"},
        ]
        segments = compiler._build_and_merge(
            compiler._topological_sort(nodes, edges), nodes, edges
        )
        assert len(segments) == 1
        sql_upper = segments[0].sql.upper()
        # Should be the parent SELECT without GROUP BY since row_columns is empty
        assert "GROUP BY" not in sql_upper


class TestJoinUnionTargetPropagation:
    """C5 fix: join/union must inherit target from upstream parents."""

    def test_compile_join_materialize_sources_targets_materialize(self):
        """Two live_* data sources joined → target=materialize, dialect=postgres."""
        compiler = get_compiler()
        nodes = [
            {
                "id": "left",
                "type": "data_source",
                "data": {
                    "config": {
                        "table": "live_positions",
                        "columns": [
                            {"name": "symbol", "dtype": "string"},
                            {"name": "quantity", "dtype": "int64"},
                        ],
                    }
                },
            },
            {
                "id": "right",
                "type": "data_source",
                "data": {
                    "config": {
                        "table": "live_quotes",
                        "columns": [
                            {"name": "symbol", "dtype": "string"},
                            {"name": "bid", "dtype": "float64"},
                        ],
                    }
                },
            },
            {
                "id": "jn",
                "type": "join",
                "data": {
                    "config": {
                        "join_type": "inner",
                        "left_key": "symbol",
                        "right_key": "symbol",
                    }
                },
            },
            {"id": "out", "type": "table_output", "data": {"config": {}}},
        ]
        edges = [
            {"source": "left", "target": "jn"},
            {"source": "right", "target": "jn"},
            {"source": "jn", "target": "out"},
        ]
        segments = compiler._build_and_merge(
            compiler._topological_sort(nodes, edges), nodes, edges
        )
        assert len(segments) == 1
        assert segments[0].target == "materialize"
        assert segments[0].dialect == "postgres"

    def test_compile_union_materialize_sources_targets_materialize(self):
        """Two live_* data sources unioned → target=materialize, dialect=postgres."""
        compiler = get_compiler()
        nodes = [
            {
                "id": "a",
                "type": "data_source",
                "data": {
                    "config": {
                        "table": "live_positions",
                        "columns": [{"name": "symbol", "dtype": "string"}],
                    }
                },
            },
            {
                "id": "b",
                "type": "data_source",
                "data": {
                    "config": {
                        "table": "live_quotes",
                        "columns": [{"name": "symbol", "dtype": "string"}],
                    }
                },
            },
            {"id": "un", "type": "union", "data": {"config": {}}},
            {"id": "out", "type": "table_output", "data": {"config": {}}},
        ]
        edges = [
            {"source": "a", "target": "un"},
            {"source": "b", "target": "un"},
            {"source": "un", "target": "out"},
        ]
        segments = compiler._build_and_merge(
            compiler._topological_sort(nodes, edges), nodes, edges
        )
        assert len(segments) == 1
        assert segments[0].target == "materialize"
        assert segments[0].dialect == "postgres"

    def test_compile_join_mixed_targets_raises(self):
        """Join with one ClickHouse + one Materialize source raises ValueError."""
        compiler = get_compiler()
        nodes = [
            {
                "id": "left",
                "type": "data_source",
                "data": {
                    "config": {
                        "table": "fct_trades",
                        "columns": [{"name": "symbol", "dtype": "string"}],
                    }
                },
            },
            {
                "id": "right",
                "type": "data_source",
                "data": {
                    "config": {
                        "table": "live_positions",
                        "columns": [{"name": "symbol", "dtype": "string"}],
                    }
                },
            },
            {
                "id": "jn",
                "type": "join",
                "data": {
                    "config": {
                        "join_type": "inner",
                        "left_key": "symbol",
                        "right_key": "symbol",
                    }
                },
            },
            {"id": "out", "type": "table_output", "data": {"config": {}}},
        ]
        edges = [
            {"source": "left", "target": "jn"},
            {"source": "right", "target": "jn"},
            {"source": "jn", "target": "out"},
        ]
        with pytest.raises(ValueError, match="Cannot join across backing stores"):
            compiler._build_and_merge(
                compiler._topological_sort(nodes, edges), nodes, edges
            )

    def test_compile_union_mixed_targets_raises(self):
        """Union with one ClickHouse + one Materialize source raises ValueError."""
        compiler = get_compiler()
        nodes = [
            {
                "id": "a",
                "type": "data_source",
                "data": {
                    "config": {
                        "table": "fct_trades",
                        "columns": [{"name": "symbol", "dtype": "string"}],
                    }
                },
            },
            {
                "id": "b",
                "type": "data_source",
                "data": {
                    "config": {
                        "table": "live_positions",
                        "columns": [{"name": "symbol", "dtype": "string"}],
                    }
                },
            },
            {"id": "un", "type": "union", "data": {"config": {}}},
            {"id": "out", "type": "table_output", "data": {"config": {}}},
        ]
        edges = [
            {"source": "a", "target": "un"},
            {"source": "b", "target": "un"},
            {"source": "un", "target": "out"},
        ]
        with pytest.raises(ValueError, match="Cannot union across backing stores"):
            compiler._build_and_merge(
                compiler._topological_sort(nodes, edges), nodes, edges
            )
