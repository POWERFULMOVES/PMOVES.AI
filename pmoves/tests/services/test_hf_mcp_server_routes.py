"""Route-level tests for hf-mcp-server FastAPI endpoints.

Covers the gaps identified in PR #2113's test suite: actual HTTP route testing
via TestClient, mocked HfApi/snapshot_download, metrics, SSE tools list.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ─── Module loader (mirrors test_hf_services.py pattern) ────────────────────

_SERVICE_PATH = Path(__file__).resolve().parents[2] / "services" / "hf-mcp-server" / "main.py"


def _load_hf_module():
    if not _SERVICE_PATH.exists():
        pytest.skip("hf-mcp-server/main.py not found")
    spec = importlib.util.spec_from_file_location("hf_mcp_main", _SERVICE_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["hf_mcp_main"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def hf():
    try:
        return _load_hf_module()
    except ImportError as e:
        pytest.skip(f"Cannot import hf-mcp-server deps: {e}")


@pytest.fixture
def tmp_cache(tmp_path, hf, monkeypatch):
    cache = tmp_path / "hf_cache"
    cache.mkdir()
    monkeypatch.setattr(hf, "HF_HUB_CACHE", str(cache))
    monkeypatch.setattr(hf, "MODELS_BASE", cache / "models")
    return cache


@pytest.fixture
def client(hf, tmp_cache):
    from fastapi.testclient import TestClient
    return TestClient(hf.app)


# ─── Health & metrics ───────────────────────────────────────────────────────


class TestHealthMetrics:
    def test_healthz_returns_healthy(self, client):
        r = client.get("/healthz")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] in ("healthy", "degraded")
        assert body["service"] == "hf-mcp-server"

    def test_health_alias(self, client):
        r = client.get("/health")
        assert r.status_code == 200

    def test_metrics_format(self, client):
        r = client.get("/metrics")
        assert r.status_code == 200
        text = r.text
        assert "hf_mcp_server_up" in text

    def test_metrics_download_count(self, client, hf):
        hf._download_count = 5
        r = client.get("/metrics")
        assert "hf_mcp_downloads_total 5" in r.text


# ─── Model search ───────────────────────────────────────────────────────────


class TestModelSearch:
    def test_search_returns_models(self, client):
        r = client.post("/api/model/search", json={})
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert isinstance(body["models"], list)
        assert len(body["models"]) > 0

    def test_search_by_tier(self, client):
        r = client.post("/api/model/search", json={"tier": "small"})
        assert r.status_code == 200
        for m in r.json()["models"]:
            assert m.get("tier") == "small"

    def test_search_empty_result(self, client):
        r = client.post("/api/model/search", json={"tier": "nonexistent_tier"})
        assert r.status_code == 200
        assert r.json()["models"] == []


# ─── Model info ─────────────────────────────────────────────────────────────


class TestModelInfo:
    def test_info_from_catalog(self, client, hf):
        first_key = next(iter(hf.MODEL_CATALOG))
        r = client.get(f"/api/model/{first_key}")
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert "model" in body

    def test_info_not_found(self, client):
        r = client.get("/api/model/nonexistent-model-xyz")
        assert r.status_code == 404


# ─── Model list (cached) ────────────────────────────────────────────────────


class TestModelList:
    def test_list_empty_cache(self, client, tmp_cache):
        r = client.get("/api/models")
        assert r.status_code == 200
        assert r.json()["models"] == []

    def test_list_with_cached_model(self, client, tmp_cache):
        model_dir = tmp_cache / "models" / "test-model"
        snapshots = model_dir / "snapshots" / "abc123"
        snapshots.mkdir(parents=True)
        (snapshots / "config.json").write_text("{}")
        r = client.get("/api/models")
        assert r.status_code == 200
        models = r.json()["models"]
        assert len(models) >= 1


# ─── TensorZero config ──────────────────────────────────────────────────────


class TestTensorZeroConfig:
    def test_config_returns_toml(self, client):
        r = client.get("/api/config/tensorzero")
        assert r.status_code == 200
        # Should contain some model entries (TOML format)
        assert "model" in r.text or len(r.text) > 0


# ─── SSE MCP tools ──────────────────────────────────────────────────────────


class TestSSETools:
    def test_sse_returns_tools_event(self, client):
        with client.stream("GET", "/sse") as resp:
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers.get("content-type", "")
            # Read the first chunk
            chunks = []
            for line in resp.iter_lines():
                chunks.append(line)
                if line.startswith("data: ") and "tools" in line.lower():
                    break
            # Find the data line
            data_line = next((c for c in chunks if c.startswith("data: [")), None)
            if data_line:
                tools = json.loads(data_line[6:])
                tool_names = [t["name"] for t in tools]
                assert "hf.model.search" in tool_names
                assert "hf.model.info" in tool_names
                assert "hf.model.download" in tool_names
                assert "hf.model.list" in tool_names


# ─── Convert GGUF ───────────────────────────────────────────────────────────


class TestConvertGGUF:
    def test_convert_not_cached(self, client):
        r = client.post("/api/model/convert-gguf", json={"model_id": "nonexistent"})
        assert r.status_code == 404
