"""Formula Parser — bracket [column] syntax -> AST -> SQL.

Parses the expression grammar used in Formula nodes:
  expression  = term (('+' | '-') term)*
  term        = factor (('*' | '/') factor)*
  factor      = NUMBER | STRING | COLUMN_REF | function_call | '(' expression ')'
  COLUMN_REF  = '[' column_name ']'
  function    = FUNC_NAME '(' expression (',' expression)* ')'

Compiles to SQL via SQLGlot, handling dialect differences between
ClickHouse and Materialize/PG.
"""

import logging
from dataclasses import dataclass
from enum import Enum, auto

import sqlglot
from sqlglot import exp

from app.schemas.schema import ColumnSchema

logger = logging.getLogger(__name__)


class TokenType(Enum):
    NUMBER = auto()
    STRING = auto()
    COLUMN_REF = auto()
    FUNCTION = auto()
    OPERATOR = auto()
    LPAREN = auto()
    RPAREN = auto()
    COMMA = auto()
    EOF = auto()


@dataclass
class Token:
    type: TokenType
    value: str
    position: int


@dataclass
class ParseError:
    message: str
    position: int


class FormulaParser:
    """Parse and compile formula expressions to SQL."""

    # Available functions by category
    FUNCTIONS = {
        # Math
        "ABS", "ROUND", "CEIL", "FLOOR", "MOD", "POWER", "SQRT", "LOG",
        # Text
        "UPPER", "LOWER", "TRIM", "LEFT", "RIGHT", "LENGTH", "CONCAT",
        "REPLACE", "CONTAINS",
        # Date
        "YEAR", "MONTH", "DAY", "HOUR", "MINUTE", "DATE_DIFF", "DATE_ADD", "NOW",
        # Logic
        "IF", "CASE", "COALESCE", "NULLIF",
        # Aggregate (only inside Group By context)
        "SUM", "AVG", "COUNT", "MIN", "MAX", "MEDIAN", "STDDEV",
        # Window (only with Sort defined)
        "LAG", "LEAD", "ROW_NUMBER", "RANK", "RUNNING_TOTAL",
    }

    def parse(self, expression: str) -> list[Token]:
        """Tokenize a formula expression.

        Returns tokens or raises ValueError with position info.
        """
        tokens: list[Token] = []
        i = 0

        while i < len(expression):
            ch = expression[i]

            if ch.isspace():
                i += 1
                continue

            if ch == "[":
                end = expression.index("]", i + 1)
                col_name = expression[i + 1 : end]
                tokens.append(Token(TokenType.COLUMN_REF, col_name, i))
                i = end + 1
            elif ch.isdigit() or (ch == "." and i + 1 < len(expression) and expression[i + 1].isdigit()):
                j = i
                while j < len(expression) and (expression[j].isdigit() or expression[j] == "."):
                    j += 1
                tokens.append(Token(TokenType.NUMBER, expression[i:j], i))
                i = j
            elif ch in "+-*/":
                tokens.append(Token(TokenType.OPERATOR, ch, i))
                i += 1
            elif ch == "(":
                tokens.append(Token(TokenType.LPAREN, "(", i))
                i += 1
            elif ch == ")":
                tokens.append(Token(TokenType.RPAREN, ")", i))
                i += 1
            elif ch == ",":
                tokens.append(Token(TokenType.COMMA, ",", i))
                i += 1
            elif ch == '"' or ch == "'":
                j = i + 1
                while j < len(expression) and expression[j] != ch:
                    j += 1
                tokens.append(Token(TokenType.STRING, expression[i + 1 : j], i))
                i = j + 1
            elif ch.isalpha() or ch == "_":
                j = i
                while j < len(expression) and (expression[j].isalnum() or expression[j] == "_"):
                    j += 1
                word = expression[i:j]
                if word.upper() in self.FUNCTIONS:
                    tokens.append(Token(TokenType.FUNCTION, word.upper(), i))
                else:
                    raise ValueError(f"Unknown identifier '{word}' at position {i}")
                i = j
            else:
                raise ValueError(f"Unexpected character '{ch}' at position {i}")

        tokens.append(Token(TokenType.EOF, "", len(expression)))
        return tokens

    def validate_columns(
        self,
        expression: str,
        available_columns: list[ColumnSchema],
    ) -> list[ParseError]:
        """Validate that all column references exist in the input schema."""
        errors: list[ParseError] = []
        available_names = {col.name for col in available_columns}

        try:
            tokens = self.parse(expression)
        except ValueError as e:
            errors.append(ParseError(message=str(e), position=0))
            return errors

        for token in tokens:
            if token.type == TokenType.COLUMN_REF and token.value not in available_names:
                errors.append(
                    ParseError(
                        message=f"Unknown column: [{token.value}]",
                        position=token.position,
                    )
                )

        return errors

    def compile_to_sql(
        self,
        expression: str,
        dialect: str = "clickhouse",
    ) -> str:
        """Compile a formula expression to SQL for the given dialect.

        Uses SQLGlot for dialect-aware compilation.
        """
        # TODO: Build proper AST from tokens and convert to SQLGlot expressions
        # For now, do simple bracket replacement
        sql = expression
        tokens = self.parse(expression)

        # Replace column refs: [col_name] -> col_name
        for token in reversed(
            [t for t in tokens if t.type == TokenType.COLUMN_REF]
        ):
            start = token.position
            end = start + len(token.value) + 2  # +2 for brackets
            sql = sql[:start] + token.value + sql[end:]

        # Handle IF -> CASE WHEN translation
        # TODO: Proper AST-based compilation

        return sqlglot.transpile(sql, read=dialect, write=dialect)[0]
