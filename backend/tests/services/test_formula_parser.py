"""Formula parser tests — expression parsing, column validation, SQL compilation."""

import pytest

from app.schemas.schema import ColumnSchema
from app.services.formula_parser import FormulaParser

COLUMNS = [
    ColumnSchema(name="price", dtype="float64", nullable=True),
    ColumnSchema(name="quantity", dtype="int64", nullable=True),
    ColumnSchema(name="revenue", dtype="float64", nullable=True),
    ColumnSchema(name="cost", dtype="float64", nullable=True),
]


class TestTokenization:
    def test_simple_arithmetic(self):
        parser = FormulaParser()
        tokens = parser.parse("[price] * [quantity]")
        column_refs = [t for t in tokens if t.type.name == "COLUMN_REF"]
        assert len(column_refs) == 2
        assert column_refs[0].value == "price"
        assert column_refs[1].value == "quantity"

    def test_function_call(self):
        parser = FormulaParser()
        tokens = parser.parse("ROUND([price] * [quantity], 2)")
        funcs = [t for t in tokens if t.type.name == "FUNCTION"]
        assert len(funcs) == 1
        assert funcs[0].value == "ROUND"

    def test_unknown_identifier_raises(self):
        parser = FormulaParser()
        with pytest.raises(ValueError, match="Unknown identifier"):
            parser.parse("foo + [price]")


class TestColumnValidation:
    def test_valid_columns_no_errors(self):
        parser = FormulaParser()
        errors = parser.validate_columns("[price] * [quantity]", COLUMNS)
        assert errors == []

    def test_unknown_column_returns_error(self):
        parser = FormulaParser()
        errors = parser.validate_columns("[price] * [unknown_col]", COLUMNS)
        assert len(errors) == 1
        assert "unknown_col" in errors[0].message


class TestSQLCompilation:
    def test_simple_expression_compiles(self):
        parser = FormulaParser()
        sql = parser.compile_to_sql("[revenue] - [cost]", dialect="clickhouse")
        assert "revenue" in sql
        assert "cost" in sql

    def test_compile_arithmetic_to_sql(self):
        parser = FormulaParser()
        sql = parser.compile_to_sql("[revenue] - [cost]")
        assert "revenue" in sql
        assert "cost" in sql
        assert "-" in sql

    def test_compile_function_call(self):
        parser = FormulaParser()
        sql = parser.compile_to_sql("ROUND([price] * [quantity], 2)")
        sql_upper = sql.upper()
        assert "ROUND" in sql_upper
        assert "2" in sql

    def test_compile_if_expression(self):
        parser = FormulaParser()
        sql = parser.compile_to_sql('IF([quantity] > 1000, "large", "small")')
        sql_upper = sql.upper()
        # IF compiles to CASE WHEN in most SQL dialects
        assert "CASE" in sql_upper or "IF" in sql_upper
        assert "1000" in sql

    def test_compile_nested_arithmetic(self):
        parser = FormulaParser()
        sql = parser.compile_to_sql("([price] + [cost]) * [quantity]")
        assert "+" in sql
        assert "*" in sql

    def test_compile_comparison_operators(self):
        parser = FormulaParser()
        for op, expected in [
            (">", ">"),
            ("<", "<"),
            (">=", ">="),
            ("<=", "<="),
        ]:
            sql = parser.compile_to_sql(f"[price] {op} 100")
            assert expected in sql

    def test_compile_division(self):
        parser = FormulaParser()
        sql = parser.compile_to_sql("[revenue] / 1000")
        assert "/" in sql
        assert "1000" in sql

    def test_compile_coalesce(self):
        parser = FormulaParser()
        sql = parser.compile_to_sql("COALESCE([price], 0)")
        assert "COALESCE" in sql.upper()

    def test_compile_string_literal(self):
        parser = FormulaParser()
        sql = parser.compile_to_sql('IF([price] > 100, "high", "low")')
        sql_upper = sql.upper()
        assert "CASE" in sql_upper or "IF" in sql_upper
