"""Unit tests for tailscale_mcp.tools — no live tailnet (the _run CLI seam is mocked)."""

from __future__ import annotations

import json

import pytest

from tailscale_mcp import tools


def _payload(result) -> dict:
    assert len(result) == 1
    return json.loads(result[0].text)


def _mock_run(rc=0, out="", err=""):
    """Build an async _run replacement returning canned (rc, out, err), capturing args."""
    calls = []

    async def fake(args, timeout=tools.DEFAULT_TIMEOUT):
        calls.append(list(args))
        return (rc, out, err)

    fake.calls = calls
    return fake


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    monkeypatch.delenv("TAILSCALE_SSH_ALLOWED_HOSTS", raising=False)


async def test_status_parses_nodes(monkeypatch):
    status = {
        "MagicDNSSuffix": "tailcad9b4.ts.net",
        "Self": {"ID": "self1", "HostName": "pmoves-4090", "Online": True, "ExitNodeOption": False},
        "ExitNodeStatus": {"ID": "n-kvm41"},
        "Peer": {"k1": {"ID": "n-kvm41", "HostName": "pmoves-kvm4-1", "Online": True, "ExitNodeOption": True}},
    }
    monkeypatch.setattr(tools, "_run", _mock_run(0, json.dumps(status)))
    out = _payload(await tools.handle_ts_status())
    assert out["self"] == "pmoves-4090"
    assert out["using_exit_node"] == "n-kvm41"
    hosts = {n["host"]: n for n in out["nodes"]}
    assert hosts["pmoves-kvm4-1"]["exit_node_option"] is True
    assert hosts["pmoves-4090"]["is_self"] is True


async def test_status_error(monkeypatch):
    monkeypatch.setattr(tools, "_run", _mock_run(1, "", "not connected"))
    out = _payload(await tools.handle_ts_status())
    assert "error" in out


async def test_exit_node_set_builds_command(monkeypatch):
    fake = _mock_run(0, "", "")
    monkeypatch.setattr(tools, "_run", fake)
    out = _payload(await tools.handle_ts_exit_node(action="set", node="pmoves-kvm4-1"))
    assert out["ok"] is True
    assert fake.calls[-1] == ["set", "--exit-node=pmoves-kvm4-1", "--exit-node-allow-lan-access"]


async def test_exit_node_set_rejects_bad_node(monkeypatch):
    monkeypatch.setattr(tools, "_run", _mock_run())
    out = _payload(await tools.handle_ts_exit_node(action="set", node="bad host;rm"))
    assert "error" in out


async def test_exit_node_clear(monkeypatch):
    fake = _mock_run(0, "", "")
    monkeypatch.setattr(tools, "_run", fake)
    await tools.handle_ts_exit_node(action="clear")
    assert fake.calls[-1] == ["set", "--exit-node="]


async def test_exit_node_unknown_action(monkeypatch):
    monkeypatch.setattr(tools, "_run", _mock_run())
    out = _payload(await tools.handle_ts_exit_node(action="frobnicate"))
    assert "error" in out


async def test_serve_set_uses_bg_and_port(monkeypatch):
    fake = _mock_run(0, "served", "")
    monkeypatch.setattr(tools, "_run", fake)
    await tools.handle_ts_serve(action="set", port=8096)
    assert fake.calls[-1] == ["serve", "--bg", "8096"]


async def test_serve_set_rejects_bad_port(monkeypatch):
    monkeypatch.setattr(tools, "_run", _mock_run())
    out = _payload(await tools.handle_ts_serve(action="set", port=0))
    assert "error" in out


async def test_funnel_rejects_nonstandard_https(monkeypatch):
    monkeypatch.setattr(tools, "_run", _mock_run())
    out = _payload(await tools.handle_ts_funnel(action="set", port=3000, https=8080))
    assert "error" in out


async def test_funnel_set_builds_command(monkeypatch):
    fake = _mock_run(0, "public url", "")
    monkeypatch.setattr(tools, "_run", fake)
    await tools.handle_ts_funnel(action="set", port=3000, https=443)
    assert fake.calls[-1] == ["funnel", "--bg", "--https=443", "localhost:3000"]


async def test_ssh_runs_command(monkeypatch):
    fake = _mock_run(0, "ip_forward=1", "")
    monkeypatch.setattr(tools, "_run", fake)
    out = _payload(await tools.handle_ts_ssh(host="pmoves-kvm2", command="cat /proc/sys/net/ipv4/ip_forward"))
    assert out["rc"] == 0 and out["host"] == "pmoves-kvm2"
    assert fake.calls[-1] == ["ssh", "pmoves-kvm2", "cat /proc/sys/net/ipv4/ip_forward"]


async def test_ssh_allowlist_enforced(monkeypatch):
    monkeypatch.setenv("TAILSCALE_SSH_ALLOWED_HOSTS", "pmoves-kvm2,pmoves-kvm4-1")
    monkeypatch.setattr(tools, "_run", _mock_run())
    out = _payload(await tools.handle_ts_ssh(host="pmoves-kvm4-2", command="hostname"))
    assert "error" in out and "allowed" in out


async def test_ssh_rejects_bad_host(monkeypatch):
    monkeypatch.setattr(tools, "_run", _mock_run())
    out = _payload(await tools.handle_ts_ssh(host="../evil", command="hostname"))
    assert "error" in out


async def test_metrics_returns_prometheus(monkeypatch):
    monkeypatch.setattr(tools, "_run", _mock_run(0, "tailscaled_inbound_bytes_total 42", ""))
    out = _payload(await tools.handle_ts_metrics())
    assert out["format"] == "prometheus" and "tailscaled_inbound_bytes_total" in out["metrics"]


async def test_netcheck_parses_json(monkeypatch):
    monkeypatch.setattr(tools, "_run", _mock_run(0, json.dumps({"UDP": True}), ""))
    out = _payload(await tools.handle_ts_netcheck())
    assert out["netcheck"]["UDP"] is True


async def test_ping_clamps_count(monkeypatch):
    fake = _mock_run(0, "pong via direct", "")
    monkeypatch.setattr(tools, "_run", fake)
    await tools.handle_ts_ping(host="pmoves-kvm2", count=99)
    assert fake.calls[-1] == ["ping", "--c=10", "pmoves-kvm2"]


def test_registry_parity():
    assert {t.name for t in tools.TOOLS} == set(tools.TOOL_HANDLERS)
