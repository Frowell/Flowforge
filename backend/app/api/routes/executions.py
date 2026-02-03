"""Workflow execution endpoints.

Run workflow, get execution status, cancel execution.
All queries are scoped by tenant_id from the JWT.
"""

import json
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_current_tenant_id,
    get_current_user_id,
    get_db,
    get_preview_service,
    get_query_router,
    get_redis,
    get_websocket_manager,
    get_workflow_compiler,
    require_role,
)
from app.models.audit_log import AuditAction, AuditResourceType
from app.services.audit_service import AuditService
from app.models.workflow import Workflow
from app.schemas.preview import PreviewRequest, PreviewResponse
from app.schemas.query import ExecutionStatusResponse, NodeStatusResponse, ExecutionRequest
from app.services.preview_service import PreviewService
from app.services.query_router import QueryRouter
from app.services.websocket_manager import WebSocketManager
from app.services.workflow_compiler import WorkflowCompiler

router = APIRouter()

EXECUTION_TTL = 3600  # 1 hour


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
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    compiler: WorkflowCompiler = Depends(get_workflow_compiler),
    query_router: QueryRouter = Depends(get_query_router),
    ws_manager: WebSocketManager = Depends(get_websocket_manager),
    redis=Depends(get_redis),
    _: dict = Depends(require_role("admin", "analyst")),
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

    audit = AuditService(db)
    await audit.log(
        tenant_id=tenant_id,
        user_id=user_id,
        action=AuditAction.EXECUTED,
        resource_type=AuditResourceType.WORKFLOW,
        resource_id=body.workflow_id,
    )
    await db.commit()

    execution_id = uuid4()
    now = datetime.now(timezone.utc).isoformat()

    graph = workflow.graph_json or {}
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])

    # Store initial execution record in Redis
    execution_record = {
        "id": str(execution_id),
        "workflow_id": str(body.workflow_id),
        "tenant_id": str(tenant_id),
        "status": "pending",
        "node_statuses": {},
        "started_at": now,
        "completed_at": None,
    }
    redis_key = f"flowforge:{tenant_id}:execution:{execution_id}"
    await redis.set(redis_key, json.dumps(execution_record), ex=EXECUTION_TTL)

    # Compile workflow
    try:
        segments = compiler.compile(nodes, edges)
    except Exception as e:
        execution_record["status"] = "failed"
        execution_record["completed_at"] = datetime.now(timezone.utc).isoformat()
        await redis.set(redis_key, json.dumps(execution_record), ex=EXECUTION_TTL)
        await ws_manager.publish_execution_status(
            tenant_id=tenant_id,
            execution_id=execution_id,
            node_id="__compiler__",
            status="failed",
            data={"error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Compilation failed: {e}",
        )

    # Update status to running
    execution_record["status"] = "running"
    await redis.set(redis_key, json.dumps(execution_record), ex=EXECUTION_TTL)
    await ws_manager.publish_execution_status(
        tenant_id=tenant_id,
        execution_id=execution_id,
        node_id="__workflow__",
        status="running",
    )

    # Execute each segment, publishing per-node status updates
    for segment in segments:
        for node_id in segment.source_node_ids:
            execution_record["node_statuses"][node_id] = {
                "status": "running",
                "started_at": datetime.now(timezone.utc).isoformat(),
            }
            await ws_manager.publish_execution_status(
                tenant_id=tenant_id,
                execution_id=execution_id,
                node_id=node_id,
                status="running",
            )

        try:
            query_result = await query_router.execute(segment)
            for node_id in segment.source_node_ids:
                execution_record["node_statuses"][node_id] = {
                    "status": "completed",
                    "started_at": execution_record["node_statuses"][node_id]["started_at"],
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                    "rows_processed": query_result.total_rows,
                }
                await ws_manager.publish_execution_status(
                    tenant_id=tenant_id,
                    execution_id=execution_id,
                    node_id=node_id,
                    status="completed",
                    data={"rows_processed": query_result.total_rows},
                )
        except Exception as e:
            for node_id in segment.source_node_ids:
                execution_record["node_statuses"][node_id] = {
                    "status": "failed",
                    "error": str(e),
                }
                await ws_manager.publish_execution_status(
                    tenant_id=tenant_id,
                    execution_id=execution_id,
                    node_id=node_id,
                    status="failed",
                    data={"error": str(e)},
                )
            execution_record["status"] = "failed"
            execution_record["completed_at"] = datetime.now(timezone.utc).isoformat()
            await redis.set(redis_key, json.dumps(execution_record), ex=EXECUTION_TTL)
            await ws_manager.publish_execution_status(
                tenant_id=tenant_id,
                execution_id=execution_id,
                node_id="__workflow__",
                status="failed",
                data={"error": str(e)},
            )
            break
    else:
        # All segments completed successfully
        execution_record["status"] = "completed"
        execution_record["completed_at"] = datetime.now(timezone.utc).isoformat()
        await redis.set(redis_key, json.dumps(execution_record), ex=EXECUTION_TTL)
        await ws_manager.publish_execution_status(
            tenant_id=tenant_id,
            execution_id=execution_id,
            node_id="__workflow__",
            status="completed",
        )

    return ExecutionStatusResponse(
        id=execution_id,
        workflow_id=body.workflow_id,
        status=execution_record["status"],
        started_at=execution_record["started_at"],
        completed_at=execution_record.get("completed_at"),
        node_statuses={
            nid: NodeStatusResponse(**ns)
            for nid, ns in execution_record["node_statuses"].items()
        },
    )


@router.get("/{execution_id}", response_model=ExecutionStatusResponse)
async def get_execution_status(
    execution_id: UUID,
    tenant_id: UUID = Depends(get_current_tenant_id),
    redis=Depends(get_redis),
):
    """Get the current status of a workflow execution."""
    redis_key = f"flowforge:{tenant_id}:execution:{execution_id}"
    raw = await redis.get(redis_key)
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Execution not found",
        )

    record = json.loads(raw)
    return ExecutionStatusResponse(
        id=UUID(record["id"]),
        workflow_id=UUID(record["workflow_id"]),
        status=record["status"],
        started_at=record.get("started_at"),
        completed_at=record.get("completed_at"),
        node_statuses={
            nid: NodeStatusResponse(**ns)
            for nid, ns in record.get("node_statuses", {}).items()
        },
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
