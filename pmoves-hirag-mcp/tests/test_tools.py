"""Unit tests for hirag_mcp.tools — no live services required (httpx mocked)."""

from __future__ import annotations

import json

import httpx
import pytest

from hirag_mcp import tools


def _payload(result) -> dict:
    """Decode the single TextContent JSON payload returned by a handler."""
    assert len(result) == 1
    return json.loads(result[0].text)


class _MockClient:
    """Minimal httpx.AsyncClient stand-in returning a canned response."""

    def __init__(self, *args, **kwargs):
        self.captured = {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, json=None, **kw):
        self.captured.update({"url": url, "json": json})
        _MockClient.last = self.captured
        return httpx.Response(200, json={"results": [{"text": "hit", "score": 0.9}]},
                              request=httpx.Request("POST", url))

    async def get(self, url, params=None, headers=None, **kw):
        self.captured.update({"url": url, "params": params, "headers": headers})
        _MockClient.last = self.captured
        return httpx.Response(200, json={"ok": True},
                              request=httpx.Request("GET", url))


@pytest.fixture(autouse=True)
def _mock_httpx(monkeypatch):
    """Replace httpx.AsyncClient with the canned mock for every test."""
    monkeypatch.setattr(tools.httpx, "AsyncClient", _MockClient)


async def test_hirag_query_posts_to_cpu_gateway(monkeypatch):
    monkeypatch.delenv("HIRAG_URL", raising=False)
    out = _payload(await tools.handle_hirag_query("what is CHIT", top_k=5))
    assert out["results"][0]["text"] == "hit"
    assert _MockClient.last["url"] == "http://localhost:8086/hirag/query"
    assert _MockClient.last["json"] == {"query": "what is CHIT", "top_k": 5, "rerank": True}


async def test_hirag_query_gpu_flag(monkeypatch):
    monkeypatch.delenv("HIRAG_GPU_URL", raising=False)
    await tools.handle_hirag_query("q", gpu=True)
    assert _MockClient.last["url"].startswith("http://localhost:8087")


async def test_hirag_query_requires_query():
    out = _payload(await tools.handle_hirag_query(""))
    assert "error" in out


async def test_hirag_query_clamps_top_k():
    await tools.handle_hirag_query("q", top_k=500)
    assert _MockClient.last["json"]["top_k"] == 50


async def test_notebook_search_requires_env(monkeypatch):
    monkeypatch.delenv("OPEN_NOTEBOOK_API_URL", raising=False)
    out = _payload(await tools.handle_notebook_search("rag"))
    assert "OPEN_NOTEBOOK_API_URL" in out["error"]


async def test_notebook_search_sends_bearer(monkeypatch):
    monkeypatch.setenv("OPEN_NOTEBOOK_API_URL", "http://nb:5055/")
    monkeypatch.setenv("OPEN_NOTEBOOK_API_TOKEN", "tok123")
    out = _payload(await tools.handle_notebook_search("rag", limit=3))
    assert out == {"ok": True}
    assert _MockClient.last["url"] == "http://nb:5055/api/search"
    assert _MockClient.last["headers"]["Authorization"] == "Bearer tok123"
    assert _MockClient.last["params"] == {"q": "rag", "limit": 3}


async def test_service_health_unknown_name():
    out = _payload(await tools.handle_service_health("nope"))
    assert "unknown service" in out["error"]
    assert "agent-zero" in out["known"]


async def test_service_health_single():
    out = _payload(await tools.handle_service_health("cipher"))
    assert out["cipher"]["ok"] is True


async def test_service_health_sweep_all():
    out = _payload(await tools.handle_service_health(""))
    assert set(out) == set(tools.HEALTH_CATALOG)


def test_registry_parity():
    """Every declared Tool has a handler and vice versa."""
    assert {t.name for t in tools.TOOLS} == set(tools.TOOL_HANDLERS)
