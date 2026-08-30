from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any, Dict

import httpx
import pytest


@pytest.fixture(scope="module")
def mcp_module() -> ModuleType:
    base = Path(__file__).resolve().parents[3]
    module_path = base / "services/agent-zero/mcp_server.py"
    spec = importlib.util.spec_from_file_location("agent_zero_mcp_server", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _DummyResponse:
    def __init__(self, status_code: int, payload: Dict[str, Any] | None = None, text: str = "") -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text
        self._request: httpx.Request | None = None

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"status {self.status_code}",
                request=self._request or httpx.Request("POST", "http://notebook.invalid"),
                response=httpx.Response(self.status_code),
            )

    def json(self) -> Dict[str, Any]:
        return self._payload


def _install_async_client(
    monkeypatch: pytest.MonkeyPatch,
    mcp_module: ModuleType,
    responses: list[_DummyResponse],
    captured: Dict[str, Any],
) -> None:
    queue = list(responses)

    class _DummyAsyncClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            captured["timeout"] = kwargs.get("timeout")

        async def __aenter__(self) -> "_DummyAsyncClient":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def post(
            self,
            url: str,
            *,
            json: Dict[str, Any],
            headers: Dict[str, str],
        ) -> _DummyResponse:
            captured.setdefault("calls", []).append(
                {"url": url, "json": json, "headers": headers}
            )
            if not queue:
                raise AssertionError(f"Unexpected extra request to {url}")
            response = queue.pop(0)
            response._request = httpx.Request("POST", url)
            return response

    monkeypatch.setattr(mcp_module.httpx, "AsyncClient", _DummyAsyncClient)


def test_notebook_search_uses_modern_endpoint(monkeypatch: pytest.MonkeyPatch, mcp_module: ModuleType) -> None:
    monkeypatch.setattr(mcp_module, "NOTEBOOK_API_URL", "http://notebook:5055")
    monkeypatch.setattr(mcp_module, "NOTEBOOK_API_TOKEN", "token")
    monkeypatch.setattr(mcp_module, "NOTEBOOK_WORKSPACE", None)

    captured: Dict[str, Any] = {}
    _install_async_client(
        monkeypatch,
        mcp_module,
        [
            _DummyResponse(
                200,
                payload={
                    "results": [{"id": "n1", "title": "First note"}],
                    "total_count": 1,
                    "search_type": "text",
                },
            )
        ],
        captured,
    )
    result = asyncio.run(mcp_module.notebook_search({"query": "pmoves", "limit": 3}))

    assert captured["calls"][0]["url"] == "http://notebook:5055/api/search"
    assert captured["calls"][0]["json"] == {"query": "pmoves", "limit": 3}
    assert captured["timeout"] == 20.0
    assert result["ok"] is True
    assert result["total"] == 1
    assert result["endpoint"] == "/api/search"
    assert result["notes"][0]["id"] == "n1"


def test_notebook_search_with_filters_uses_modern_endpoint(monkeypatch: pytest.MonkeyPatch, mcp_module: ModuleType) -> None:
    monkeypatch.setattr(mcp_module, "NOTEBOOK_API_URL", "http://notebook:5055")
    monkeypatch.setattr(mcp_module, "NOTEBOOK_API_TOKEN", "token")
    monkeypatch.setattr(mcp_module, "NOTEBOOK_WORKSPACE", None)

    captured: Dict[str, Any] = {}
    _install_async_client(
        monkeypatch,
        mcp_module,
        [
            _DummyResponse(
                200,
                payload={
                    "results": [{"note": {"id": "modern-1", "title": "Modern note"}}],
                    "total": 1,
                },
            )
        ],
        captured,
    )
    result = asyncio.run(
        mcp_module.notebook_search({"query": "pmoves", "limit": 2, "notebook_id": "nb-1"})
    )

    assert [call["url"] for call in captured["calls"]] == [
        "http://notebook:5055/api/search",
    ]
    assert captured["calls"][0]["json"] == {
        "query": "pmoves",
        "limit": 2,
        "filters": {"notebook_id": "nb-1"},
    }
    assert result["endpoint"] == "/api/search"
    assert result["notes"][0]["id"] == "modern-1"


def test_notebook_search_with_filters_falls_back_to_legacy_endpoint(
    monkeypatch: pytest.MonkeyPatch, mcp_module: ModuleType
) -> None:
    monkeypatch.setattr(mcp_module, "NOTEBOOK_API_URL", "http://notebook:5055")
    monkeypatch.setattr(mcp_module, "NOTEBOOK_API_TOKEN", "token")
    monkeypatch.setattr(mcp_module, "NOTEBOOK_WORKSPACE", None)

    captured: Dict[str, Any] = {}
    _install_async_client(
        monkeypatch,
        mcp_module,
        [
            _DummyResponse(404, payload={"detail": "not found"}),
            _DummyResponse(404, payload={"detail": "not found"}),
            _DummyResponse(
                200,
                payload={
                    "results": [{"note": {"id": "legacy-1", "title": "Legacy note"}}],
                    "total": 1,
                },
            ),
        ],
        captured,
    )
    result = asyncio.run(
        mcp_module.notebook_search({"query": "pmoves", "limit": 2, "notebook_id": "nb-1"})
    )

    assert [call["url"] for call in captured["calls"]] == [
        "http://notebook:5055/api/search",
        "http://notebook:5055/search",
        "http://notebook:5055/api/v1/notebooks/search",
    ]
    assert captured["calls"][0]["json"]["filters"] == {"notebook_id": "nb-1"}
    assert captured["calls"][2]["json"]["filters"] == {"notebook_id": "nb-1"}
    assert result["endpoint"] == "/api/v1/notebooks/search"
    assert result["notes"][0]["id"] == "legacy-1"


def test_notebook_search_supports_data_key(monkeypatch: pytest.MonkeyPatch, mcp_module: ModuleType) -> None:
    monkeypatch.setattr(mcp_module, "NOTEBOOK_API_URL", "http://notebook:5055")
    monkeypatch.setattr(mcp_module, "NOTEBOOK_API_TOKEN", "token")
    monkeypatch.setattr(mcp_module, "NOTEBOOK_WORKSPACE", None)
    captured: Dict[str, Any] = {}
    _install_async_client(
        monkeypatch,
        mcp_module,
        [
            _DummyResponse(
                200,
                payload={"data": [{"id": "n-data-1", "title": "Data note"}], "total": 1},
            )
        ],
        captured,
    )

    result = asyncio.run(mcp_module.notebook_search({"query": "pmoves", "limit": 1}))
    assert result["notes"][0]["id"] == "n-data-1"
    assert result["total"] == 1


def test_notebook_search_surfaces_auth_errors_as_value_error(
    monkeypatch: pytest.MonkeyPatch, mcp_module: ModuleType
) -> None:
    monkeypatch.setattr(mcp_module, "NOTEBOOK_API_URL", "http://notebook:5055")
    monkeypatch.setattr(mcp_module, "NOTEBOOK_API_TOKEN", "token")
    monkeypatch.setattr(mcp_module, "NOTEBOOK_WORKSPACE", None)
    captured: Dict[str, Any] = {}
    _install_async_client(
        monkeypatch,
        mcp_module,
        [_DummyResponse(401, payload={"detail": "unauthorized"}, text="unauthorized")],
        captured,
    )

    with pytest.raises(ValueError, match="authentication failed"):
        asyncio.run(mcp_module.notebook_search({"query": "pmoves", "limit": 1}))
