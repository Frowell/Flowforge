"""Health check endpoints. No authentication required.

- /health       — legacy, backward-compatible
- /health/live  — liveness probe (always 200)
- /health/ready — readiness probe (checks dependencies)
"""

import asyncio
import time

import httpx
import structlog
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clickhouse import get_clickhouse_client
from app.core.config import settings
from app.core.database import get_db
from app.core.materialize import MaterializeClient
from app.core.metrics import store_health_check_duration_seconds, store_health_status
from app.core.redis import get_redis

router = APIRouter()
logger = structlog.stdlib.get_logger("flowforge.health")

# Per-store timeout for health checks (seconds)
_HEALTH_CHECK_TIMEOUT = 3.0


@router.get("/health")
async def health_check():
    """Legacy health check — backward compatible."""
    return {"status": "healthy", "service": "flowforge"}


@router.get("/health/live")
async def liveness():
    """Liveness probe — process is alive."""
    return {"status": "live"}


async def _check_postgresql(db: AsyncSession) -> dict:
    """Check PostgreSQL connectivity."""
    try:
        start = time.monotonic()
        await asyncio.wait_for(db.execute(text("SELECT 1")), timeout=_HEALTH_CHECK_TIMEOUT)
        elapsed = time.monotonic() - start
        store_health_check_duration_seconds.labels(store="postgresql").observe(elapsed)
        store_health_status.labels(store="postgresql").set(1)
        return {"status": "ok", "_healthy": True}
    except Exception as exc:
        elapsed = time.monotonic() - start
        store_health_check_duration_seconds.labels(store="postgresql").observe(elapsed)
        store_health_status.labels(store="postgresql").set(0)
        logger.warning("readiness_check_failed", dependency="postgresql", error=str(exc))
        return {"status": "error", "detail": str(exc), "_healthy": False}


async def _check_redis(redis: Redis) -> dict:
    """Check Redis connectivity."""
    try:
        start = time.monotonic()
        await asyncio.wait_for(redis.ping(), timeout=_HEALTH_CHECK_TIMEOUT)  # type: ignore[misc]
        elapsed = time.monotonic() - start
        store_health_check_duration_seconds.labels(store="redis").observe(elapsed)
        store_health_status.labels(store="redis").set(1)
        return {"status": "ok", "_healthy": True}
    except Exception as exc:
        elapsed = time.monotonic() - start
        store_health_check_duration_seconds.labels(store="redis").observe(elapsed)
        store_health_status.labels(store="redis").set(0)
        logger.warning("readiness_check_failed", dependency="redis", error=str(exc))
        return {"status": "error", "detail": str(exc), "_healthy": False}


async def _check_clickhouse() -> dict:
    """Check ClickHouse connectivity (optional — degraded, not failing)."""
    start = time.monotonic()
    try:
        ch = get_clickhouse_client()
        ok = await asyncio.wait_for(ch.ping(), timeout=_HEALTH_CHECK_TIMEOUT)
        elapsed = time.monotonic() - start
        store_health_check_duration_seconds.labels(store="clickhouse").observe(elapsed)
        store_health_status.labels(store="clickhouse").set(1 if ok else 0)
        return {"status": "ok" if ok else "degraded", "_healthy": True}
    except Exception as exc:
        elapsed = time.monotonic() - start
        store_health_check_duration_seconds.labels(store="clickhouse").observe(elapsed)
        store_health_status.labels(store="clickhouse").set(0)
        logger.info("readiness_check_degraded", dependency="clickhouse", error=str(exc))
        return {"status": "degraded", "detail": str(exc), "_healthy": True}


async def _check_materialize(mz_client: MaterializeClient) -> dict:
    """Check Materialize connectivity (optional — degraded, not failing)."""
    start = time.monotonic()
    try:
        ok = await asyncio.wait_for(mz_client.ping(), timeout=_HEALTH_CHECK_TIMEOUT)
        elapsed = time.monotonic() - start
        store_health_check_duration_seconds.labels(store="materialize").observe(elapsed)
        store_health_status.labels(store="materialize").set(1 if ok else 0)
        return {"status": "ok" if ok else "degraded", "_healthy": True}
    except Exception as exc:
        elapsed = time.monotonic() - start
        store_health_check_duration_seconds.labels(store="materialize").observe(elapsed)
        store_health_status.labels(store="materialize").set(0)
        logger.info("readiness_check_degraded", dependency="materialize", error=str(exc))
        return {"status": "degraded", "detail": str(exc), "_healthy": True}


async def _check_redpanda() -> dict:
    """Check Redpanda connectivity (optional — degraded, not failing)."""
    try:
        redpanda_host = settings.redpanda_brokers.split(":")[0]
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"http://{redpanda_host}:9644/v1/status/ready",
                timeout=_HEALTH_CHECK_TIMEOUT,
            )
            return {
                "status": "ok" if resp.status_code == 200 else "degraded",
                "_healthy": True,
            }
    except Exception as exc:
        logger.info("readiness_check_degraded", dependency="redpanda", error=str(exc))
        return {"status": "degraded", "detail": str(exc), "_healthy": True}


@router.get("/health/ready")
async def readiness(
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    """Readiness probe — checks PostgreSQL, Redis, ClickHouse, Materialize, Redpanda.

    All checks run concurrently with a per-check timeout to prevent
    slow stores from blocking the entire readiness response.
    """
    mz_client: MaterializeClient = request.app.state.materialize_client
    results = await asyncio.gather(
        _check_postgresql(db),
        _check_redis(redis),
        _check_clickhouse(),
        _check_materialize(mz_client),
        _check_redpanda(),
    )

    names = ["postgresql", "redis", "clickhouse", "materialize", "redpanda"]
    checks: dict[str, dict] = {}
    healthy = True

    for name, result in zip(names, results):
        if not result.pop("_healthy", True):
            healthy = False
        checks[name] = result

    status_code = 200 if healthy else 503
    return JSONResponse(
        content={"status": "ready" if healthy else "not_ready", "checks": checks},
        status_code=status_code,
    )
