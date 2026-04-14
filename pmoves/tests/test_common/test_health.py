import asyncio
import importlib
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

repo_root = Path(__file__).resolve().parents[3]
if str(repo_root) not in sys.path:
    sys.path.append(str(repo_root))

sys.modules.setdefault("services", importlib.import_module("pmoves.services"))

from services.common.health import (
    build_health_payload,
    create_health_endpoint,
    get_uptime_seconds,
)


def test_build_health_payload_status_ok():
    """build_health_payload returns correct structure with status='ok'."""
    payload = build_health_payload(service_name="test-svc", status="ok")
    assert payload["status"] == "ok"
    assert payload["service"] == "test-svc"
    assert "uptime_seconds" in payload
    assert isinstance(payload["uptime_seconds"], float)


def test_build_health_payload_custom_status():
    """build_health_payload passes through custom status."""
    payload = build_health_payload(
        service_name="my-svc",
        status="degraded",
        extra={"db": "unhealthy"},
    )
    assert payload["status"] == "degraded"
    assert payload["service"] == "my-svc"
    assert payload["db"] == "unhealthy"


def test_get_uptime_seconds_positive():
    """get_uptime_seconds returns a positive value."""
    uptime = get_uptime_seconds()
    assert uptime > 0


def test_create_health_endpoint_returns_callable():
    """create_health_endpoint returns an async callable."""
    handler = create_health_endpoint(service_name="test-svc")
    assert callable(handler)
    assert asyncio.iscoroutinefunction(handler)
