"""Positive control for tools/agent_zero_smoke.py.

The smoke targets (`health-agent-zero`, `a0-mcp-smoke`, `a0-mcp-exec-smoke`)
only run where Agent Zero is up, so nothing in CI ever exercised them and four
wrong-port/wrong-route/wrong-schema defects shipped undetected (PR #2905 review).

These tests run the probe logic against in-process stubs, so they need no
running service. They assert both halves of a usable check:

  1. the probes go GREEN against the documented supervisor contract, and
  2. the probes go RED against each historical defect.

(2) is the important half. A smoke that cannot fail reports green whether the
service is healthy or absent.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import socket
import sys

import pytest

TOOL = pathlib.Path(__file__).resolve().parents[2] / "tools" / "agent_zero_smoke.py"


def _load():
    spec = importlib.util.spec_from_file_location("agent_zero_smoke", TOOL)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


smoke = _load()


def _free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


@pytest.mark.parametrize("probe", sorted(smoke.PROBES))
def test_probe_passes_against_documented_contract(probe):
    """Green half: each probe accepts a supervisor that honours the contract."""
    ok, detail = smoke._run_against(smoke.GOOD_ROUTES, probe)
    assert ok, f"{probe} failed against a compliant supervisor stub: {detail}"


DEFECTS = {
    # Codex P1 #1 — probing 8081 lands on the A0 UI, which serves HTML not JSON.
    "wrong_port_ui_html": (
        "health",
        {**smoke.GOOD_ROUTES, ("GET", "/healthz"): (200, b"<!doctype html><title>Agent Zero</title>")},
    ),
    # Codex P1 #2 — /healthz has no form; asserting one there fails a healthy service.
    "healthz_without_supervisor_keys": (
        "health",
        {**smoke.GOOD_ROUTES, ("GET", "/healthz"): (200, {"nats": {}})},
    ),
    "healthz_reports_stopped": (
        "health",
        {**smoke.GOOD_ROUTES, ("GET", "/healthz"): (200, {"status": "stopped", "nats": {}})},
    ),
    # Codex P1 #3 — the listing route is /mcp/commands; a bare /mcp 404s.
    "mcp_commands_route_missing": (
        "mcp-list",
        {k: v for k, v in smoke.GOOD_ROUTES.items() if k != ("GET", "/mcp/commands")},
    ),
    # The cannot-fail regression: commands present, default_form absent.
    "default_form_missing": (
        "mcp-list",
        {
            **smoke.GOOD_ROUTES,
            ("GET", "/mcp/commands"): (
                200,
                {"default_form": None, "commands": [{"name": "form.get", "description": "d"}]},
            ),
        },
    ),
    "commands_not_name_description": (
        "mcp-list",
        {
            **smoke.GOOD_ROUTES,
            ("GET", "/mcp/commands"): (200, {"default_form": "f", "commands": ["form.get"]}),
        },
    ),
    # Codex P1 #4 — MCPExecuteRequest requires `cmd`; the legacy `command` body 422s.
    "execute_schema_rejected_422": (
        "mcp-exec",
        {**smoke.GOOD_ROUTES, ("POST", "/mcp/execute"): (422, {"detail": "field required: cmd"})},
    ),
    "form_get_returns_empty_form": (
        "mcp-exec",
        {
            **smoke.GOOD_ROUTES,
            ("POST", "/mcp/execute"): (200, {"cmd": "form.get", "result": {"form": {}}}),
        },
    ),
}


@pytest.mark.parametrize("name", sorted(DEFECTS))
def test_probe_fails_against_each_known_defect(name):
    """Red half: every historical defect must turn the check red."""
    probe, routes = DEFECTS[name]
    ok, detail = smoke._run_against(routes, probe)
    assert not ok, f"{probe} stayed GREEN against defect {name!r} — this check cannot fail"
    assert "red(" in detail


def test_unreachable_service_is_not_a_pass():
    """A missing service must be red, never a silent green."""
    ok, detail = smoke._run_against({}, "health", serve=False)
    assert not ok, "health passed with nothing listening — could-not-measure was reported as a pass"
    assert f"exit={smoke.EXIT_UNREACHABLE}" in detail, detail


def test_default_base_targets_the_supervisor_port(monkeypatch):
    """docker-compose publishes the supervisor on ${AGENT_ZERO_PORT:-8080}."""
    monkeypatch.delenv("AGENT_ZERO_SUPERVISOR_URL", raising=False)
    monkeypatch.delenv("AGENT_ZERO_PORT", raising=False)
    assert smoke._default_base() == "http://localhost:8080"

    monkeypatch.setenv("AGENT_ZERO_PORT", "18080")
    assert smoke._default_base() == "http://localhost:18080"

    monkeypatch.setenv("AGENT_ZERO_SUPERVISOR_URL", "http://az.example:9/")
    assert smoke._default_base() == "http://az.example:9"


def test_execute_payload_uses_the_request_schema():
    """The POST body must be MCPExecuteRequest: {cmd, arguments} — not {command}."""
    captured = {}

    def fake_request(path, payload=None):
        captured["path"] = path
        captured["payload"] = payload
        return {"cmd": "form.get", "result": {"form": {"name": "pmoves.default"}}}

    original = smoke._request
    smoke._request = fake_request
    try:
        smoke.mcp_exec()
    finally:
        smoke._request = original

    assert captured["path"] == "/mcp/execute"
    assert captured["payload"] == {"cmd": "form.get", "arguments": {}}
    assert "command" not in captured["payload"], "legacy `command` key must not be sent"


def test_selftest_mode_exits_zero(capsys):
    """`agent_zero_smoke.py selftest` is the operator-facing positive control."""
    smoke.selftest()
    out = capsys.readouterr().out
    assert "defects all caught red" in out


def test_no_superseded_routes_referenced():
    """Guard against regressing onto the never-implemented .claude/context routes."""
    source = TOOL.read_text(encoding="utf-8")
    body = source.split('"""', 2)[-1]  # skip the module docstring, which names them to warn
    for dead in ("/mcp/command\"", "/mcp/health", "/mcp/agents", "/mcp/subordinate", "MCP_CLIENT_SECRET"):
        assert dead not in body, f"{dead} was never implemented by services/agent-zero"
    assert "AGENT_ZERO_API_URL" not in body, "the 8081 UI-port env var must not come back"
    assert json.dumps  # keep the import meaningful for linters
    assert sys.version_info >= (3, 9)
