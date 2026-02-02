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
