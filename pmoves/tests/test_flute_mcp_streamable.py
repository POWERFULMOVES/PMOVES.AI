"""flute-gateway streamable-http /mcp mount — VOICE_FABRIC_PLAN step 1 tests.

The router exposes POST /mcp (stateless JSON-RPC dispatch, same handlers as the
SSE surface) alongside the legacy /sse + /messages. These tests drive the
dispatcher directly (no server) via dispatch(), and the router via FastAPI's
TestClient with provider/nats stubs.
"""
import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

SERVICE_DIR = Path(__file__).resolve().parents[1] / "services" / "flute-gateway"


@pytest.fixture(scope="module")
def bridge():
    sys.path.insert(0, str(SERVICE_DIR))
    try:
        mod = importlib.import_module("mcp_bridge")
    except ModuleNotFoundError as exc:  # fastapi et al missing in this env
        pytest.skip(f"flute-gateway deps unavailable: {exc}")
    return mod


class _StubProvider:
    """Enough of the UltimateTTS surface for tts_* tools to answer."""

    def get_status(self):  # used by engine-status style handlers
        return {"loaded": ["kokoro"], "available": ["kokoro", "kitten_tts"]}


def _make_session(bridge):
    return bridge.MCPSession("test-session", _StubProvider(), None)


@pytest.mark.asyncio
async def test_dispatch_initialize_advertises_tools(bridge):
    resp = await _make_session(bridge).dispatch(
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
    )
    assert resp["id"] == 1
    assert resp["result"]["serverInfo"]["name"] == "pmoves-flute-gateway"
    assert "tools" in resp["result"]["capabilities"]


@pytest.mark.asyncio
async def test_dispatch_tools_list_shape(bridge):
    resp = await _make_session(bridge).dispatch(
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
    )
    names = {t["name"] for t in resp["result"]["tools"]}
    assert {"tts_list_engines", "tts_list_intents", "tts_synthesize"} <= names


@pytest.mark.asyncio
async def test_dispatch_notification_returns_none(bridge):
    resp = await _make_session(bridge).dispatch(
        {"jsonrpc": "2.0", "method": "notifications/initialized"}
    )
    assert resp is None


@pytest.mark.asyncio
async def test_dispatch_unknown_method(bridge):
    resp = await _make_session(bridge).dispatch(
        {"jsonrpc": "2.0", "id": 3, "method": "no/such"}
    )
    assert resp["error"]["code"] == -32601


@pytest.mark.asyncio
async def test_dispatch_ping(bridge):
    resp = await _make_session(bridge).dispatch(
        {"jsonrpc": "2.0", "id": 4, "method": "ping"}
    )
    assert resp == {"jsonrpc": "2.0", "id": 4, "result": {}}


def test_streamable_mcp_route_roundtrip(bridge):
    """POST /mcp dispatches a single message and returns the response in-body."""
    fastapi = pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    app = fastapi.FastAPI()
    app.include_router(
        bridge.create_mcp_router(
            get_provider=lambda: _StubProvider(),
            get_nats_client=lambda: None,
        )
    )
    client = TestClient(app)

    r = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 10, "method": "tools/list"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == 10
    assert any(t["name"] == "tts_synthesize" for t in body["result"]["tools"])


def test_streamable_mcp_route_notification_202(bridge):
    fastapi = pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    app = fastapi.FastAPI()
    app.include_router(
        bridge.create_mcp_router(
            get_provider=lambda: _StubProvider(),
            get_nats_client=lambda: None,
        )
    )
    client = TestClient(app)

    r = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "method": "notifications/initialized"},
    )
    assert r.status_code == 202
    assert r.json() == {}
