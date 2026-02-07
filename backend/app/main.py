"""FlowForge FastAPI application entry point."""

import asyncio
import contextlib
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    api_keys,
    audit,
    dashboards,
    embed,
    executions,
    health,
    metrics,
    schema,
    templates,
    widgets,
    workflows,
    ws,
)
from app.core.config import settings
from app.core.logging_config import configure_logging
from app.core.materialize import get_materialize_client
from app.core.metrics import app_info
from app.core.middleware import ObservabilityMiddleware
from app.core.redis import get_redis
from app.services.live_data_service import LiveDataService
from app.services.websocket_manager import WebSocketManager

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle events."""
    app_info.info({"version": "0.1.0", "env": settings.app_env})

    # Initialize Materialize pool (optional — may fail in dev)
    mz_client = get_materialize_client()
    await mz_client.create_pool()
    app.state.materialize_client = mz_client

    # Initialize WebSocket manager with Redis pub/sub
    redis = await get_redis()
    ws_manager = WebSocketManager(redis)
    app.state.ws_manager = ws_manager
    subscriber_task = asyncio.create_task(ws_manager.start_subscriber())

    # Initialize live data service (placeholder widget_data_service —
    # actual per-request service is injected in routes)
    live_data_service = LiveDataService(
        ws_manager=ws_manager,
        widget_data_service=None,  # type: ignore[arg-type]
        materialize_client=mz_client,
    )
    live_data_service.start()
    app.state.live_data_service = live_data_service

    yield

    # Shutdown: stop live data service, cancel subscriber, close pool
    live_data_service.stop()
    subscriber_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await subscriber_task
    await mz_client.close_pool()


app = FastAPI(
    title="FlowForge",
    description="Visual analytics canvas + BI layer — compiles workflows to SQL",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(ObservabilityMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes — all REST under /api/v1/
app.include_router(health.router, tags=["health"])
app.include_router(workflows.router, prefix="/api/v1/workflows", tags=["workflows"])
app.include_router(executions.router, prefix="/api/v1/executions", tags=["executions"])
app.include_router(dashboards.router, prefix="/api/v1/dashboards", tags=["dashboards"])
app.include_router(widgets.router, prefix="/api/v1/widgets", tags=["widgets"])
app.include_router(embed.router, prefix="/api/v1/embed", tags=["embed"])
app.include_router(schema.router, prefix="/api/v1/schema", tags=["schema"])
app.include_router(api_keys.router, prefix="/api/v1/api-keys", tags=["api-keys"])
app.include_router(templates.router, prefix="/api/v1/templates", tags=["templates"])
app.include_router(audit.router, prefix="/api/v1/audit-logs", tags=["audit-logs"])
app.include_router(ws.router, tags=["websocket"])
app.include_router(metrics.router, tags=["metrics"])
