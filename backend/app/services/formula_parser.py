"""Formula Parser — bracket [column] syntax -> AST -> SQL.

Parses the expression grammar used in Formula nodes:
  expression  = comparison ((AND | OR) comparison)*
  comparison  = term (('>' | '<' | '>=' | '<=' | '=' | '!=') term)?
  term        = factor (('+' | '-') factor)*
  factor      = unary (('*' | '/') unary)*
  unary       = '-' unary | atom
  atom        = NUMBER | STRING | COLUMN_REF | function_call | '(' expression ')'
  COLUMN_REF  = '[' column_name ']'
  function    = FUNC_NAME '(' expression (',' expression)* ')'

Compiles to SQL via SQLGlot, handling dialect differences between
ClickHouse and Materialize/PG.
"""

import logging
from dataclasses import dataclass
from enum import Enum, auto

from sqlglot import exp

from app.schemas.schema import ColumnSchema

logger = logging.getLogger(__name__)


class TokenType(Enum):
    NUMBER = auto()
    STRING = auto()
    COLUMN_REF = auto()
    FUNCTION = auto()
    OPERATOR = auto()
    COMPARISON = auto()
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

    COMPARISON_OPS = {">=", "<=", "!=", ">", "<", "="}

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
            elif ch in "><=!":
                # Two-char comparison operators
                two_char = expression[i : i + 2]
                if two_char in (">=", "<=", "!="):
                    tokens.append(Token(TokenType.COMPARISON, two_char, i))
                    i += 2
                elif ch in "><":
                    tokens.append(Token(TokenType.COMPARISON, ch, i))
                    i += 1
                elif ch == "=":
                    tokens.append(Token(TokenType.COMPARISON, "=", i))
                    i += 1
                else:
                    raise ValueError(f"Unexpected character '{ch}' at position {i}")
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

        Uses SQLGlot for dialect-aware compilation via recursive descent parsing.
        """
        self._tokens = self.parse(expression)
        self._pos = 0
        ast = self._parse_expression()
        return ast.sql(dialect=dialect)

    def compile_to_expression(
        self,
        expression: str,
    ) -> exp.Expression:
        """Compile a formula expression to a SQLGlot Expression AST node."""
        self._tokens = self.parse(expression)
        self._pos = 0
        return self._parse_expression()

    # ---- Recursive descent parser producing SQLGlot AST ----

    def _current(self) -> Token:
        return self._tokens[self._pos]

    def _advance(self) -> Token:
        token = self._tokens[self._pos]
        self._pos += 1
        return token

    def _expect(self, token_type: TokenType, value: str | None = None) -> Token:
        token = self._current()
        if token.type != token_type:
            raise ValueError(
                f"Expected {token_type.name} but got {token.type.name} at position {token.position}"
            )
        if value is not None and token.value != value:
            raise ValueError(
                f"Expected '{value}' but got '{token.value}' at position {token.position}"
            )
        return self._advance()

    def _parse_expression(self) -> exp.Expression:
        """expression = comparison"""
        return self._parse_comparison()

    def _parse_comparison(self) -> exp.Expression:
        """comparison = term (('>' | '<' | '>=' | '<=' | '=' | '!=') term)?"""
        left = self._parse_term()

        if self._current().type == TokenType.COMPARISON:
            op_token = self._advance()
            right = self._parse_term()

            op_map = {
                ">": exp.GT,
                "<": exp.LT,
                ">=": exp.GTE,
                "<=": exp.LTE,
                "=": exp.EQ,
                "!=": exp.NEQ,
            }
            op_class = op_map[op_token.value]
            return op_class(this=left, expression=right)

        return left

    def _parse_term(self) -> exp.Expression:
        """term = factor (('+' | '-') factor)*"""
        left = self._parse_factor()

        while (
            self._current().type == TokenType.OPERATOR
            and self._current().value in ("+", "-")
        ):
            op_token = self._advance()
            right = self._parse_factor()
            if op_token.value == "+":
                left = exp.Add(this=left, expression=right)
            else:
                left = exp.Sub(this=left, expression=right)

        return left

    def _parse_factor(self) -> exp.Expression:
        """factor = unary (('*' | '/') unary)*"""
        left = self._parse_unary()

        while (
            self._current().type == TokenType.OPERATOR
            and self._current().value in ("*", "/")
        ):
            op_token = self._advance()
            right = self._parse_unary()
            if op_token.value == "*":
                left = exp.Mul(this=left, expression=right)
            else:
                left = exp.Div(this=left, expression=right)

        return left

    def _parse_unary(self) -> exp.Expression:
        """unary = '-' unary | atom"""
        if (
            self._current().type == TokenType.OPERATOR
            and self._current().value == "-"
        ):
            self._advance()
            operand = self._parse_unary()
            return exp.Neg(this=operand)

        return self._parse_atom()

    def _parse_atom(self) -> exp.Expression:
        """atom = NUMBER | STRING | COLUMN_REF | function_call | '(' expression ')'"""
        token = self._current()

        if token.type == TokenType.NUMBER:
            self._advance()
            return exp.Literal.number(token.value)

        if token.type == TokenType.STRING:
            self._advance()
            return exp.Literal.string(token.value)

        if token.type == TokenType.COLUMN_REF:
            self._advance()
            return exp.Column(this=exp.to_identifier(token.value))

        if token.type == TokenType.FUNCTION:
            return self._parse_function_call()

        if token.type == TokenType.LPAREN:
            self._advance()
            inner = self._parse_expression()
            self._expect(TokenType.RPAREN)
            return exp.Paren(this=inner)

        raise ValueError(
            f"Unexpected token {token.type.name} '{token.value}' at position {token.position}"
        )

    def _parse_function_call(self) -> exp.Expression:
        """function_call = FUNC_NAME '(' expression (',' expression)* ')'"""
        func_token = self._advance()  # consume function name
        func_name = func_token.value

        self._expect(TokenType.LPAREN)

        args: list[exp.Expression] = []
        if self._current().type != TokenType.RPAREN:
            args.append(self._parse_expression())
            while self._current().type == TokenType.COMMA:
                self._advance()
                args.append(self._parse_expression())

        self._expect(TokenType.RPAREN)

        # Special handling for IF -> exp.If (compiles to CASE WHEN)
        if func_name == "IF":
            if len(args) < 2:
                raise ValueError(f"IF requires at least 2 arguments at position {func_token.position}")
            return exp.If(
                this=args[0],
                true=args[1],
                false=args[2] if len(args) > 2 else exp.Null(),
            )

        # Special handling for COALESCE
        if func_name == "COALESCE":
            return exp.Coalesce(this=args[0], expressions=args[1:])

        # Special handling for NULLIF
        if func_name == "NULLIF":
            return exp.Nullif(this=args[0], expression=args[1])

        # All other functions -> exp.Anonymous
        return exp.Anonymous(this=func_name, expressions=args)
