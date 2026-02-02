"""Dependency injection for FastAPI routes.

All services and sessions are provided via Depends() from this module.
Route handlers never instantiate services directly.
"""

from collections.abc import AsyncGenerator
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db as _get_db
from app.core.redis import get_redis as _get_redis


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Provide an async database session."""
    async for session in _get_db():
        yield session


async def get_redis():
    """Provide the Redis client."""
    return await _get_redis()


# Auth dependency re-exports — canonical way to get user/tenant context in routes.
from app.core.auth import get_current_tenant_id  # noqa: E402, F401
from app.core.auth import get_current_user_id  # noqa: E402, F401

# Service dependency providers — import the service, inject its dependencies.
# Each returns a configured service instance for the request lifecycle.

from fastapi import Depends  # noqa: E402

from app.core.clickhouse import get_clickhouse_client
from app.core.config import settings
from app.services.preview_service import PreviewService
from app.services.query_router import QueryRouter
from app.services.rate_limiter import RateLimiter
from app.services.schema_engine import SchemaEngine
from app.services.schema_registry import SchemaRegistry
from app.services.widget_data_service import WidgetDataService
from app.services.workflow_compiler import WorkflowCompiler


async def get_schema_registry(
    redis=Depends(get_redis),
) -> SchemaRegistry:
    clickhouse = get_clickhouse_client()
    return SchemaRegistry(redis=redis, clickhouse=clickhouse, cache_ttl=settings.schema_cache_ttl)


async def get_schema_engine() -> SchemaEngine:
    return SchemaEngine()


async def get_workflow_compiler(
    schema_engine: SchemaEngine = Depends(get_schema_engine),
) -> WorkflowCompiler:
    return WorkflowCompiler(schema_engine=schema_engine)


async def get_query_router(
    redis=Depends(get_redis),
) -> QueryRouter:
    clickhouse = get_clickhouse_client()
    return QueryRouter(clickhouse=clickhouse, redis=redis)


async def get_preview_service(
    compiler: WorkflowCompiler = Depends(get_workflow_compiler),
    query_router: QueryRouter = Depends(get_query_router),
    redis=Depends(get_redis),
) -> PreviewService:
    return PreviewService(compiler=compiler, query_router=query_router, redis=redis)


async def get_widget_data_service(
    compiler: WorkflowCompiler = Depends(get_workflow_compiler),
    query_router: QueryRouter = Depends(get_query_router),
    redis=Depends(get_redis),
) -> WidgetDataService:
    return WidgetDataService(compiler=compiler, query_router=query_router, redis=redis)


async def get_rate_limiter(redis=Depends(get_redis)) -> RateLimiter:
    return RateLimiter(redis=redis)
