from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient


def _prepare_agent_zero(module, monkeypatch):
    monkeypatch.setattr(module.runtime_config, "entrypoint", str(Path(module.__file__)))

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
    module._controller_ready.clear()
    module._controller_shutdown.clear()
    return module


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

    module = load_service_module("agent_zero_main_env", "services/agent-zero/main.py")
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
    module = load_service_module("agent_zero_main_mcp", "services/agent-zero/main.py")
    module = _prepare_agent_zero(module, monkeypatch)

    fake_commands = {"demo.cmd": {"summary": "Demo command"}}
    monkeypatch.setattr(module.mcp_server, "COMMAND_REGISTRY", {"demo.cmd": "Demo command"})
    monkeypatch.setattr(module.mcp_server, "list_commands", lambda: fake_commands)

    executed: dict[str, tuple[str, dict]] = {}

    def fake_execute(cmd, args):
        executed["call"] = (cmd, args)
        return {"ok": True, "args": args}

    monkeypatch.setattr(module.mcp_server, "execute_command", fake_execute)

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
