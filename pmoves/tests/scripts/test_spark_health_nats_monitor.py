"""spark_health must probe the PUBLISHED NATS monitor port, not the container one.

8222 is the NATS monitor port inside the container. No compose layout in this
repo publishes it on a SPARK host (base compose publishes
``${NATS_MONITORING_PORT:-9223}:8222``), so the old 8222 default reported a
healthy hub as DOWN. 8222 stays as a fallback for the Z890 leaf and the
standalone cipher stack, which do publish it.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "pmoves" / "scripts" / "spark_health.py"


@pytest.fixture()
def spark_health(monkeypatch):
    monkeypatch.delenv("SPARK_NATS_URL", raising=False)
    monkeypatch.delenv("NATS_MONITORING_PORT", raising=False)
    spec = importlib.util.spec_from_file_location("spark_health_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_default_tries_published_port_before_container_port(spark_health):
    assert spark_health._nats_monitor_urls() == [
        "http://localhost:9223/healthz",
        "http://localhost:8222/healthz",
    ]


def test_monitoring_port_env_is_honoured_and_deduplicated(spark_health, monkeypatch):
    monkeypatch.setenv("NATS_MONITORING_PORT", "8222")
    assert spark_health._nats_monitor_urls() == ["http://localhost:8222/healthz"]


def test_explicit_override_is_tried_first(spark_health, monkeypatch):
    monkeypatch.setenv("SPARK_NATS_URL", "http://localhost:19999/healthz")
    urls = spark_health._nats_monitor_urls()
    assert urls[0] == "http://localhost:19999/healthz"
    assert urls[1:] == [
        "http://localhost:9223/healthz",
        "http://localhost:8222/healthz",
    ]


def test_main_wires_the_helper(spark_health):
    """Production change that would make this fail: re-inlining a literal
    8222 list in main() and leaving the helper unused."""
    source = SCRIPT.read_text(encoding="utf-8")
    assert '"nats-local": _nats_monitor_urls(),' in source
    assert "localhost:8222/health\"" not in source
