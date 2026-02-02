# Tests — Agent Rules

> Parent rules: [`/workspace/backend/agents.md`](../agents.md) | Architecture: [`/workspace/planning.md`](../../planning.md)

## Structure

Test directory mirrors `app/`:

```
tests/
├── api/           # Route handler integration tests
└── services/      # Service unit tests
```

## Test Client

Use `httpx.AsyncClient` for API integration tests with the FastAPI test client pattern:

```python
async with AsyncClient(app=app, base_url="http://test") as client:
    response = await client.post("/api/v1/workflows", json={...})
```

## Naming Convention

```
test_<action>_<condition>_<expected>
```

Examples:
- `test_create_workflow_valid_returns_201`
- `test_compile_workflow_missing_source_raises_validation_error`
- `test_query_router_live_table_dispatches_to_materialize`

## Key Test Areas

| Area | What to test |
|---|---|
| Workflow compiler | Query merging — verify adjacent nodes produce single queries, not one-per-node |
| Schema engine | Transform functions — verify output schemas match expected for each node type |
| Formula parser | Expression parsing — arithmetic, functions, conditionals, column validation |
| Query router | Freshness routing — correct dispatch to ClickHouse / Materialize / Redis |
| API routes | Request validation, auth enforcement, correct status codes |

## Mocking

- **Always** mock external stores (ClickHouse, Materialize, Redis). Tests must never require running instances.
- Use factory functions to create test data (workflows, dashboards, widgets). Avoid deep pytest fixture chains.
- Mock at the service boundary when testing routes; mock at the client boundary when testing services.

## Pytest Configuration

- `asyncio_mode = "auto"` — all async tests run automatically without explicit markers.
- Fixtures provide a test database session (PostgreSQL) with transaction rollback per test.

## Multi-Tenancy Test Requirements

### Tenant Fixtures

- Test fixtures must provide at least **two distinct tenants** (`tenant_a`, `tenant_b`) with separate UUIDs.
- Each tenant fixture creates its own users, workflows, and dashboards.
- A `mock_tenant_auth` fixture overrides `get_current_tenant_id` to return a specific tenant UUID for the test.

### Required Isolation Tests

Every tenant-scoped route MUST have tests verifying:

1. **List isolation**: `GET /workflows` for tenant A returns only tenant A's workflows — never tenant B's.
2. **Get isolation**: `GET /workflows/{id}` returns 404 (not 403) when the workflow belongs to a different tenant. This prevents attackers from distinguishing "exists but forbidden" from "does not exist."
3. **Create scoping**: `POST /workflows` sets `tenant_id` from auth context, not from request body.
4. **Update isolation**: `PATCH /workflows/{id}` returns 404 for cross-tenant IDs.
5. **Delete isolation**: `DELETE /workflows/{id}` returns 404 for cross-tenant IDs.
6. **Cross-tenant references**: Creating a widget that references a workflow from a different tenant must fail.

### Cache Isolation Tests

- Preview cache tests must verify that tenant A's cached result is NOT returned for tenant B's identical query.

### Test Naming for Tenant Tests

```
test_list_workflows_filters_by_tenant
test_get_workflow_different_tenant_returns_404
test_create_widget_cross_tenant_workflow_fails
test_preview_cache_isolated_by_tenant
```
