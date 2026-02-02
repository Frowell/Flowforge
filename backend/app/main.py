"""FlowForge FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging_config import configure_logging
from app.core.metrics import app_info
from app.core.middleware import ObservabilityMiddleware
from app.api.routes import health, workflows, executions, dashboards, widgets, embed, schema, ws, metrics


configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle events."""
    app_info.info({"version": "0.1.0", "env": settings.app_env})
    # TODO: Initialize WebSocket manager subscriber
    # TODO: Warm schema registry cache
    yield
    # Shutdown: close connections
    # TODO: Close ClickHouse client
    # TODO: Close Redis connections


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
app.include_router(ws.router, tags=["websocket"])
app.include_router(metrics.router, tags=["metrics"])
