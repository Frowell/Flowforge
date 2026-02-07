"""Workflow export/import endpoint tests."""

from uuid import UUID

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_user_claims
from app.main import app
from app.models.audit_log import AuditAction, AuditLog
from app.models.workflow import Workflow


def _make_claims(user_id: UUID, tenant_id: UUID, role: str = "analyst"):
    async def _claims():
        return {
            "sub": str(user_id),
            "tenant_id": str(tenant_id),
            "realm_access": {"roles": [role]},
            "resource_access": {},
        }

    return _claims


async def _create_workflow(
    db_session: AsyncSession, tenant_id: UUID, user_id: UUID, name: str = "Test WF"
) -> Workflow:
    wf = Workflow(
        name=name,
        description="A test workflow",
        tenant_id=tenant_id,
        created_by=user_id,
        graph_json={
            "nodes": [
                {
                    "id": "src-1",
                    "type": "data_source",
                    "data": {"config": {"table": "trades"}},
                },
                {
                    "id": "flt-1",
                    "type": "filter",
                    "data": {"config": {"column": "symbol", "operator": "=", "value": "AAPL"}},
                },
            ],
            "edges": [
                {"id": "e1", "source": "src-1", "target": "flt-1"},
            ],
        },
    )
    db_session.add(wf)
    await db_session.commit()
    await db_session.refresh(wf)
    return wf


async def test_export_workflow_returns_structure(
    client: AsyncClient,
    db_session: AsyncSession,
    mock_auth,
    seed_user_a,
    tenant_id: UUID,
    user_id: UUID,
):
    """GET /{id}/export returns correctly structured export payload."""
    app.dependency_overrides[get_user_claims] = _make_claims(user_id, tenant_id)
    try:
        wf = await _create_workflow(db_session, tenant_id, user_id)
        response = await client.get(f"/api/v1/workflows/{wf.id}/export")
        assert response.status_code == 200
        data = response.json()

        assert "metadata" in data
        assert data["metadata"]["version"] == "1.0"
        assert data["metadata"]["source_workflow_id"] == str(wf.id)
        assert "exported_at" in data["metadata"]
        assert data["name"] == "Test WF"
        assert data["description"] == "A test workflow"
        assert "graph_json" in data
        assert len(data["graph_json"]["nodes"]) == 2
    finally:
        app.dependency_overrides.pop(get_user_claims, None)


async def test_export_workflow_cross_tenant_returns_404(
    client: AsyncClient,
    db_session: AsyncSession,
    mock_auth,
    seed_user_a,
    seed_user_b,
    tenant_id: UUID,
    user_id: UUID,
    tenant_id_b: UUID,
    user_id_b: UUID,
):
    """Exporting a workflow from another tenant returns 404."""
    app.dependency_overrides[get_user_claims] = _make_claims(user_id, tenant_id)
    try:
        wf = await _create_workflow(db_session, tenant_id_b, user_id_b, "Other Tenant WF")
        response = await client.get(f"/api/v1/workflows/{wf.id}/export")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.pop(get_user_claims, None)


async def test_export_workflow_logs_audit_event(
    client: AsyncClient,
    db_session: AsyncSession,
    mock_auth,
    seed_user_a,
    tenant_id: UUID,
    user_id: UUID,
):
    """Export creates an audit log entry with EXPORTED action."""
    app.dependency_overrides[get_user_claims] = _make_claims(user_id, tenant_id)
    try:
        wf = await _create_workflow(db_session, tenant_id, user_id)
        response = await client.get(f"/api/v1/workflows/{wf.id}/export")
        assert response.status_code == 200

        result = await db_session.execute(
            select(AuditLog).where(
                AuditLog.resource_id == wf.id,
                AuditLog.action == AuditAction.EXPORTED,
            )
        )
        audit = result.scalar_one_or_none()
        assert audit is not None
        assert audit.tenant_id == tenant_id
    finally:
        app.dependency_overrides.pop(get_user_claims, None)


async def test_import_workflow_creates_new_workflow(
    client: AsyncClient,
    db_session: AsyncSession,
    mock_auth,
    seed_user_a,
    tenant_id: UUID,
    user_id: UUID,
):
    """POST /import creates a new workflow with regenerated IDs."""
    app.dependency_overrides[get_user_claims] = _make_claims(user_id, tenant_id)
    try:
        import_payload = {
            "metadata": {
                "version": "1.0",
                "exported_at": "2026-02-07T00:00:00Z",
                "source_workflow_id": "00000000-0000-0000-0000-000000000099",
            },
            "name": "Imported Workflow",
            "description": "Imported from export",
            "graph_json": {
                "nodes": [
                    {"id": "old-src", "type": "data_source", "data": {"config": {"table": "trades"}}},
                    {"id": "old-flt", "type": "filter", "data": {"config": {"column": "x"}}},
                ],
                "edges": [
                    {"id": "old-e1", "source": "old-src", "target": "old-flt"},
                ],
            },
        }

        response = await client.post("/api/v1/workflows/import", json=import_payload)
        assert response.status_code == 201
        data = response.json()

        assert data["name"] == "Imported Workflow"
        assert data["tenant_id"] == str(tenant_id)
        assert data["created_by"] == str(user_id)

        # Verify node IDs were regenerated
        nodes = data["graph_json"]["nodes"]
        node_ids = {n["id"] for n in nodes}
        assert "old-src" not in node_ids
        assert "old-flt" not in node_ids
        assert len(node_ids) == 2

        # Verify edge references were updated
        edges = data["graph_json"]["edges"]
        assert edges[0]["source"] in node_ids
        assert edges[0]["target"] in node_ids
        assert edges[0]["id"] != "old-e1"
    finally:
        app.dependency_overrides.pop(get_user_claims, None)


async def test_import_workflow_logs_audit_event(
    client: AsyncClient,
    db_session: AsyncSession,
    mock_auth,
    seed_user_a,
    tenant_id: UUID,
    user_id: UUID,
):
    """Import creates an audit log entry with IMPORTED action."""
    app.dependency_overrides[get_user_claims] = _make_claims(user_id, tenant_id)
    try:
        import_payload = {
            "metadata": {
                "version": "1.0",
                "exported_at": "2026-02-07T00:00:00Z",
                "source_workflow_id": "00000000-0000-0000-0000-000000000099",
            },
            "name": "Audit Import Test",
            "graph_json": {"nodes": [], "edges": []},
        }

        response = await client.post("/api/v1/workflows/import", json=import_payload)
        assert response.status_code == 201
        wf_id = UUID(response.json()["id"])

        result = await db_session.execute(
            select(AuditLog).where(
                AuditLog.resource_id == wf_id,
                AuditLog.action == AuditAction.IMPORTED,
            )
        )
        audit = result.scalar_one_or_none()
        assert audit is not None
        assert audit.tenant_id == tenant_id
    finally:
        app.dependency_overrides.pop(get_user_claims, None)


async def test_import_workflow_viewer_role_forbidden(
    client: AsyncClient,
    mock_auth,
    seed_user_a,
    tenant_id: UUID,
    user_id: UUID,
):
    """Import with viewer role returns 403."""
    app.dependency_overrides[get_user_claims] = _make_claims(
        user_id, tenant_id, role="viewer"
    )
    try:
        import_payload = {
            "metadata": {
                "version": "1.0",
                "exported_at": "2026-02-07T00:00:00Z",
                "source_workflow_id": "00000000-0000-0000-0000-000000000099",
            },
            "name": "Should Fail",
            "graph_json": {"nodes": [], "edges": []},
        }

        response = await client.post("/api/v1/workflows/import", json=import_payload)
        assert response.status_code == 403
    finally:
        app.dependency_overrides.pop(get_user_claims, None)


async def test_export_roundtrip(
    client: AsyncClient,
    db_session: AsyncSession,
    mock_auth,
    seed_user_a,
    tenant_id: UUID,
    user_id: UUID,
):
    """Export then import produces a valid workflow with different IDs."""
    app.dependency_overrides[get_user_claims] = _make_claims(user_id, tenant_id)
    try:
        wf = await _create_workflow(db_session, tenant_id, user_id, "Roundtrip Test")

        # Export
        export_resp = await client.get(f"/api/v1/workflows/{wf.id}/export")
        assert export_resp.status_code == 200
        export_data = export_resp.json()

        # Import
        import_resp = await client.post("/api/v1/workflows/import", json=export_data)
        assert import_resp.status_code == 201
        imported = import_resp.json()

        # Different workflow ID
        assert imported["id"] != str(wf.id)
        # Same name and structure size
        assert imported["name"] == wf.name
        assert len(imported["graph_json"]["nodes"]) == len(wf.graph_json["nodes"])
        assert len(imported["graph_json"]["edges"]) == len(wf.graph_json["edges"])
    finally:
        app.dependency_overrides.pop(get_user_claims, None)
