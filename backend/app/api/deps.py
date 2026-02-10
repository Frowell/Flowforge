"""Dependency injection for FastAPI routes.

All services and sessions are provided via Depends() from this module.
Route handlers never instantiate services directly.
"""

from collections.abc import AsyncGenerator

from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import (
    get_current_tenant_id,  # noqa: F401
    get_current_user_claims,
    get_current_user_id,  # noqa: F401
)
from app.core.clickhouse import get_clickhouse_client
from app.core.config import settings
from app.core.database import get_db as _get_db
from app.core.materialize import get_materialize_client
from app.core.redis import get_redis as _get_redis
from app.services.preview_service import PreviewService
from app.services.query_router import QueryRouter
from app.services.rate_limiter import RateLimiter
from app.services.schema_engine import SchemaEngine
from app.services.schema_registry import SchemaRegistry
from app.services.websocket_manager import WebSocketManager
from app.services.widget_data_service import WidgetDataService
from app.services.workflow_compiler import WorkflowCompiler


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Provide an async database session."""
    async for session in _get_db():
        yield session


async def get_redis():
    """Provide the Redis client."""
    return await _get_redis()


async def get_schema_registry(
    redis=Depends(get_redis),
) -> SchemaRegistry:
    clickhouse = get_clickhouse_client()
    materialize = get_materialize_client()
    return SchemaRegistry(
        redis=redis,
        clickhouse=clickhouse,
        materialize=materialize,
        cache_ttl=settings.schema_cache_ttl,
    )


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
    materialize = get_materialize_client()
    return QueryRouter(
        clickhouse=clickhouse,
        redis=redis,
        materialize=materialize,
    )


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


async def get_websocket_manager(request: Request) -> WebSocketManager:
    """Return the WebSocket manager from app state."""
    return request.app.state.ws_manager


async def get_user_claims(request: Request) -> dict:
    """Wrapper around get_current_user_claims for DI.

    In development mode without auth header or with "dev-token",
    returns dev claims with admin access.
    This allows Depends() override in tests.
    """
    auth_header = request.headers.get("Authorization")
    token = auth_header.removeprefix("Bearer ") if auth_header else None
    if settings.app_env == "development" and (not token or token == "dev-token"):
        return {
            "sub": settings.dev_user_id,
            "tenant_id": settings.dev_tenant_id,
            "realm_access": {"roles": ["admin"]},
            "resource_access": {},
            "dev_bypass": True,
        }
    return await get_current_user_claims(request)


def require_role(*allowed_roles: str):
    """Dependency factory that enforces Keycloak role-based access.

    Usage: `Depends(require_role("admin", "analyst"))`
    """

    async def _check(
        claims: dict = Depends(get_user_claims),
    ) -> dict:
        realm_roles = claims.get("realm_access", {}).get("roles", [])
        client_roles = []
        for client_data in claims.get("resource_access", {}).values():
            client_roles.extend(client_data.get("roles", []))
        all_roles = set(realm_roles + client_roles)

        if not any(r in all_roles for r in allowed_roles):
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return claims

    return _check
