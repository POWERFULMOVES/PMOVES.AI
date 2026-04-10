"""Shared health endpoint factory for PMOVES FastAPI services.

Provides a standard ``/healthz`` endpoint that services can customise
with their own checks while maintaining a consistent response shape.

Usage::

    from services.common.health import create_health_endpoint

    async def my_checks() -> dict:
        return {"db": "ok", "cache": "degraded"}

    app.get("/healthz")(create_health_endpoint(
        service_name="my-service",
        extra_checks=my_checks,
    ))
"""

from __future__ import annotations

import os
import time
from typing import Any, Callable, Coroutine, Dict, Optional

from fastapi import FastAPI


# Module-level startup timestamp (set on first import of this module by a service).
_process_start_time: float = time.time()


def get_uptime_seconds() -> float:
    """Return seconds since this module was first imported."""
    return time.time() - _process_start_time


def build_health_payload(
    *,
    service_name: str,
    status: str = "ok",
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a standard health-check response dictionary.

    Args:
        service_name: Human-readable service identifier.
        status: Overall status string (``"ok"``, ``"degraded"``, ``"stopped"``).
        extra: Arbitrary service-specific health data.

    Returns:
        A dictionary suitable for JSON serialisation.
    """
    payload: Dict[str, Any] = {
        "status": status,
        "service": service_name,
        "uptime_seconds": round(get_uptime_seconds(), 1),
    }
    if extra:
        payload.update(extra)
    return payload


def create_health_endpoint(
    *,
    service_name: str,
    extra_checks: Optional[Callable[[], Coroutine[Any, Any, Dict[str, Any]]]] = None,
    nats_client_getter: Optional[Callable[[], Any]] = None,
) -> Callable[..., Coroutine[Any, Any, Dict[str, Any]]]:
    """Return a FastAPI-compatible async health-check handler.

    The returned coroutine has the signature ``async def healthz() -> dict``
    and can be wired directly to a route::

        app.get("/healthz")(create_health_endpoint(service_name="my-svc"))

    Args:
        service_name: Name included in the response payload.
        extra_checks: Optional async callable returning additional data.
        nats_client_getter: Optional callable returning a NATS client whose
            ``is_connected`` attribute is checked.
    """
    async def healthz() -> Dict[str, Any]:
        status = "ok"
        extra: Dict[str, Any] = {}

        # NATS connectivity
        if nats_client_getter is not None:
            try:
                nc = nats_client_getter()
                nats_connected = bool(getattr(nc, "is_connected", False))
                extra["nats"] = nats_connected
                if not nats_connected:
                    status = "degraded"
            except Exception:
                extra["nats"] = False
                status = "degraded"

        # Custom checks
        if extra_checks is not None:
            try:
                custom = await extra_checks()
                extra.update(custom)
                # If any custom check signals unhealthy, degrade
                if custom.get("status") == "error":
                    status = "degraded"
            except Exception as exc:
                extra["check_error"] = str(exc)
                status = "degraded"

        return build_health_payload(
            service_name=service_name,
            status=status,
            extra=extra,
        )

    return healthz


def register_health_endpoint(
    app: FastAPI,
    *,
    service_name: str,
    path: str = "/healthz",
    **kwargs: Any,
) -> None:
    """Convenience: create and register a health endpoint on *app*.

    Usage::

        register_health_endpoint(app, service_name="my-service")
    """
    handler = create_health_endpoint(service_name=service_name, **kwargs)
    app.add_api_route(path, handler, methods=["GET"])


__all__ = [
    "build_health_payload",
    "create_health_endpoint",
    "register_health_endpoint",
    "get_uptime_seconds",
]
