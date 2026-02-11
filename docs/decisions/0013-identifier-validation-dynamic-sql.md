# ADR 0013: Identifier Validation for Dynamic SQL

- **Status:** Accepted
- **Date:** 2026-02-11
- **Deciders:** Security audit team

## Context

ADR 0001 mandates all SQL generation via SQLGlot AST, but certain database
commands are not representable as SQLGlot expressions. Materialize's
`SUBSCRIBE TO <view>` is proprietary streaming syntax with no SQLGlot node
type. The `materialize.py` client was interpolating `view_name` directly into
an f-string without validation — a SQL injection vector if the view name
originated from user-controlled input (e.g. widget configuration).

We needed a safe escape hatch for the small set of cases where SQLGlot
cannot generate the statement.

## Decision

Validate dynamic SQL identifiers with a strict regex **before** interpolation:

```python
_VALID_VIEW_NAME = re.compile(
    r"^[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)?$"
)
```

Rules:
1. Only letters, digits, and underscores are permitted.
2. A single dot separator is allowed for `schema.name` qualification.
3. Validation raises `ValueError` immediately — the query never executes.
4. A comment at the interpolation site must explain why it is safe.

Implemented in `backend/app/core/materialize.py` (`subscribe()`).

## Alternatives Considered

- **Allowlist of known views** — too rigid; views are created by external
  ingestion pipelines and the set changes without code deploys.
- **SQLGlot `exp.Column` / `exp.Identifier` quoting** — SQLGlot can quote
  identifiers, but `SUBSCRIBE TO` is not a parseable statement in any
  supported dialect, so we would still need string assembly.
- **asyncpg parameterized identifiers** — PostgreSQL/Materialize parameters
  (`$1`) only work for values, not identifiers. `SUBSCRIBE TO $1` is a
  syntax error.

## Consequences

**Positive:**
- Eliminates injection risk for Materialize streaming queries.
- Regex is simple to audit and test (`test_materialize.py` covers valid and
  malicious inputs).
- Pattern is reusable for any future non-SQLGlot SQL (e.g. `COPY`,
  `CLUSTER`).

**Negative:**
- Identifiers with special characters (spaces, hyphens) are rejected. This
  is acceptable because our naming convention already forbids them.
- Each new non-SQLGlot statement site requires its own validation call —
  developers must remember to add it. The RFC 0004 reviewer checklist
  mitigates this.
