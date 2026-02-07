"""Workflow CRUD endpoints.

Thin controllers: validate -> call service -> return Pydantic response.
All queries are scoped by tenant_id from the JWT.
"""

import uuid as _uuid
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_current_tenant_id,
    get_current_user_id,
    get_db,
    require_role,
)
from app.models.audit_log import AuditAction, AuditResourceType
from app.models.workflow import Workflow, WorkflowVersion
from app.schemas.workflow import (
    WorkflowCreate,
    WorkflowExportMetadata,
    WorkflowExportResponse,
    WorkflowImportRequest,
    WorkflowListResponse,
    WorkflowResponse,
    WorkflowUpdate,
    WorkflowVersionListResponse,
    WorkflowVersionResponse,
)
from app.services.audit_service import AuditService

router = APIRouter()


@router.get("", response_model=WorkflowListResponse)
async def list_workflows(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    total_q = await db.execute(
        select(func.count(Workflow.id)).where(Workflow.tenant_id == tenant_id)
    )
    total = total_q.scalar_one()

    q = (
        select(Workflow)
        .where(Workflow.tenant_id == tenant_id)
        .order_by(Workflow.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(q)
    workflows = result.scalars().all()

    return WorkflowListResponse(
        items=[WorkflowResponse.model_validate(w) for w in workflows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: UUID,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Workflow).where(
            Workflow.id == workflow_id,
            Workflow.tenant_id == tenant_id,
        )
    )
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found"
        )
    return WorkflowResponse.model_validate(workflow)


@router.post("", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
async def create_workflow(
    body: WorkflowCreate,
    tenant_id: UUID = Depends(get_current_tenant_id),
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_role("admin", "analyst")),
):
    workflow = Workflow(
        name=body.name,
        description=body.description,
        graph_json=body.graph_json,
        tenant_id=tenant_id,
        created_by=user_id,
    )
    db.add(workflow)
    await db.flush()

    audit = AuditService(db)
    await audit.log(
        tenant_id=tenant_id,
        user_id=user_id,
        action=AuditAction.CREATED,
        resource_type=AuditResourceType.WORKFLOW,
        resource_id=workflow.id,
        metadata={"name": body.name},
    )

    await db.commit()
    await db.refresh(workflow)
    return WorkflowResponse.model_validate(workflow)


@router.patch("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: UUID,
    body: WorkflowUpdate,
    tenant_id: UUID = Depends(get_current_tenant_id),
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_role("admin", "analyst")),
):
    result = await db.execute(
        select(Workflow).where(
            Workflow.id == workflow_id,
            Workflow.tenant_id == tenant_id,
        )
    )
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found"
        )

    update_data = body.model_dump(exclude_unset=True)

    # Auto-snapshot current graph_json before applying update
    if "graph_json" in update_data:
        max_ver = await db.execute(
            select(func.coalesce(func.max(WorkflowVersion.version_number), 0)).where(
                WorkflowVersion.workflow_id == workflow.id
            )
        )
        next_version = max_ver.scalar_one() + 1

        snapshot = WorkflowVersion(
            workflow_id=workflow.id,
            version_number=next_version,
            graph_json=workflow.graph_json,
            created_by=user_id,
        )
        db.add(snapshot)

    for field, value in update_data.items():
        setattr(workflow, field, value)

    audit = AuditService(db)
    await audit.log(
        tenant_id=tenant_id,
        user_id=user_id,
        action=AuditAction.UPDATED,
        resource_type=AuditResourceType.WORKFLOW,
        resource_id=workflow.id,
        metadata={"fields": list(update_data.keys())},
    )

    await db.commit()
    await db.refresh(workflow)
    return WorkflowResponse.model_validate(workflow)


@router.delete("/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workflow(
    workflow_id: UUID,
    tenant_id: UUID = Depends(get_current_tenant_id),
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_role("admin", "analyst")),
):
    result = await db.execute(
        select(Workflow).where(
            Workflow.id == workflow_id,
            Workflow.tenant_id == tenant_id,
        )
    )
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found"
        )

    audit = AuditService(db)
    await audit.log(
        tenant_id=tenant_id,
        user_id=user_id,
        action=AuditAction.DELETED,
        resource_type=AuditResourceType.WORKFLOW,
        resource_id=workflow.id,
        metadata={"name": workflow.name},
    )

    await db.delete(workflow)
    await db.commit()


# --- Export/Import endpoints ---


@router.get("/{workflow_id}/export", response_model=WorkflowExportResponse)
async def export_workflow(
    workflow_id: UUID,
    tenant_id: UUID = Depends(get_current_tenant_id),
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_role("admin", "analyst")),
):
    result = await db.execute(
        select(Workflow).where(
            Workflow.id == workflow_id,
            Workflow.tenant_id == tenant_id,
        )
    )
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found"
        )

    audit = AuditService(db)
    await audit.log(
        tenant_id=tenant_id,
        user_id=user_id,
        action=AuditAction.EXPORTED,
        resource_type=AuditResourceType.WORKFLOW,
        resource_id=workflow.id,
        metadata={"name": workflow.name},
    )
    await db.commit()

    return WorkflowExportResponse(
        metadata=WorkflowExportMetadata(
            version="1.0",
            exported_at=datetime.now(UTC),
            source_workflow_id=workflow.id,
        ),
        name=workflow.name,
        description=workflow.description,
        graph_json=workflow.graph_json,
    )


@router.post(
    "/import",
    response_model=WorkflowResponse,
    status_code=status.HTTP_201_CREATED,
)
async def import_workflow(
    body: WorkflowImportRequest,
    tenant_id: UUID = Depends(get_current_tenant_id),
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_role("admin", "analyst")),
):
    # Regenerate all node and edge IDs to prevent collisions
    graph = body.graph_json.copy()
    id_mapping: dict[str, str] = {}

    nodes = graph.get("nodes", [])
    for node in nodes:
        old_id = node.get("id", "")
        new_id = str(_uuid.uuid4())
        id_mapping[old_id] = new_id
        node["id"] = new_id

    edges = graph.get("edges", [])
    for edge in edges:
        edge["id"] = str(_uuid.uuid4())
        old_source = edge.get("source", "")
        old_target = edge.get("target", "")
        edge["source"] = id_mapping.get(old_source, old_source)
        edge["target"] = id_mapping.get(old_target, old_target)

    graph["nodes"] = nodes
    graph["edges"] = edges

    workflow = Workflow(
        name=body.name,
        description=body.description,
        graph_json=graph,
        tenant_id=tenant_id,
        created_by=user_id,
    )
    db.add(workflow)
    await db.flush()

    audit = AuditService(db)
    await audit.log(
        tenant_id=tenant_id,
        user_id=user_id,
        action=AuditAction.IMPORTED,
        resource_type=AuditResourceType.WORKFLOW,
        resource_id=workflow.id,
        metadata={
            "name": body.name,
            "source_workflow_id": str(body.metadata.source_workflow_id),
        },
    )

    await db.commit()
    await db.refresh(workflow)
    return WorkflowResponse.model_validate(workflow)


# --- Version endpoints ---


@router.get("/{workflow_id}/versions", response_model=WorkflowVersionListResponse)
async def list_workflow_versions(
    workflow_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    # Verify workflow belongs to tenant
    wf_result = await db.execute(
        select(Workflow.id).where(
            Workflow.id == workflow_id,
            Workflow.tenant_id == tenant_id,
        )
    )
    if not wf_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found"
        )

    total_q = await db.execute(
        select(func.count(WorkflowVersion.id)).where(
            WorkflowVersion.workflow_id == workflow_id
        )
    )
    total = total_q.scalar_one()

    q = (
        select(WorkflowVersion)
        .where(WorkflowVersion.workflow_id == workflow_id)
        .order_by(WorkflowVersion.version_number.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(q)
    versions = result.scalars().all()

    return WorkflowVersionListResponse(
        items=[WorkflowVersionResponse.model_validate(v) for v in versions],
        total=total,
    )


@router.get(
    "/{workflow_id}/versions/{version_id}", response_model=WorkflowVersionResponse
)
async def get_workflow_version(
    workflow_id: UUID,
    version_id: UUID,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    # Verify workflow belongs to tenant
    wf_result = await db.execute(
        select(Workflow.id).where(
            Workflow.id == workflow_id,
            Workflow.tenant_id == tenant_id,
        )
    )
    if not wf_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found"
        )

    result = await db.execute(
        select(WorkflowVersion).where(
            WorkflowVersion.id == version_id,
            WorkflowVersion.workflow_id == workflow_id,
        )
    )
    version = result.scalar_one_or_none()
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Version not found"
        )

    return WorkflowVersionResponse.model_validate(version)


@router.post(
    "/{workflow_id}/versions/{version_id}/rollback",
    response_model=WorkflowResponse,
)
async def rollback_workflow(
    workflow_id: UUID,
    version_id: UUID,
    tenant_id: UUID = Depends(get_current_tenant_id),
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_role("admin", "analyst")),
):
    # Fetch workflow (tenant-scoped)
    wf_result = await db.execute(
        select(Workflow).where(
            Workflow.id == workflow_id,
            Workflow.tenant_id == tenant_id,
        )
    )
    workflow = wf_result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found"
        )

    # Fetch target version
    ver_result = await db.execute(
        select(WorkflowVersion).where(
            WorkflowVersion.id == version_id,
            WorkflowVersion.workflow_id == workflow_id,
        )
    )
    target_version = ver_result.scalar_one_or_none()
    if not target_version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Version not found"
        )

    # Snapshot current state before rollback
    max_ver = await db.execute(
        select(func.coalesce(func.max(WorkflowVersion.version_number), 0)).where(
            WorkflowVersion.workflow_id == workflow.id
        )
    )
    next_version = max_ver.scalar_one() + 1

    snapshot = WorkflowVersion(
        workflow_id=workflow.id,
        version_number=next_version,
        graph_json=workflow.graph_json,
        created_by=user_id,
    )
    db.add(snapshot)

    # Apply rollback
    workflow.graph_json = target_version.graph_json

    await db.commit()
    await db.refresh(workflow)
    return WorkflowResponse.model_validate(workflow)
