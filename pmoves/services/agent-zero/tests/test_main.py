from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any, Callable, Dict

import httpx
import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def load_service_module() -> Callable[[str, str], ModuleType]:
    """Import a service module from the pmoves tree by relative path."""
    cache: Dict[str, ModuleType] = {}
    base = Path(__file__).resolve().parents[3]

    def _load(name: str, relative_path: str) -> ModuleType:
        if name in cache:
            return cache[name]
        module_path = base / relative_path
        spec = importlib.util.spec_from_file_location(name, module_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load module {name} from {module_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        cache[name] = module
        return module

    return _load


def _prepare_agent_zero(module, monkeypatch):
    monkeypatch.setattr(module, "NATS_ANNOUNCE_AVAILABLE", False)
    monkeypatch.setattr(module.runtime_config, "entrypoint", str(Path(module.__file__)))

    async def _fake_announce_service(*args, **kwargs):
        return None

    monkeypatch.setattr(module, "NATS_ANNOUNCE_AVAILABLE", False, raising=False)
    monkeypatch.setattr(module, "announce_service", _fake_announce_service, raising=False)

    async def _fake_start():
        return None

    async def _fake_stop():
        return None

    async def _fake_ensure():
        return None

    monkeypatch.setattr(module.process_manager, "start", _fake_start)
    monkeypatch.setattr(module.process_manager, "stop", _fake_stop)
    monkeypatch.setattr(module.process_manager, "ensure_running", _fake_ensure)

    async def _fake_controller_start():
        module.event_controller._started = True
        module.event_controller._nc = SimpleNamespace(is_connected=True)

    async def _fake_controller_stop():
        module.event_controller._started = False
        module.event_controller._nc = None

    monkeypatch.setattr(module.event_controller, "start", _fake_controller_start)
    monkeypatch.setattr(module.event_controller, "stop", _fake_controller_stop)
    module.event_controller._started = False
    module.event_controller._nc = None
    module._controller_ready = asyncio.Event()
    module._controller_shutdown = asyncio.Event()
    return module


class _DummyAsyncClient:
    def __init__(self, captured: dict[str, dict[str, object]], *args: Any, **kwargs: Any) -> None:
        captured["client"] = {"timeout": kwargs.get("timeout")}
        self._captured = captured

    async def __aenter__(self) -> "_DummyAsyncClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def post(self, url: str, *, json: dict[str, object]) -> "_DummyResponse":
        self._captured["request"] = {"url": url, "json": json}
        return _DummyResponse(url)


class _DummyResponse:
    def __init__(self, url: str) -> None:
        self.status_code = 200
        self._request = httpx.Request("POST", url)

    def raise_for_status(self) -> None:  # pragma: no cover - simple stub
        return None

    def json(self) -> dict[str, object]:
        return {"ok": True}


def test_environment_endpoint_reflects_env_overrides(monkeypatch, load_service_module):
    monkeypatch.setenv("PORT", "9090")
    monkeypatch.setenv("NATS_URL", "nats://demo:4222")
    monkeypatch.setenv("HIRAG_URL", "http://gateway.test:8086")
    monkeypatch.setenv("YT_URL", "http://yt.test:8077")
    monkeypatch.setenv("RENDER_WEBHOOK_URL", "http://render.test:8085")
    monkeypatch.setenv("OPEN_NOTEBOOK_API_URL", "https://notebook.example/api")
    monkeypatch.setenv("OPEN_NOTEBOOK_WORKSPACE", "workspace-alpha")
    monkeypatch.setenv("OPEN_NOTEBOOK_API_TOKEN", "token-value")
    monkeypatch.setenv("AGENT_FORM", "CUSTOM")
    monkeypatch.setenv("AGENT_FORMS_DIR", "configs/custom/forms")
    monkeypatch.setenv("AGENT_KNOWLEDGE_BASE_DIR", "runtime/custom-knowledge")
    monkeypatch.setenv("AGENT_MCP_RUNTIME_DIR", "runtime/custom-mcp")

    module = load_service_module("agent_zero_main", "services/agent-zero/main.py")
    module.service_config = module.load_service_config()
    module = _prepare_agent_zero(module, monkeypatch)

    with TestClient(module.app) as client:
        response = client.get("/config/environment")
    assert response.status_code == 200
    data = response.json()

    assert data["port"] == 9090
    assert data["nats_url"] == "nats://demo:4222"
    assert data["geometry_gateway_url"] == "http://gateway.test:8086"
    assert data["youtube_ingest_url"] == "http://yt.test:8077"
    assert data["render_webhook_url"] == "http://render.test:8085"
    assert data["open_notebook_api_url"] == "https://notebook.example/api"
    assert data["open_notebook_workspace"] == "workspace-alpha"
    assert data["open_notebook_token_present"] is True
    assert data["agent_form"] == "CUSTOM"
    assert data["agent_forms_dir"] == "configs/custom/forms"
    assert data["knowledge_base_dir"] == "runtime/custom-knowledge"
    assert data["mcp_runtime_dir"] == "runtime/custom-mcp"


def test_mcp_endpoints_expose_registry(monkeypatch, load_service_module):
    module = load_service_module("agent_zero_main", "services/agent-zero/main.py")
    module = _prepare_agent_zero(module, monkeypatch)

    fake_commands = {"demo.cmd": {"summary": "Demo command"}}
    monkeypatch.setattr(module.mcp_server, "COMMAND_REGISTRY", {"demo.cmd": "Demo command"})
    monkeypatch.setattr(module.mcp_server, "list_commands", lambda: fake_commands)

    executed: dict[str, tuple[str, dict]] = {}

    async def fake_execute(cmd, args):
        executed["call"] = (cmd, args)
        return {"ok": True, "args": args}

    monkeypatch.setattr(module.mcp_server, "execute_command_async", fake_execute)

    with TestClient(module.app) as client:
        commands_response = client.get("/mcp/commands")
        execute_response = client.post(
            "/mcp/execute",
            json={"cmd": "demo.cmd", "arguments": {"value": 42}},
        )

    assert commands_response.status_code == 200
    commands_payload = commands_response.json()
    assert commands_payload["default_form"] == module.service_config.agent_form
    assert commands_payload["runtime"]["knowledge_base_dir"] == module.service_config.knowledge_base_dir
    assert commands_payload["commands"] == fake_commands

    assert execute_response.status_code == 200
    execute_payload = execute_response.json()
    assert execute_payload["cmd"] == "demo.cmd"
    assert execute_payload["result"]["ok"] is True
    assert execute_payload["result"]["args"] == {"value": 42}
    assert executed["call"] == ("demo.cmd", {"value": 42})


def test_geometry_decode_text_uses_new_payload(monkeypatch, load_service_module):
    module = load_service_module("agent_zero_main", "services/agent-zero/main.py")
    module = _prepare_agent_zero(module, monkeypatch)

    captured: dict[str, dict[str, object]] = {}

    def fake_async_client(*args: Any, **kwargs: Any) -> _DummyAsyncClient:
        return _DummyAsyncClient(captured, *args, **kwargs)

    monkeypatch.setattr(module.mcp_server.httpx, "AsyncClient", fake_async_client)

    with TestClient(module.app) as client:
        response = client.post(
            "/mcp/execute",
            json={
                "cmd": "geometry.decode_text",
                "arguments": {
                    "mode": "geometry",
                    "constellation_id": "const-123",
                    "k": 3,
                    "shape_id": "shape-789",
                },
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["result"]["ok"] is True

    assert captured["request"]["url"] == f"{module.mcp_server.GATEWAY_URL}/geometry/decode/text"
    assert captured["client"]["timeout"] == 60.0

    request_body = captured["request"]["json"]
    assert request_body["mode"] == "geometry"
    assert request_body["constellation_id"] == "const-123"
    assert request_body["k"] == 3
    assert request_body["constellation_ids"] == ["const-123"]
    assert request_body["per_constellation"] == 3
    assert request_body["shape_id"] == "shape-789"


def test_send_message_without_a_pinned_token_fails_with_an_actionable_error(
    monkeypatch, load_service_module
):
    """A missing API key must name its own cause, not surface a bare 401.

    When AGENT_ZERO_MCP_TOKEN and MCP_SERVER_TOKEN are both unset the wrapper
    key is empty while the inner runtime auto-generates its own, so every
    session POST is rejected. `_headers` simply omits X-API-KEY, so without
    this guard the operator sees an unexplained 401 from a request that could
    never have succeeded. Codex P2 on #2780.
    """
    import asyncio

    import pytest as _pytest

    module = load_service_module("agent_zero_main", "services/agent-zero/main.py")

    config = module.AgentZeroRuntimeConfig()
    config.api_key = ""
    client = module.AgentZeroClient(config)

    with _pytest.raises(module.AgentZeroRequestError) as excinfo:
        asyncio.run(client.send_message({"text": "hello"}))

    assert excinfo.value.status_code == 503
    body = excinfo.value.message
    assert "AGENT_ZERO_MCP_TOKEN" in body
    assert "MCP_SERVER_TOKEN" in body


def test_send_message_passes_configured_message_timeout(
    monkeypatch, load_service_module
):
    """AGENT_ZERO_MESSAGE_TIMEOUT must reach the inner HTTP call.

    The inner-call timeout was hardcoded to 60s, so any agent task longer
    than a minute surfaced as a wrapper 503 even though the runtime was
    healthy (SPARK 2026-08-28: long research prompts, three failed dispatches).
    """
    import asyncio

    module = load_service_module("agent_zero_main", "services/agent-zero/main.py")
    monkeypatch.setenv("AGENT_ZERO_MESSAGE_TIMEOUT", "900")
    config = module.AgentZeroRuntimeConfig()
    config.api_key = "test-key"
    assert config.message_timeout == 900.0

    captured: Dict[str, Any] = {}

    async def fake_request(method, path, *, params=None, json_body=None, timeout=None):
        captured.update(method=method, path=path, timeout=timeout)
        return {"context_id": "c1", "status": "completed", "response": "ok"}

    client = module.AgentZeroClient(config)
    monkeypatch.setattr(client, "_request", fake_request)
    result = asyncio.run(client.send_message({"message": "hello"}))
    assert result["status"] == "completed"
    assert captured["timeout"] == 900.0
    assert captured["method"] == "POST"


def test_health_method_is_configurable(monkeypatch, load_service_module):
    """AGENT_ZERO_HEALTH_METHOD=POST must be used for the connector probe.

    The #2780 compose default points AGENT_ZERO_HEALTH_PATH at the
    POST-only _a0_connector capabilities route; a GET-only probe receives
    405 and silently degrades to the 404-means-alive heuristic.
    """
    import asyncio

    module = load_service_module("agent_zero_main", "services/agent-zero/main.py")
    monkeypatch.setenv("AGENT_ZERO_HEALTH_METHOD", "post")
    config = module.AgentZeroRuntimeConfig()
    assert config.health_method == "POST"

    captured: Dict[str, Any] = {}

    async def fake_request(method, path, *, params=None, json_body=None, timeout=None):
        captured.update(method=method, path=path)
        return {"protocol": "a0-connector.v1"}

    client = module.AgentZeroClient(config)
    monkeypatch.setattr(client, "_request", fake_request)
    result = asyncio.run(client.health())
    assert result["protocol"] == "a0-connector.v1"
    assert captured["method"] == "POST"
    assert captured["path"] == config.health_path


def test_healthz_reports_503_when_inner_runtime_is_down(
    monkeypatch, load_service_module
):
    """healthz must fail when the inner runtime is dead.

    Previously it returned HTTP 200 with body status=stopped, keeping
    Docker's healthcheck green while every message call failed.
    """
    module = load_service_module("agent_zero_main", "services/agent-zero/main.py")
    module.service_config = module.load_service_config()
    module = _prepare_agent_zero(module, monkeypatch)
    module.process_manager._process = None

    with TestClient(module.app) as client:
        response = client.get("/healthz")
    assert response.status_code == 503
    assert response.json()["status"] == "stopped"


def test_healthz_reports_200_when_inner_runtime_is_running(
    monkeypatch, load_service_module
):
    module = load_service_module("agent_zero_main", "services/agent-zero/main.py")
    module.service_config = module.load_service_config()
    module = _prepare_agent_zero(module, monkeypatch)
    module.process_manager._process = SimpleNamespace(returncode=None, pid=4242)

    async def fake_health():
        return {"status": "ok"}

    monkeypatch.setattr(module.client, "health", fake_health)
    with TestClient(module.app) as client:
        response = client.get("/healthz")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["pid"] == 4242
