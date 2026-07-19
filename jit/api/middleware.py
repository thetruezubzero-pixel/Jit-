"""
HTTP middleware for the Jit API.

Sits between incoming requests and the routers: assigns a request ID,
times the request, and logs method/path/status/duration for every call.
"""

from __future__ import annotations

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("jit.api")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Stamps each request with an ID, times it, and logs the outcome.

    Adds ``X-Request-ID`` and ``X-Process-Time`` response headers so
    clients (including the bundled frontend) can correlate a response
    with a server-side log line.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        start = time.perf_counter()

        response = await call_next(request)

        duration_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = f"{duration_ms:.2f}ms"

        logger.info(
            "%s %s -> %s (%.2fms) [%s]",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            request_id,
        )
        return response
