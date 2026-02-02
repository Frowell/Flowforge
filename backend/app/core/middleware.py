"""Observability middleware — request IDs, logging, and metrics."""

import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.metrics import http_request_duration_seconds, http_requests_total


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """Injects request_id, logs requests, and records HTTP metrics.

    WebSocket upgrade requests pass through without instrumentation —
    they get their own session_id in the WS handler.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if request.scope.get("type") == "websocket":
            return await call_next(request)

        request_id = str(uuid.uuid4())
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        logger = structlog.stdlib.get_logger("flowforge.http")
        start = time.perf_counter()

        response = await call_next(request)

        duration = time.perf_counter() - start
        status = response.status_code

        # Use the route pattern (low cardinality) not the resolved path
        route = request.scope.get("route")
        path = route.path if route else request.url.path
        method = request.method

        http_requests_total.labels(method=method, path=path, status=status).inc()
        http_request_duration_seconds.labels(method=method, path=path).observe(duration)

        response.headers["X-Request-ID"] = request_id

        logger.info(
            "request_completed",
            method=method,
            path=path,
            status=status,
            duration_ms=round(duration * 1000, 2),
        )

        structlog.contextvars.clear_contextvars()
        return response
