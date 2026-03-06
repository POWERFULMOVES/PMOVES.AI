from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any, Dict

import pytest
import requests


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

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(f"status {self.status_code}", response=self)

    def json(self) -> Dict[str, Any]:
        return self._payload


def test_notebook_search_uses_modern_endpoint(monkeypatch: pytest.MonkeyPatch, mcp_module: ModuleType) -> None:
    monkeypatch.setattr(mcp_module, "NOTEBOOK_API_URL", "http://notebook:5055")
    monkeypatch.setattr(mcp_module, "NOTEBOOK_API_TOKEN", "token")
    monkeypatch.setattr(mcp_module, "NOTEBOOK_WORKSPACE", None)

    captured: Dict[str, Any] = {}

    def _post(url: str, json: Dict[str, Any], headers: Dict[str, str], timeout: int) -> _DummyResponse:
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        captured["timeout"] = timeout
        return _DummyResponse(
            200,
            payload={"results": [{"id": "n1", "title": "First note"}], "total_count": 1, "search_type": "text"},
        )

    monkeypatch.setattr(mcp_module.requests, "post", _post)
    result = mcp_module.notebook_search({"query": "pmoves", "limit": 3})

    assert captured["url"] == "http://notebook:5055/api/search"
    assert captured["json"] == {"query": "pmoves", "limit": 3}
    assert captured["timeout"] == 20
    assert result["ok"] is True
    assert result["total"] == 1
    assert result["endpoint"] == "/api/search"
    assert result["notes"][0]["id"] == "n1"


def test_notebook_search_falls_back_to_legacy_endpoint(monkeypatch: pytest.MonkeyPatch, mcp_module: ModuleType) -> None:
    monkeypatch.setattr(mcp_module, "NOTEBOOK_API_URL", "http://notebook:5055")
    monkeypatch.setattr(mcp_module, "NOTEBOOK_API_TOKEN", "token")
    monkeypatch.setattr(mcp_module, "NOTEBOOK_WORKSPACE", None)

    calls: list[tuple[str, Dict[str, Any]]] = []
    sequence = [
        _DummyResponse(404, payload={"detail": "not found"}),
        _DummyResponse(404, payload={"detail": "not found"}),
        _DummyResponse(200, payload={"results": [{"note": {"id": "legacy-1", "title": "Legacy note"}}], "total": 1}),
    ]

    def _post(url: str, json: Dict[str, Any], headers: Dict[str, str], timeout: int) -> _DummyResponse:
        calls.append((url, json))
        return sequence[len(calls) - 1]

    monkeypatch.setattr(mcp_module.requests, "post", _post)
    result = mcp_module.notebook_search({"query": "pmoves", "limit": 2, "notebook_id": "nb-1"})

    assert [url for url, _ in calls] == [
        "http://notebook:5055/api/search",
        "http://notebook:5055/search",
        "http://notebook:5055/api/v1/notebooks/search",
    ]
    assert calls[2][1]["filters"] == {"notebook_id": "nb-1"}
    assert result["endpoint"] == "/api/v1/notebooks/search"
    assert result["notes"][0]["id"] == "legacy-1"


def test_notebook_search_surfaces_auth_errors_as_value_error(
    monkeypatch: pytest.MonkeyPatch, mcp_module: ModuleType
) -> None:
    monkeypatch.setattr(mcp_module, "NOTEBOOK_API_URL", "http://notebook:5055")
    monkeypatch.setattr(mcp_module, "NOTEBOOK_API_TOKEN", "token")
    monkeypatch.setattr(mcp_module, "NOTEBOOK_WORKSPACE", None)
    monkeypatch.setattr(
        mcp_module.requests,
        "post",
        lambda *args, **kwargs: _DummyResponse(401, payload={"detail": "unauthorized"}, text="unauthorized"),
    )

    with pytest.raises(ValueError, match="authentication failed"):
        mcp_module.notebook_search({"query": "pmoves", "limit": 1})
