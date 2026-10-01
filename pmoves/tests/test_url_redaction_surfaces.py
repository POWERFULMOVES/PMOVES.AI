"""Credential-bearing URLs leave no surface unredacted (PR #3244 review follow-up).

One test per surface the dataflow sweep found: unauthenticated HTTP routes, a
raised exception, and connect-time log/print lines fed through generic names
(self.url, config.url, url). Every credential here is synthetic. Each test feeds
a URL WITH userinfo and asserts the secret is absent and the redaction marker is
present, so a test that never reached the sink cannot pass by accident.

Third-party libraries that are incidental to the assertion (web framework,
ASGI server, Google client, structlog, neo4j driver, feed/date parsers) are
replaced by small stubs, so every test RUNS under the merge-gate CI
requirements (.github/requirements-tests.txt). The service code under test --
the route handler, the log call, the raise -- is the real code.
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
needs_nats = pytest.mark.skipif(not REAL_NATS, reason="nats-py not installed")

PMOVES = Path(__file__).resolve().parents[1]
REPO = PMOVES.parent
SERVICES = PMOVES / "services"

SECRET = "SYNTHsecret"
NATS_WITH = f"nats://example-user:{SECRET}@nats:4222"
DB_WITH = f"postgresql://example-user:{SECRET}@db:5432/app"
HTTP_WITH = f"http://example-user:{SECRET}@supabase:54321"


class _Anything:
    """Absorbs any attribute access, call, decorator use or item assignment."""

    def __call__(self, *args, **_kwargs):
        return args[0] if len(args) == 1 and callable(args[0]) else _Anything()

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return _Anything()

    def __setitem__(self, _key, _value):
        pass

    def __getitem__(self, _key):
        return _Anything()

    def __iter__(self):
        return iter(())


class _Permissive:
    """Stand-in for a framework object: records @route views, ignores everything else."""

    def __init__(self, *_args, **_kwargs):
        self.routes = {}

    def route(self, path, **_kwargs):
        def deco(fn):
            self.routes[path] = fn
            return fn
        return deco

    def __call__(self, *args, **_kwargs):
        return args[0] if len(args) == 1 and callable(args[0]) else self

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return _Anything()


def _module(name: str, **attrs) -> ModuleType:
    mod = ModuleType(name)
    mod.__dict__.update(attrs)

    def _any(attr):  # PEP 562: any other public name
        if attr.startswith("__"):
            raise AttributeError(attr)
        return _Anything()

    mod.__getattr__ = _any
    return mod


def _stub(monkeypatch, name: str, module: ModuleType, *, only_if_missing: bool = True) -> None:
    if only_if_missing:
        try:
            importlib.import_module(name)
            return
        except ImportError:
            pass
    parts = name.split(".")
    for i in range(1, len(parts)):
        parent = ".".join(parts[:i])
        if parent not in sys.modules:
            monkeypatch.setitem(sys.modules, parent, _module(parent))
    monkeypatch.setitem(sys.modules, name, module)
    if len(parts) > 1:
        monkeypatch.setattr(sys.modules[".".join(parts[:-1])], parts[-1], module, raising=False)


def _stub_uvicorn(monkeypatch):
    _stub(monkeypatch, "uvicorn", _module("uvicorn", run=lambda *a, **k: None))


def _stub_supabase(monkeypatch):
    try:
        from supabase import Client, create_client  # noqa: F401
    except ImportError:
        _stub(monkeypatch, "supabase", _module("supabase", Client=_Permissive, create_client=lambda *a, **k: _Anything()),
              only_if_missing=False)


def _stub_channel_monitor_deps(monkeypatch):
    _stub(monkeypatch, "googleapiclient.discovery", _module("googleapiclient.discovery", build=lambda *a, **k: None))
    _stub(monkeypatch, "googleapiclient.errors", _module("googleapiclient.errors", HttpError=type("HttpError", (Exception,), {})))
    _stub(monkeypatch, "google.oauth2.credentials", _module("google.oauth2.credentials", Credentials=_Permissive))
    _stub(monkeypatch, "google.auth.transport.requests", _module("google.auth.transport.requests", Request=_Permissive))
    _stub(monkeypatch, "feedparser", _module("feedparser", parse=lambda *a, **k: SimpleNamespace(entries=[])))
    _stub(monkeypatch, "dateutil.parser", _module("dateutil.parser", parse=lambda *a, **k: None))

    async def _no_pool(*_args, **_kwargs):
        raise OSError("asyncpg stub: no database in unit tests")

    _stub(monkeypatch, "asyncpg", _module(
        "asyncpg", create_pool=_no_pool, Pool=object,
        PostgresConnectionError=type("PostgresConnectionError", (Exception,), {}),
    ))


class _StructlogRecorder:
    def __init__(self):
        self.events = []

    def bind(self, **_kwargs):
        return self

    def __getattr__(self, level):
        def log(event, *args, **kwargs):
            self.events.append({"level": level, "event": event, "args": args, **kwargs})
        return log


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
    from fastapi.testclient import TestClient

    _stub_uvicorn(monkeypatch)

    monkeypatch.setenv("NATS_URL", NATS_WITH)
    monkeypatch.setenv("SUPABASE_URL", HTTP_WITH)
    svc = SERVICES / "model-registry"
    module = _fresh(monkeypatch, "model_registry_main", svc / "main.py", paths=[svc], purge=["hf_client"])
    response = TestClient(module.app).get("/healthz")  # no `with`: lifespan (NATS/Supabase) not started
    assert response.status_code == 200
    _assert_redacted(response.text)


def test_tokenism_root_route(monkeypatch):
    # Flask is always stubbed: the assertion is on the "/" view's return value.
    flask = _module("flask", Flask=_Permissive, Blueprint=_Permissive,
                    jsonify=lambda *a, **k: a[0] if a else k)
    _stub(monkeypatch, "flask", flask, only_if_missing=False)
    _stub(monkeypatch, "flask_cors", _module("flask_cors", CORS=lambda *a, **k: None), only_if_missing=False)
    _stub(monkeypatch, "structlog", _module("structlog", get_logger=lambda *a, **k: _StructlogRecorder()))
    monkeypatch.setenv("NATS_URL", NATS_WITH)
    monkeypatch.setenv("SUPABASE_URL", HTTP_WITH)
    svc = SERVICES / "tokenism-simulator"
    # The service ships its own top-level `services` package, so services.common
    # is absent and the inline redact_url fallback is what runs here.
    module = _fresh(monkeypatch, "tokenism_app", svc / "app.py", paths=[svc],
                    purge=["config", "app", "services", "api", "nats_consumer"])
    body, status = module.create_app().routes["/"]()
    assert status == 200
    _assert_redacted(json.dumps(body))


def test_channel_monitor_healthz(monkeypatch, tmp_path):
    _stub_channel_monitor_deps(monkeypatch)
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
    _stub_uvicorn(monkeypatch)
    _stub_supabase(monkeypatch)
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
    _stub_channel_monitor_deps(monkeypatch)
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
    # structlog and the neo4j driver are always stubbed; the recorder captures the
    # real NATSHandler.connect() log call.
    recorder = _StructlogRecorder()
    _stub(monkeypatch, "structlog", _module("structlog", get_logger=lambda *a, **k: recorder), only_if_missing=False)
    exc = {n: type(n, (Exception,), {}) for n in ("ServiceUnavailable", "AuthError", "Neo4jError")}
    _stub(monkeypatch, "neo4j.exceptions", _module("neo4j.exceptions", **exc), only_if_missing=False)
    _stub(monkeypatch, "neo4j", _module("neo4j", GraphDatabase=_Permissive(), Driver=object,
                                        ManagedTransaction=object, exceptions=sys.modules["neo4j.exceptions"]),
          only_if_missing=False)
    svc = SERVICES / "graph-linker"
    module = _fresh(
        monkeypatch, "graph_linker_nats_handler", svc / "nats_handler.py",
        paths=[svc], purge=["config", "models", "neo4j_client", "chit_signer"],
    )
    monkeypatch.setattr(module, "NATSClient", _FakeNC)
    settings = SimpleNamespace(
        nats_url=NATS_WITH, nats_name="t", nats_reconnect_wait=1,
        nats_max_reconnect_attempts=1, nats_pending_msg_limit=1,
    )
    asyncio.run(module.NATSHandler(settings, None).connect())
    assert any(e["event"] == "nats.connected" for e in recorder.events)
    _assert_redacted(json.dumps(recorder.events, default=str))


# ----------------------- sinks fed by the former private redactors (round 3)

# A password with an unencoded '/' made every private copy return the URL verbatim.
NATS_SLASH = f"nats://example-user:{SECRET}/x@nats:4222"


class _OkNC(_FakeNC):
    async def subscribe(self, *_args, **_kwargs):
        return None


@needs_nats
def test_agent_zero_event_bus_log(monkeypatch, caplog):
    module = _fresh(monkeypatch, "a0_events_bus", SERVICES / "agent-zero" / "python" / "events" / "bus.py")
    monkeypatch.setattr(module, "NATSClient", _OkNC)
    bus = module.EventBus(nats_url=NATS_SLASH, use_jetstream=False)
    with caplog.at_level(logging.INFO):
        asyncio.run(bus.connect())
    _assert_redacted(caplog.text)


@needs_nats
def test_supaserch_connect_log(monkeypatch, caplog):
    monkeypatch.setenv("NATS_URL", NATS_SLASH)
    # Imported once: the module registers Prometheus collectors at import time.
    module = _fresh(monkeypatch, "supaserch_app", SERVICES / "supaserch" / "app.py", paths=[SERVICES / "supaserch"])
    for reachable in (True, False):
        class _NC(_OkNC):
            async def connect(self, *_args, **_kwargs):
                if not reachable:
                    raise OSError("unreachable")

        monkeypatch.setattr(module, "NATS", _NC)
        caplog.clear()
        with caplog.at_level(logging.INFO):
            asyncio.run(module._connect_nats())
        _assert_redacted(caplog.text)


@needs_nats
def test_voice_relay_redacted_constant(monkeypatch):
    monkeypatch.setenv("NATS_URL", NATS_SLASH)
    module = _fresh(monkeypatch, "voice_relay_main", SERVICES / "voice-relay" / "main.py", paths=[SERVICES / "voice-relay"])
    _assert_redacted(module.NATS_URL_REDACTED)


@needs_nats
def test_flute_gateway_imports_and_redacts(monkeypatch):
    """flute-gateway's old _redact_url_password raised ValueError at IMPORT on this input."""
    monkeypatch.setenv("NATS_URL", NATS_SLASH)
    svc = SERVICES / "flute-gateway"
    module = _fresh(monkeypatch, "flute_gateway_main", svc / "main.py", paths=[svc])
    _assert_redacted(module.NATS_URL_REDACTED)
