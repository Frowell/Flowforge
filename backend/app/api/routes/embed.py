"""Embed endpoints — API key authenticated widget data for iframes.

Route: /embed/:widget_id?api_key=sk_live_...

Tenant context is resolved from the API key's tenant_id column,
not from a Keycloak JWT (embed routes are unauthenticated via SSO).
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_rate_limiter, get_widget_data_service
from app.core.auth import validate_api_key
from app.models.dashboard import Dashboard, Widget
from app.models.workflow import Workflow
from app.schemas.dashboard import WidgetDataResponse
from app.services.rate_limiter import RateLimiter, RateLimitExceededError
from app.services.widget_data_service import WidgetDataService

router = APIRouter()


@router.get("/{widget_id}", response_model=WidgetDataResponse)
async def get_embed_widget_data(
    widget_id: UUID,
    api_key: str = Query(..., alias="api_key"),
    offset: int = 0,
    limit: int = 10_000,
    db: AsyncSession = Depends(get_db),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
    widget_data_service: WidgetDataService = Depends(get_widget_data_service),
):
    """Fetch widget data for embed mode.

    Authenticates via API key (not session). The API key must be
    scoped to include this widget_id and must belong to the same
    tenant as the widget's dashboard.
    """
    # 1. Validate API key
    scope = await validate_api_key(api_key, db)

    # 2. Rate limit check
    try:
        await rate_limiter.check(scope["key_hash"], limit=scope["rate_limit"])
    except RateLimitExceededError as exc:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"detail": "Rate limit exceeded"},
            headers={"Retry-After": str(exc.retry_after)},
        )

    # 3. Widget scope check
    scoped_ids = scope["scoped_widget_ids"]
    if scoped_ids is not None and widget_id not in scoped_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API key does not have access to this widget",
        )

    # 4. Load widget, verify tenant match through dashboard
    tenant_id = scope["tenant_id"]
    result = await db.execute(
        select(Widget)
        .join(Dashboard, Widget.dashboard_id == Dashboard.id)
        .where(
            Widget.id == widget_id,
            Dashboard.tenant_id == tenant_id,
        )
    )
    widget = result.scalar_one_or_none()
    if not widget:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Widget not found",
        )

    # 5. Load source workflow with tenant check
    wf_result = await db.execute(
        select(Workflow).where(
            Workflow.id == widget.source_workflow_id,
            Workflow.tenant_id == tenant_id,
        )
    )
    workflow = wf_result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source workflow not found",
        )

    # 6. Fetch widget data (with caching)
    data = await widget_data_service.fetch_widget_data(
        tenant_id=tenant_id,
        source_node_id=widget.source_node_id,
        graph_json=workflow.graph_json,
        config_overrides=widget.config_overrides,
        offset=offset,
        limit=limit,
    )
    return WidgetDataResponse(**data)
