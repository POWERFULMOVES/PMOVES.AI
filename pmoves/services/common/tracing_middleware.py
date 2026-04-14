"""FastAPI middleware for OpenTelemetry distributed tracing.

Adds automatic span creation for every inbound HTTP request with trace
context propagation via W3C ``traceparent`` headers.  Falls back to a
no-op when OpenTelemetry packages are not installed.

Usage::

    from services.common.tracing_middleware import TracingMiddleware

    app = FastAPI()
    app.add_middleware(TracingMiddleware)

Compatible with existing Prometheus metrics — this middleware does not
interfere with ``prometheus_fastapi_instrumentator`` or similar.
"""

from __future__ import annotations

import logging
import time
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Graceful import
# ---------------------------------------------------------------------------
_tracing_enabled = False

try:
    from opentelemetry import trace, context as otel_context
    from opentelemetry.trace import SpanKind, Status, StatusCode, get_current_span
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.trace.propagation.tracecontext import (
        TraceContextTextMapPropagator,
    )
    from opentelemetry.context import Context

    _propagator = TraceContextTextMapPropagator()
    _tracing_enabled = True
except ImportError:
    _propagator = None  # type: ignore[assignment]


class TracingMiddleware(BaseHTTPMiddleware):
    """Starlette/FastAPI middleware that creates an OpenTelemetry span for
    every inbound HTTP request.

    * Extracts ``traceparent`` from incoming headers to link to upstream spans.
    * Records ``http.method``, ``http.url``, ``http.status_code``, and duration.
    * Sets ``ERROR`` status when the handler raises an exception.
    * Completely no-op when ``opentelemetry-*`` packages are absent.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if not _tracing_enabled:
            return await call_next(request)

        # Extract remote context from incoming headers.
        headers = dict(request.headers)
        ctx = _propagator.extract(headers) if _propagator else None

        method = request.method
        path = request.url.path
        span_name = f"{method} {path}"

        tracer = trace.get_tracer("pmoves.fastapi")

        # Use the extracted context as parent if present.
        token = None
        if ctx is not None:
            token = otel_context.attach(ctx)

        try:
            with tracer.start_as_current_span(
                span_name,
                kind=SpanKind.SERVER,
                attributes={
                    "http.method": method,
                    "http.url": str(request.url),
                    "http.scheme": request.url.scheme,
                    "http.host": request.url.hostname or "",
                    "http.target": path,
                    "http.flavor": request.scope.get("http_version", "1.1"),
                    "user_agent.original": request.headers.get("user-agent", ""),
                },
            ) as span:
                start = time.monotonic()
                try:
                    response = await call_next(request)
                    duration_ms = (time.monotonic() - start) * 1000

                    span.set_attribute("http.status_code", response.status_code)
                    span.set_attribute("http.response_duration_ms", round(duration_ms, 2))

                    if response.status_code >= 500:
                        span.set_status(Status(StatusCode.ERROR))
                    else:
                        span.set_status(Status(StatusCode.OK))

                    # Inject trace context into response headers for debugging.
                    response.headers["X-Trace-Id"] = format(
                        span.get_span_context().trace_id, "032x"
                    )

                    return response
                except Exception as exc:
                    span.set_status(Status(StatusCode.ERROR, str(exc)))
                    span.record_exception(exc)
                    raise
        finally:
            if token is not None:
                otel_context.detach(token)


__all__ = ["TracingMiddleware"]
