"""OpenTelemetry tracing instrumentation for PMOVES services.

Provides distributed tracing utilities that integrate with the OpenTelemetry
Collector and Jaeger backend.  All OpenTelemetry imports are wrapped in
try/except so services without the ``opentelemetry-*`` packages still start.

Usage::

    from services.common.tracing import setup_tracing, get_tracer

    setup_tracing("my-service")
    tracer = get_tracer("my-service")

    # Inside a request handler the middleware creates the parent span;
    # child spans are created automatically via ``tracer.start_span()``.
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Any, Dict, Generator

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Graceful import — services without opentelemetry packages still work
# ---------------------------------------------------------------------------
_tracing_enabled = False

try:
    from opentelemetry import trace, context as otel_context
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.sampling import ParentBasedTraceIdRatio
    from opentelemetry.sdk.resources import Resource, SERVICE_NAME
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
        OTLPSpanExporter,
    )
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.trace.propagation.tracecontext import (
        TraceContextTextMapPropagator,
    )
    from opentelemetry.trace import (
        get_current_span,
        set_span_in_context,
        SpanKind,
        Status,
        StatusCode,
    )

    _propagator = TraceContextTextMapPropagator()
    _tracing_enabled = True
    logger.debug("OpenTelemetry tracing is available")
except ImportError:
    _propagator = None  # type: ignore[assignment]
    logger.debug(
        "OpenTelemetry packages not installed — tracing disabled (opt-in)"
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def setup_tracing(
    service_name: str,
    endpoint: str | None = None,
    sample_rate: float = 1.0,
) -> bool:
    """Initialize the OpenTelemetry SDK for *service_name*.

    Args:
        service_name: Logical service name used in trace attributes.
        endpoint: OTLP gRPC endpoint.  Defaults to the ``OTEL_EXPORTER_OTLP_ENDPOINT``
            env-var, falling back to ``http://otel-collector:4317``.
        sample_rate: Fraction of traces to sample (0.0 – 1.0).

    Returns:
        ``True`` if tracing was successfully initialised, ``False`` otherwise.
    """
    if not _tracing_enabled:
        logger.info("Tracing skipped — opentelemetry packages not installed")
        return False

    try:
        otlp_endpoint = endpoint or os.getenv(
            "OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317"
        )

        resource = Resource.create({SERVICE_NAME: service_name})
        provider = TracerProvider(
            resource=resource,
            sampler=ParentBasedTraceIdRatio(rate=sample_rate),
        )

        exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(exporter))

        trace.set_tracer_provider(provider)
        logger.info(
            "Tracing initialised for %s → %s (sample_rate=%.2f)",
            service_name,
            otlp_endpoint,
            sample_rate,
        )
        return True
    except Exception as exc:
        logger.warning("Failed to initialise tracing: %s", exc)
        return False


def get_tracer(name: str) -> Any:
    """Return a named :class:`opentelemetry.trace.Tracer`.

    Falls back to a no-op tracer when the SDK is not available.
    """
    if _tracing_enabled:
        return trace.get_tracer(name)
    return _NoOpTracer()


def inject_trace_headers(headers: Dict[str, str]) -> Dict[str, str]:
    """Inject the current trace context into *headers*.

    Returns a **new** dict with the W3C ``traceparent`` and ``tracestate``
    headers added.  Safe to call when tracing is disabled (returns *headers*
    unchanged).
    """
    if not _tracing_enabled or _propagator is None:
        return headers
    mutated = dict(headers)
    try:
        _propagator.inject(mutated)
    except Exception as exc:
        logger.debug("Failed to inject trace headers: %s", exc)
    return mutated


def extract_trace_headers(headers: Dict[str, str]) -> Any:
    """Extract a trace context from *headers*.

    Returns an OpenTelemetry ``Context`` object or ``None`` when tracing is
    disabled or the headers contain no trace information.
    """
    if not _tracing_enabled or _propagator is None:
        return None
    try:
        ctx = _propagator.extract(headers)
        return ctx
    except Exception as exc:
        logger.debug("Failed to extract trace headers: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Context managers for span creation
# ---------------------------------------------------------------------------

@contextmanager
def trace_nats_message(
    subject: str,
    data: bytes | str | None = None,
) -> Generator[Any, None, None]:
    """Context manager that wraps a NATS message handler in a span.

    Usage::

        with trace_nats_message("compute.nodes.heartbeat", msg.data) as span:
            # process message
            span.set_attribute("message.size", len(msg.data))
    """
    if not _tracing_enabled:
        yield None
        return

    tracer = trace.get_tracer("pmoves.nats")
    with tracer.start_as_current_span(
        f"nats.receive {subject}",
        kind=SpanKind.CONSUMER,
        attributes={
            "messaging.system": "nats",
            "messaging.destination": subject,
            "messaging.operation": "receive",
        },
    ) as span:
        if data is not None:
            span.set_attribute("message.size", len(data) if data else 0)
        try:
            yield span
        except Exception as exc:
            span.set_status(Status(StatusCode.ERROR, str(exc)))
            span.record_exception(exc)
            raise


@contextmanager
def trace_http_request(
    method: str,
    url: str,
) -> Generator[Any, None, None]:
    """Context manager that wraps an outbound HTTP request in a span.

    Usage::

        with trace_http_request("GET", "http://api/service") as span:
            resp = httpx.get(url)
            span.set_attribute("http.status_code", resp.status_code)
    """
    if not _tracing_enabled:
        yield None
        return

    tracer = trace.get_tracer("pmoves.http")
    with tracer.start_as_current_span(
        f"HTTP {method} {url}",
        kind=SpanKind.CLIENT,
        attributes={
            "http.method": method,
            "http.url": url,
        },
    ) as span:
        try:
            yield span
        except Exception as exc:
            span.set_status(Status(StatusCode.ERROR, str(exc)))
            span.record_exception(exc)
            raise


# ---------------------------------------------------------------------------
# No-op tracer fallback
# ---------------------------------------------------------------------------

class _NoOpTracer:
    """Minimal stand-in when OpenTelemetry is not installed."""

    def start_span(self, *args: Any, **kwargs: Any) -> _NoOpSpan:
        return _NoOpSpan()

    def start_as_current_span(
        self, *args: Any, **kwargs: Any
    ) -> _NoOpSpanContext:
        return _NoOpSpanContext()


class _NoOpSpan:
    """Minimal span stand-in."""

    def set_attribute(self, *args: Any, **kwargs: Any) -> None:
        pass

    def set_status(self, *args: Any, **kwargs: Any) -> None:
        pass

    def record_exception(self, *args: Any, **kwargs: Any) -> None:
        pass

    def __enter__(self) -> "_NoOpSpan":
        return self

    def __exit__(self, *args: Any) -> None:
        pass


class _NoOpSpanContext:
    """Context manager that yields a no-op span."""

    def __enter__(self) -> _NoOpSpan:
        return _NoOpSpan()

    def __exit__(self, *args: Any) -> None:
        pass


__all__ = [
    "setup_tracing",
    "get_tracer",
    "trace_nats_message",
    "trace_http_request",
    "inject_trace_headers",
    "extract_trace_headers",
]
