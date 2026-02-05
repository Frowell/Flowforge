# Multi-Tenancy Guide

> Parent: [`/workspace/agents.md`](../agents.md) | Architecture: [`/workspace/Application plan.md`](../Application%20plan.md)

FlowForge is **multi-tenant from day one**. Every tenant-scoped resource is isolated by a `tenant_id` UUID column. Tenant identity is derived from Keycloak JWT claims — never from client-supplied headers or URL parameters.

---

## 10 Core Rules

1. **Tenant ID comes from the JWT.** The backend extracts `tenant_id` from a custom Keycloak claim (`tenant_id` or group mapping). The `get_current_tenant_id()` dependency in `api/deps.py` is the single source of truth. Never accept tenant ID from request bodies, query params, or custom headers.

2. **Every query filters by tenant.** All `SELECT`, `UPDATE`, and `DELETE` queries on tenant-scoped tables (`users`, `workflows`, `dashboards`, `api_keys`) MUST include a `WHERE tenant_id = :tenant_id` clause. A missing tenant filter is a **data leak bug**. Use the `TenantMixin` on all scoped models.

3. **Tenant-scoped models.** These models carry a `tenant_id` column: `User`, `Workflow`, `Dashboard`, `APIKey`. Child models (`Widget`, `DashboardFilter`) inherit tenant scope from their parent `Dashboard` — no separate `tenant_id` column, but cross-tenant references are prevented by the parent's tenant check.

4. **Cross-tenant references are forbidden.** When creating a `Widget`, the route MUST verify that both the target `Dashboard` and the source `Workflow` belong to the same tenant. A widget must never point to a workflow owned by a different tenant.

5. **Cache keys include tenant.** The preview cache key (`preview_service.py`) MUST include `tenant_id` in its hash. Without it, tenant A could see tenant B's cached preview results.

6. **Compiled SQL includes tenant isolation.** Serving-layer tables contain shared market data (no `tenant_id` column). Tenant isolation is enforced via **symbol-based access control**: the workflow compiler injects `WHERE symbol IN (:allowed_symbols)` using the tenant's symbol ACL from the schema registry. This is enforced at the compiler level, not at the route level. PostgreSQL app metadata uses standard `tenant_id` column filtering.

7. **WebSocket channels are tenant-scoped.** Redis pub/sub channel names MUST include `tenant_id` so execution status updates and live data pushes never leak across tenants.

8. **API keys are tenant-scoped.** The `api_keys` table includes `tenant_id`. An API key can only access widgets belonging to dashboards in the same tenant.

9. **Schema catalog is tenant-scoped.** Different tenants may have access to different serving-layer tables. The schema registry caches catalogs per tenant.

10. **PostgreSQL RLS is defense-in-depth.** Row-level security policies on tenant-scoped tables provide a database-level safety net. Application-level filtering is the primary mechanism; RLS is the backstop.

---

## Tenant Dependency Pattern

```python
# In api/deps.py — the canonical way to get tenant context
async def get_current_tenant_id(request: Request) -> UUID:
    claims = await get_current_user_claims(request)
    tenant_id = claims.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=403, detail="No tenant claim in token")
    return UUID(tenant_id)

# In route handlers — always inject tenant_id
@router.get("")
async def list_workflows(
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    q = select(Workflow).where(Workflow.tenant_id == tenant_id)
    ...
```

---

## Tenant Context in Services

Services that interact with external stores or caching must receive `tenant_id`:

| Service | Tenant Usage |
|---------|-------------|
| **PreviewService** | Cache keys MUST include `tenant_id` to prevent cross-tenant cache leaks |
| **WorkflowCompiler** | Compiled SQL MUST inject `WHERE symbol IN (:allowed_symbols)` for serving-layer market data tables |
| **SchemaRegistry** | Catalog is cached per tenant (different tenants may see different tables) |
| **WebSocketManager** | Pub/sub channels are prefixed with `tenant_id` |

---

## Cross-Tenant Reference Prevention

When creating a `Widget`, verify that BOTH the target `Dashboard` AND the source `Workflow` belong to the caller's tenant. Never allow a widget to reference a workflow from a different tenant.

```python
# CORRECT — verify both resources share the same tenant
dashboard = await db.get(Dashboard, dashboard_id)
if dashboard.tenant_id != tenant_id:
    raise HTTPException(status_code=404)

workflow = await db.get(Workflow, body.source_workflow_id)
if workflow.tenant_id != tenant_id:
    raise HTTPException(status_code=404)  # 404 not 403 — prevents enumeration
```

---

## Route Handler Patterns

```python
# CORRECT — tenant-filtered list
@router.get("")
async def list_workflows(
    tenant_id: UUID = Depends(get_current_tenant_id),
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    q = select(Workflow).where(Workflow.tenant_id == tenant_id)
    ...

# CORRECT — tenant-checked single-item fetch (prevents IDOR)
@router.get("/{workflow_id}")
async def get_workflow(
    workflow_id: UUID,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Workflow).where(
            Workflow.id == workflow_id,
            Workflow.tenant_id == tenant_id,  # REQUIRED
        )
    )

# WRONG — no tenant filter (data leak!)
@router.get("/{workflow_id}")
async def get_workflow(workflow_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))  # NO
```
