"""MCP surface: tool listing, call path, /healthz, both HTTP transports, bearer gate.

Skipped (not failed) where the `mcp` SDK is absent -- e.g. the repo-wide ratchet
environment. The dedicated titanmail-mcp workflow installs the locked cassette and
runs these for real.
"""
from datetime import datetime, timezone

import pytest

pytest.importorskip("mcp")

from starlette.testclient import TestClient  # noqa: E402

from titanmail.mcp_app import TOOL_NAMES, build_asgi, build_mcp, payload_of  # noqa: E402
from titanmail.models import EmailMessage  # noqa: E402
from titanmail.service import TitanMailService  # noqa: E402
from titanmail.timewindow import FrozenClock, load_tz  # noqa: E402
from titanmail.transports import InMemoryTransport  # noqa: E402

NOW = datetime(2026, 11, 15, 12, 0, 0, tzinfo=timezone.utc)


def _mcp():
    msgs = [EmailMessage(id="m1", date=NOW.replace(hour=1), subject="hi", from_addr="a@x.test",
                         to=["me@x.test"], message_id="1@x.test")]
    svc = TitanMailService(InMemoryTransport(msgs), clock=FrozenClock(NOW), tz=load_tz("UTC"))
    return build_mcp(svc)


async def test_tool_listing_and_signatures():
    tools = {t.name: t for t in await _mcp().list_tools()}
    assert set(tools) == set(TOOL_NAMES)
    props = tools["search_messages"].inputSchema["properties"]
    assert {"query", "after_iso", "before_iso", "limit", "relative"} <= set(props)
    assert set(tools["get_message"].inputSchema.get("required", [])) == {"id"}
    assert set(tools["list_threads"].inputSchema["properties"]) == {"after_iso", "before_iso", "relative"}
    assert set(tools["dedup_report"].inputSchema["properties"]) == {"after_iso", "before_iso", "relative"}
    assert tools["now"].inputSchema.get("properties", {}) == {}


async def test_call_path_injects_server_time():
    mcp = _mcp()
    now = payload_of(await mcp.call_tool("now", {}))
    assert now["server_time_utc"] == "2026-11-15T12:00:00Z"
    res = payload_of(await mcp.call_tool("search_messages", {"relative": "today"}))
    assert res["ok"] and res["envelope"]["window"]["after_utc"] == "2026-11-15T00:00:00Z"
    assert [m["id"] for m in res["messages"]] == ["m1"]
    refused = payload_of(await mcp.call_tool("search_messages", {"query": "hi"}))
    assert refused["ok"] is False


def test_healthz_and_routes():
    app = build_asgi(_mcp())
    paths = {getattr(r, "path", None) for r in app.routes}
    assert {"/mcp", "/sse", "/messages", "/healthz"} <= paths | {"/messages"}
    assert "/sse" in paths and "/mcp" in paths
    with TestClient(app) as c:
        r = c.get("/healthz")
        assert r.status_code == 200 and r.json()["service"] == "titanmail-mcp"
        assert r.json()["server_time_utc"] == "2026-11-15T12:00:00Z"


def test_bearer_gate_protects_mcp_but_not_healthz():
    app = build_asgi(_mcp(), token="t0ken")
    # A loopback-bound FastMCP enables the SDK's DNS-rebinding protection, so the Host
    # header must be localhost/127.0.0.1 -- TestClient's default "testserver" gets 421.
    with TestClient(app, base_url="http://localhost:8092") as c:
        assert c.get("/healthz").status_code == 200
        assert c.post("/mcp", json={}).status_code == 401
        assert c.get("/sse").status_code == 401
        ok = c.post("/mcp", headers={"Authorization": "Bearer t0ken",
                                     "Accept": "application/json, text/event-stream"},
                    json={"jsonrpc": "2.0", "id": 1, "method": "initialize",
                          "params": {"protocolVersion": "2025-03-26", "capabilities": {},
                                     "clientInfo": {"name": "t", "version": "0"}}})
        assert ok.status_code == 200
