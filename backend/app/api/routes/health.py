"""Health check endpoints. No authentication required.

- /health       — legacy, backward-compatible
- /health/live  — liveness probe (always 200)
- /health/ready — readiness probe (checks dependencies)
"""

import structlog
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clickhouse import get_clickhouse_client
from app.core.database import get_db
from app.core.redis import get_redis

router = APIRouter()
logger = structlog.stdlib.get_logger("flowforge.health")


@router.get("/health")
async def health_check():
    """Legacy health check — backward compatible."""
    return {"status": "healthy", "service": "flowforge"}


@router.get("/health/live")
async def liveness():
    """Liveness probe — process is alive."""
    return {"status": "live"}


@router.get("/health/ready")
async def readiness(
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    """Readiness probe — checks PostgreSQL, Redis, and ClickHouse."""
    checks: dict[str, dict] = {}
    healthy = True

    # PostgreSQL
    try:
        await db.execute(text("SELECT 1"))
        checks["postgresql"] = {"status": "ok"}
    except Exception as exc:
        checks["postgresql"] = {"status": "error", "detail": str(exc)}
        healthy = False
        logger.warning(
            "readiness_check_failed", dependency="postgresql", error=str(exc)
        )

    # Redis
    try:
        await redis.ping()  # type: ignore[misc]
        checks["redis"] = {"status": "ok"}
    except Exception as exc:
        checks["redis"] = {"status": "error", "detail": str(exc)}
        healthy = False
        logger.warning("readiness_check_failed", dependency="redis", error=str(exc))

    # ClickHouse (optional — degraded, not failing)
    try:
        ch = get_clickhouse_client()
        ok = await ch.ping()
        checks["clickhouse"] = {"status": "ok" if ok else "degraded"}
    except Exception as exc:
        checks["clickhouse"] = {"status": "degraded", "detail": str(exc)}
        logger.info("readiness_check_degraded", dependency="clickhouse", error=str(exc))

    status_code = 200 if healthy else 503
    return JSONResponse(
        content={"status": "ready" if healthy else "not_ready", "checks": checks},
        status_code=status_code,
    )
