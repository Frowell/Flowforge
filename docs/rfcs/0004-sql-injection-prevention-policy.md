# RFC 0004: SQL Injection Prevention Policy

- **Status:** Accepted
- **Author:** Security audit team
- **Date:** 2026-02-11

## Summary

This RFC establishes a mandatory SQL injection prevention policy after a
security audit discovered four critical vulnerabilities in the backend. All
four have been fixed (commit `31e0e24`), but without codified rules and
reviewer guidance the same patterns will recur as the codebase grows.

## Motivation

The audit found two categories of vulnerability:

**Category A — Raw SQL interpolation of user input (3 instances):**

1. `preview_service.py` — f-string `LIMIT {limit} OFFSET {offset}` wrapping
   of compiled SQL. An attacker controlling pagination parameters could
   inject arbitrary SQL into ClickHouse queries.
2. `widget_data_service.py` — identical f-string LIMIT/OFFSET pattern for
   widget data queries, same injection vector.
3. `materialize.py` — `SUBSCRIBE TO {view_name}` with no validation of
   `view_name`. A crafted view name could execute arbitrary Materialize
   commands.

**Category B — Insecure production defaults (1 instance):**

4. `config.py` — `secret_key` defaulted to `"dev-secret-change-in-prod"`.
   Combined with `VITE_DEV_AUTH=true`, this bypassed authentication
   entirely. If deployed without an explicit secret, any request had full
   tenant access.

All four violate [ADR 0001](../decisions/0001-sqlglot-over-dataframes.md)'s
intent (SQL via SQLGlot, never string concatenation) and the multi-tenancy
isolation rules in `docs/multi-tenancy.md`.

## Detailed Design

### Rule 1: All Query SQL via SQLGlot AST

Every SQL query — including wrappers for LIMIT, OFFSET, ORDER BY, and
subqueries — must be built using SQLGlot's expression API.

**Correct** (SQLGlot builds the full query):
```python
inner = sqlglot.parse_one(segment.sql, dialect=dialect)
wrapped = (
    sqlglot.select("*")
    .from_(inner.subquery("preview"))
    .limit(int(limit))
    .offset(int(offset))
)
constrained_sql = wrapped.sql(dialect=dialect)
```

**Incorrect** (f-string interpolation of user-controlled values):
```python
# NEVER DO THIS — limit/offset may originate from query parameters
sql = f"SELECT * FROM ({segment.sql}) AS t LIMIT {limit} OFFSET {offset}"
```

**Applies to:**
- `backend/app/services/preview_service.py` (`_wrap_with_constraints`)
- `backend/app/services/widget_data_service.py` (`get_widget_data`)
- `backend/app/services/workflow_compiler.py` (all query assembly)
- Any future service that builds or wraps SQL

**Exception:** Module-level integer constants (e.g. ClickHouse `SETTINGS
max_execution_time=30`) may be appended via f-string because they are not
user-controlled. Each such site must include a comment explaining why.

### Rule 2: Dynamic Identifiers Validated via Strict Regex

When SQLGlot cannot represent a statement (e.g. Materialize `SUBSCRIBE TO`),
identifiers must be validated with the following regex before interpolation:

```python
_VALID_IDENTIFIER = re.compile(
    r"^[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)?$"
)
```

The interpolation site must include an inline comment citing this validation.
See [ADR 0013](../decisions/0013-identifier-validation-dynamic-sql.md) for
the full rationale and alternatives considered.

**Applies to:**
- `backend/app/core/materialize.py` (`subscribe()`)
- Any future non-standard SQL command (e.g. `COPY`, `CLUSTER`, `CREATE
  SUBSCRIPTION`)

### Rule 3: Production Configuration Guards

Sensitive configuration values that have insecure development defaults must
include a `@model_validator` that refuses startup in non-development
environments. See
[ADR 0014](../decisions/0014-production-configuration-safety-guards.md).

**Applies to:**
- `backend/app/core/config.py` (`Settings`)
- Any future configuration class with security-sensitive defaults

## PR Reviewer Checklist

Every PR that touches SQL generation or configuration must verify:

- [ ] **No f-string/format SQL with external input.** Search for `f"` and
  `.format(` in any file that imports `sqlglot` or touches SQL strings.
- [ ] **LIMIT/OFFSET via SQLGlot.** Pagination must use `.limit()` and
  `.offset()` on a SQLGlot expression, not string interpolation.
- [ ] **Dynamic identifiers validated.** Any identifier interpolated into
  SQL has a regex check or allowlist gate _before_ the f-string.
- [ ] **No new dev defaults for secrets.** Config values that control auth,
  encryption, or API keys must not have usable defaults outside development.
- [ ] **`int()` cast on numeric SQL values.** Even when using SQLGlot,
  explicit `int()` casts on limit/offset prevent type-confusion bugs.
- [ ] **Inline safety comments.** Every non-SQLGlot interpolation site has
  a comment explaining why it is safe.

## Alternatives Considered

- **ORM-only approach (SQLAlchemy Core for all queries)** — FlowForge
  compiles user-defined workflows to SQL across multiple dialects.
  SQLAlchemy's dialect support does not cover ClickHouse or Materialize
  adequately. SQLGlot was chosen in ADR 0001 for exactly this reason.
- **WAF / query firewall** — adds latency and false positives. Defense in
  depth is valuable but does not replace secure code.
- **Automated SAST in CI** — complements this policy but cannot catch all
  semantic injection patterns (e.g. the Materialize `SUBSCRIBE` case).
  Recommended as a future addition, not a replacement.

## Open Questions

- ~~Should we add a Ruff custom rule for f-string SQL?~~ Resolved: too many
  false positives. The reviewer checklist is sufficient for now; revisit if
  the team grows past 10 contributors.
- ~~Should `SETTINGS` constants also use SQLGlot?~~ Resolved: no. ClickHouse
  `SETTINGS` is a non-standard clause. Module-level `int` constants are safe
  and the comment requirement makes intent explicit.

## Implementation

- SQL injection fixes (Rules 1 & 2): commit `31e0e24`, PR #42
- Production config guard (Rule 3): same commit
- Identifier validation rationale: [ADR 0013](../decisions/0013-identifier-validation-dynamic-sql.md)
- Production guard rationale: [ADR 0014](../decisions/0014-production-configuration-safety-guards.md)
