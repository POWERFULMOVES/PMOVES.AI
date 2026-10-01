"""Credential-bearing URLs leave no surface unredacted (PR #3244 review follow-up).

One test per surface the dataflow sweep found: unauthenticated HTTP routes, a
raised exception, and connect-time log/print lines fed through generic names
(self.url, config.url, url). Every credential here is synthetic. Each test feeds
a URL WITH userinfo and asserts the secret is absent and the redaction marker is
present, so a test that never reached the sink cannot pass by accident.

Surfaces whose service dependencies are not installed are SKIPPED with the
missing module named; a skip is not a pass.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import logging
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from urllib.parse import urlparse

import pytest

# Import the real nats-py during collection, before the session-wide
# stub_external_modules fixture can install its fake `nats` module.
try:
    import nats  # noqa: F401
    import nats.aio.client  # noqa: F401
    import nats.aio.msg  # noqa: F401
    import nats.aio.subscription  # noqa: F401
    import nats.errors  # noqa: F401

    REAL_NATS = True
except ImportError:
    REAL_NATS = False
try:  # same reason: the session stub would shadow the real driver
    import neo4j  # noqa: F401
except ImportError:
    pass

needs_nats = pytest.mark.skipif(not REAL_NATS, reason="nats-py not installed")

PMOVES = Path(__file__).resolve().parents[1]
REPO = PMOVES.parent
SERVICES = PMOVES / "services"

SECRET = "SYNTHsecret"
NATS_WITH = f"nats://example-user:{SECRET}@nats:4222"
DB_WITH = f"postgresql://example-user:{SECRET}@db:5432/app"
HTTP_WITH = f"http://example-user:{SECRET}@supabase:54321"


def _assert_redacted(text: str) -> None:
    assert SECRET not in text
    assert "***@" in text, "sink was not reached (no redaction marker in output)"


def _fresh(monkeypatch, name: str, path: Path, *, paths=(), purge=(), package: bool = False) -> ModuleType:
    """Import *path* as *name* with a clean module cache for the given prefixes."""
    for p in (REPO, PMOVES, *paths):
        monkeypatch.syspath_prepend(str(p))
    for mod in list(sys.modules):
        if any(mod == x or mod.startswith(x + ".") for x in (name, *purge)):
            monkeypatch.delitem(sys.modules, mod)
    kwargs = {"submodule_search_locations": [str(path.parent)]} if package else {}
    spec = importlib.util.spec_from_file_location(name, path, **kwargs)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------- HTTP routes


def test_model_registry_healthz(monkeypatch):
    pytest.importorskip("jsonschema")
    from fastapi.testclient import TestClient

    monkeypatch.setenv("NATS_URL", NATS_WITH)
    monkeypatch.setenv("SUPABASE_URL", HTTP_WITH)
    svc = SERVICES / "model-registry"
    module = _fresh(monkeypatch, "model_registry_main", svc / "main.py", paths=[svc], purge=["hf_client"])
    response = TestClient(module.app).get("/healthz")  # no `with`: lifespan (NATS/Supabase) not started
    assert response.status_code == 200
    _assert_redacted(response.text)


def test_tokenism_root_route(monkeypatch):
    pytest.importorskip("flask")
    pytest.importorskip("flask_cors")
    pytest.importorskip("numpy")
    monkeypatch.setenv("NATS_URL", NATS_WITH)
    monkeypatch.setenv("SUPABASE_URL", HTTP_WITH)
    svc = SERVICES / "tokenism-simulator"
    # The service ships its own top-level `services` package, so services.common
    # is absent and the inline redact_url fallback is what runs here.
    module = _fresh(monkeypatch, "tokenism_app", svc / "app.py", paths=[svc], purge=["config", "app", "services"])
    response = module.create_app().test_client().get("/")
    assert response.status_code == 200
    _assert_redacted(response.get_data(as_text=True))


def test_channel_monitor_healthz(monkeypatch, tmp_path):
    pytest.importorskip("googleapiclient")
    monkeypatch.setenv("CHANNEL_MONITOR_CONFIG_PATH", str(tmp_path / "channel_monitor.json"))
    monkeypatch.setenv("CHANNEL_MONITOR_DATABASE_URL", DB_WITH)
    monkeypatch.setenv("CHANNEL_MONITOR_QUEUE_URL", HTTP_WITH + "/yt/ingest")
    svc = SERVICES / "channel-monitor"
    monkeypatch.syspath_prepend(str(svc))
    for mod in list(sys.modules):
        if mod == "channel_monitor" or mod.startswith("channel_monitor."):
            monkeypatch.delitem(sys.modules, mod)
    import channel_monitor.main as main

    async def healthy():
        return True

    monkeypatch.setattr(main.monitor, "check_database_health", healthy)
    body = json.dumps(asyncio.run(main.healthz()))
    _assert_redacted(body)


def test_fleet_sentinel_healthz_listener_error(monkeypatch):
    pytest.importorskip("fastapi")
    monkeypatch.setenv("NATS_URL", NATS_WITH)
    module = _fresh(monkeypatch, "fleet_sentinel_main", SERVICES / "fleet_sentinel" / "main.py")
    listener_mod = importlib.import_module("services.common.nats_service_listener")

    class _DeadListener:
        def __init__(self, **_kwargs):
            pass

        async def start(self):
            return False

    monkeypatch.setattr(listener_mod, "ServiceAnnouncementListener", _DeadListener)
    assert asyncio.run(module.sentinel.start_listener()) is False
    body = json.dumps(asyncio.run(module.healthz()), default=str)
    _assert_redacted(body)


def test_container_agent_nats_probe(monkeypatch):
    pytest.importorskip("aiohttp")
    monkeypatch.setenv("NATS_URL", NATS_WITH)
    module = _fresh(monkeypatch, "container_agent_app", SERVICES / "container-agent" / "app.py")

    class _NC:
        connected_url = urlparse(NATS_WITH)
        _server_info: dict = {}

        async def close(self):
            return None

    fake = ModuleType("nats")

    async def ok_connect(**_kwargs):
        return _NC()

    fake.connect = ok_connect
    monkeypatch.setitem(sys.modules, "nats", fake)
    _assert_redacted(json.dumps(asyncio.run(module.check_nats())))

    async def bad_connect(**_kwargs):
        raise OSError("unreachable")

    fake.connect = bad_connect
    _assert_redacted(json.dumps(asyncio.run(module.check_nats())))


@needs_nats
def test_benchmark_runner_stats(monkeypatch):
    pkg = SERVICES / "benchmark-runner"
    _fresh(monkeypatch, "benchmark_runner", pkg / "__init__.py", package=True)
    server = importlib.import_module("benchmark_runner.server")
    stats = server.BenchmarkServer(nats_url=NATS_WITH).get_stats()
    _assert_redacted(json.dumps(stats, default=str))


# ------------------------------------------------------------------ raise


def test_channel_monitor_db_failure_message(monkeypatch, tmp_path, caplog):
    pytest.importorskip("googleapiclient")
    svc = SERVICES / "channel-monitor"
    monkeypatch.syspath_prepend(str(svc))
    for mod in list(sys.modules):
        if mod == "channel_monitor" or mod.startswith("channel_monitor."):
            monkeypatch.delitem(sys.modules, mod)
    import channel_monitor.monitor as monitor_mod

    async def refuse(*_args, **_kwargs):
        raise OSError("connection refused")

    monkeypatch.setattr(monitor_mod.asyncpg, "create_pool", refuse)
    cm = monitor_mod.ChannelMonitor(tmp_path / "cfg.json", HTTP_WITH, DB_WITH)
    with caplog.at_level(logging.CRITICAL), pytest.raises(RuntimeError) as err:
        asyncio.run(cm.start())
    _assert_redacted(str(err.value))
    _assert_redacted(caplog.text)


# ------------------------------------------------- logs via generic names


class _FakeNC:
    is_connected = True

    def jetstream(self):
        return SimpleNamespace()

    async def subscribe(self, *_args, **_kwargs):
        raise asyncio.CancelledError  # stop nats-echo right after its connect print

    async def connect(self, *_args, **_kwargs):
        return None

    async def close(self):
        return None


@needs_nats
def test_tokenism_nats_client_log(monkeypatch, caplog):
    svc = SERVICES / "tokenism-simulator"
    _fresh(monkeypatch, "config", svc / "config" / "__init__.py", paths=[svc], purge=["services"], package=True)
    nats_cfg = importlib.import_module("config.nats")

    async def connect(**_kwargs):
        return _FakeNC()

    monkeypatch.setattr(nats_cfg.nats, "connect", connect)
    client = nats_cfg.NATSClient(nats_cfg.NATSConfig(url=NATS_WITH, jetstream_enabled=False))
    with caplog.at_level(logging.INFO):
        asyncio.run(client.connect())
    _assert_redacted(caplog.text)


@needs_nats
def test_consciousness_publisher_log(monkeypatch, caplog):
    svc = SERVICES / "consciousness-service"
    module = _fresh(monkeypatch, "consciousness_main", svc / "main.py", paths=[svc])

    async def connect(*_args, **_kwargs):
        return _FakeNC()

    monkeypatch.setattr(module.nats, "connect", connect)
    with caplog.at_level(logging.INFO):
        asyncio.run(module.NATSPublisher(NATS_WITH).connect())
    _assert_redacted(caplog.text)


@needs_nats
def test_nats_echo_print(monkeypatch, capsys):
    module = _fresh(monkeypatch, "nats_echo", SERVICES / "nats-echo" / "nats_echo.py")
    monkeypatch.setattr(module.nats, "NATS", _FakeNC)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(module.main("demo.subject", NATS_WITH))
    _assert_redacted(capsys.readouterr().out)


@needs_nats
def test_graph_linker_connect_log(monkeypatch):
    structlog = pytest.importorskip("structlog")
    pytest.importorskip("neo4j")
    svc = SERVICES / "graph-linker"
    module = _fresh(
        monkeypatch, "graph_linker_nats_handler", svc / "nats_handler.py",
        paths=[svc], purge=["config", "models", "neo4j_client"],
    )
    monkeypatch.setattr(module, "NATSClient", _FakeNC)
    settings = SimpleNamespace(
        nats_url=NATS_WITH, nats_name="t", nats_reconnect_wait=1,
        nats_max_reconnect_attempts=1, nats_pending_msg_limit=1,
    )
    with structlog.testing.capture_logs() as logs:
        asyncio.run(module.NATSHandler(settings, None).connect())
    _assert_redacted(json.dumps(logs, default=str))
