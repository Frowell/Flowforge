"""Workflow execution endpoints.

Run workflow, get execution status, cancel execution.
All queries are scoped by tenant_id from the JWT.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_tenant_id, get_db, get_preview_service
from app.models.workflow import Workflow
from app.schemas.preview import PreviewRequest, PreviewResponse
from app.schemas.query import ExecutionRequest, ExecutionStatusResponse
from app.services.preview_service import PreviewService

router = APIRouter()


@router.post("/preview", response_model=PreviewResponse)
async def preview_node(
    body: PreviewRequest,
    tenant_id: UUID = Depends(get_current_tenant_id),
    preview_service: PreviewService = Depends(get_preview_service),
):
    """Execute a constrained preview query for a single node.

    Returns paginated rows with resource limits enforced.
    Results are cached by content-addressed key (tenant_id + node config + offset/limit).
    """
    result = await preview_service.execute_preview(
        tenant_id=tenant_id,
        target_node_id=body.target_node_id,
        nodes=body.graph.nodes,
        edges=body.graph.edges,
        offset=body.offset,
        limit=body.limit,
    )
    return PreviewResponse(**result)


@router.post("", response_model=ExecutionStatusResponse, status_code=status.HTTP_202_ACCEPTED)
async def execute_workflow(
    body: ExecutionRequest,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    """Compile and execute a workflow.

    The backend compiles the canvas DAG into merged SQL queries via SQLGlot,
    dispatches to the appropriate backing stores via the query router,
    and streams status updates via WebSocket.
    """
    result = await db.execute(
        select(Workflow).where(
            Workflow.id == body.workflow_id,
            Workflow.tenant_id == tenant_id,
        )
    )
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")

    # TODO: Compile workflow DAG -> SQL via workflow_compiler (pass tenant_id)
    # TODO: Dispatch via query_router
    # TODO: Stream status via websocket_manager (tenant-scoped channels)
    # TODO: Return execution tracking ID

    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Workflow execution not yet implemented",
    )


@router.get("/{execution_id}", response_model=ExecutionStatusResponse)
async def get_execution_status(
    execution_id: UUID,
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """Get the current status of a workflow execution."""
    # TODO: Look up execution status (likely from Redis for speed, scoped by tenant_id)
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Execution status tracking not yet implemented",
    )


@router.post("/{execution_id}/cancel", status_code=status.HTTP_202_ACCEPTED)
async def cancel_execution(
    execution_id: UUID,
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """Cancel a running workflow execution."""
    # TODO: Signal cancellation to running tasks (verify tenant ownership)
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Execution cancellation not yet implemented",
    )
