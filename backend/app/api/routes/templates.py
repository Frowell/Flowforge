"""Template registry endpoints.

List, get, and instantiate pre-defined workflow templates.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_current_tenant_id,
    get_current_user_id,
    get_db,
    require_role,
)
from app.models.audit_log import AuditAction, AuditResourceType
from app.models.workflow import Workflow
from app.schemas.template import (
    TemplateInstantiateRequest,
    TemplateListResponse,
    TemplateResponse,
)
from app.schemas.workflow import WorkflowResponse
from app.services.audit_service import AuditService
from app.services.template_registry import (
    get_all_templates,
    get_template,
    instantiate_template,
)

router = APIRouter()


@router.get("", response_model=TemplateListResponse)
async def list_templates(
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """List all available workflow templates."""
    templates = get_all_templates()
    return TemplateListResponse(
        items=[
            TemplateResponse(
                id=t.id,
                name=t.name,
                description=t.description,
                category=t.category,
                tags=t.tags,
                graph_json=t.graph_json,
                thumbnail=t.thumbnail,
            )
            for t in templates
        ]
    )


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template_detail(
    template_id: str,
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """Get a single template by ID."""
    template = get_template(template_id)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Template not found"
        )
    return TemplateResponse(
        id=template.id,
        name=template.name,
        description=template.description,
        category=template.category,
        tags=template.tags,
        graph_json=template.graph_json,
        thumbnail=template.thumbnail,
    )


@router.post(
    "/{template_id}/instantiate",
    response_model=WorkflowResponse,
    status_code=status.HTTP_201_CREATED,
)
async def instantiate_template_route(
    template_id: str,
    body: TemplateInstantiateRequest | None = None,
    tenant_id: UUID = Depends(get_current_tenant_id),
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_role("admin", "analyst")),
):
    """Create a new workflow from a template with fresh node IDs."""
    template = get_template(template_id)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Template not found"
        )

    graph_json = instantiate_template(template_id)
    name = body.name if body and body.name else template.name

    workflow = Workflow(
        name=name,
        description=template.description,
        graph_json=graph_json,
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
        metadata={"template_id": template_id, "name": name},
    )

    await db.commit()
    await db.refresh(workflow)
    return WorkflowResponse.model_validate(workflow)
