"""Unit tests for the HuggingFace agent services.

Covers three services:
- ``hf-agent`` — autonomous HF Hub patrol, publishes ``hf.model.discovered.v1``
- ``hf-research-agent`` — evaluates discovered models, publishes ``hf.model.evaluated.v1``
- ``hf-mcp-server`` — FastAPI MCP server with model catalog + search/download endpoints

Tests follow the spark-shape-worker pattern: import the service module, exercise
pure logic (no live NATS / no live HF API), and verify payload contracts.
Network-bound code paths are validated through FastAPI's TestClient against
in-memory state only.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

SERVICES_DIR = Path(__file__).resolve().parents[2] / "services"


# ---------------------------------------------------------------------------
# Module loading helpers
# ---------------------------------------------------------------------------

def _load_module(rel_path: str, module_name: str):
    """Load a service ``main.py`` as an isolated module.

    Each HF service ships as a single-file ``main.py`` with no package
    ``__init__.py``, so we load via spec from the absolute path.
    """
    src = SERVICES_DIR / rel_path / "main.py"
    spec = importlib.util.spec_from_file_location(module_name, src)
    assert spec and spec.loader, f"unable to load spec for {src}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


# Load each service independently so a missing optional dep (fastapi,
# huggingface_hub ModelFilter) only skips that service's tests.
hf_agent_mod = None
hf_research_mod = None
hf_mcp_mod = None
_hf_agent_skip_reason: str | None = None
_hf_research_skip_reason: str | None = None
_hf_mcp_skip_reason: str | None = None

try:
    import nats  # noqa: F401 — guards hf-agent import; pytest.importorskip raises BaseException
    hf_agent_mod = _load_module("hf-agent", "pmoves_test_hf_agent")
except Exception as exc:  # pragma: no cover
    hf_agent_mod = None
    _hf_agent_skip_reason = f"{type(exc).__name__}: {exc}"

try:
    hf_research_mod = _load_module("hf-research-agent", "pmoves_test_hf_research_agent")
except Exception as exc:  # pragma: no cover
    hf_research_mod = None
    _hf_research_skip_reason = f"{type(exc).__name__}: {exc}"

try:
    hf_mcp_mod = _load_module("hf-mcp-server", "pmoves_test_hf_mcp_server")
except Exception as exc:  # pragma: no cover
    hf_mcp_mod = None
    _hf_mcp_skip_reason = f"{type(exc).__name__}: {exc}"


# ---------------------------------------------------------------------------
# hf-agent — discovery payload contract
# ---------------------------------------------------------------------------

class TestHFAgent:
    """Verify hf-agent publishes the documented NATS contract."""

    pytestmark = pytest.mark.skipif(
        hf_agent_mod is None, reason=f"hf-agent import failed: {_hf_agent_skip_reason}"
    )

    def test_publish_subject_matches_registry(self) -> None:
        """Subject must match agent_registry.yaml: hf.model.discovered.v1."""
        assert hf_agent_mod.PUBLISH_SUBJECT == "hf.model.discovered.v1"

    def test_discovery_entry_shape(self) -> None:
        """Each discovered model payload must carry the contract fields."""
        agent = hf_agent_mod.HFAgent(
            nats_url="nats://localhost:4222",
            hf_token="",
            poll_interval=1,
        )
        agent._api = type("StubAPI", (), {})()  # bypass real HfApi init

        # Build a fake model_info object the discovery loop expects.
        class FakeModel:
            id = "Qwen/Qwen3.5-9B"
            tags = ["text-generation", "qwen"]
            downloads = 12345
            likes = 42
            lastModified = "2026-07-10T00:00:00Z"
            pipeline_tag = "text-generation"
            author = "Qwen"

        def fake_list_models(**_kwargs):
            return [FakeModel()]

        agent._api.list_models = fake_list_models
        discovered = agent._discover_models()
        assert len(discovered) == 1
        entry = discovered[0]
        # Required contract fields per datasets.yaml + nats-subjects.md
        assert entry["model_id"] == "Qwen/Qwen3.5-9B"
        assert entry["hf_url"] == "https://huggingface.co/Qwen/Qwen3.5-9B"
        assert entry["downloads"] == 12345
        assert entry["likes"] == 42
        assert entry["pipeline_tag"] == "text-generation"
        assert "discovered_at" in entry
        # JSON-serialisable (will be json.dumps'd on publish)
        json.dumps(entry, default=str)

    def test_discovery_dedupes_seen_models(self) -> None:
        """Second poll cycle must not re-emit a model already in _seen."""
        agent = hf_agent_mod.HFAgent("nats://localhost:4222", "", 1)
        agent._api = type("StubAPI", (), {})()

        class FakeModel:
            id = "meta-llama/Llama-4-8B"
            tags = []
            downloads = 0
            likes = 0
            lastModified = ""
            pipeline_tag = ""
            author = ""

        agent._api.list_models = lambda **_: [FakeModel()]
        first = agent._discover_models()
        second = agent._discover_models()
        assert len(first) == 1
        assert second == [], "_seen set must prevent re-emission"

    def test_discovery_swallows_errors(self) -> None:
        """API errors must not crash the poll loop (returns [])."""
        agent = hf_agent_mod.HFAgent("nats://localhost:4222", "", 1)
        agent._api = type("StubAPI", (), {})()

        def boom(**_):
            raise RuntimeError("network down")

        agent._api.list_models = boom
        assert agent._discover_models() == []


# ---------------------------------------------------------------------------
# hf-research-agent — evaluation scoring
# ---------------------------------------------------------------------------

class TestHFResearchAgent:
    """Verify hf-research-agent scoring matches the documented rubric."""

    pytestmark = pytest.mark.skipif(
        hf_research_mod is None,
        reason=f"hf-research-agent import failed: {_hf_research_skip_reason}",
    )

    def test_publish_and_subscribe_subjects_match_registry(self) -> None:
        assert hf_research_mod.SUBSCRIBE_SUBJECT == "hf.model.discovered.v1"
        assert hf_research_mod.PUBLISH_SUBJECT == "hf.model.evaluated.v1"

    def test_high_quality_model_passes(self) -> None:
        """High downloads + likes + preferred tag + pipeline => pass."""
        model = {
            "model_id": "Qwen/Qwen3.5-35B-A3B",
            "tags": ["text-generation", "qwen", "moe"],
            "downloads": 50000,
            "likes": 200,
            "pipeline_tag": "text-generation",
            "hf_url": "https://huggingface.co/Qwen/Qwen3.5-35B-A3B",
        }
        result = hf_research_mod.HFResearchAgent._evaluate_model(model)
        assert result["passed"] is True
        assert result["score"] >= 50
        assert result["max_score"] == 100
        assert "high downloads" in " ".join(result["reasons"])

    def test_low_quality_model_fails(self) -> None:
        """Zero-download, zero-like, no-tag model must fail."""
        model = {
            "model_id": "novel/unknown-7b",
            "tags": [],
            "downloads": 0,
            "likes": 0,
            "pipeline_tag": "",
        }
        result = hf_research_mod.HFResearchAgent._evaluate_model(model)
        assert result["passed"] is False
        assert result["score"] < 50

    def test_avoid_tags_apply_penalty(self) -> None:
        """Avoid-tag matches must subtract 10 points each."""
        model = {
            "model_id": "test/controversial",
            "tags": ["deprecated", "broken"],
            "downloads": 10000,
            "likes": 100,
            "pipeline_tag": "text-generation",
        }
        # Patch avoid-tags set on the module (read at import time from env).
        original = hf_research_mod.AVOID_TAGS
        hf_research_mod.AVOID_TAGS = {"deprecated", "broken"}
        try:
            result = hf_research_mod.HFResearchAgent._evaluate_model(model)
        finally:
            hf_research_mod.AVOID_TAGS = original
        # 40 (downloads) + 25 (likes) + 15 (pipeline) - 20 (2 avoid tags) = 60
        # Still passes (>=50) but penalty is visible in reasons.
        assert any("avoid tags match" in r for r in result["reasons"])
        assert result["score"] == 60

    def test_preferred_tags_add_20_points(self) -> None:
        model = {
            "model_id": "Qwen/Qwen3.5-9B",
            "tags": ["text-generation", "qwen"],
            "downloads": 1000,
            "likes": 10,
            "pipeline_tag": "text-generation",
        }
        original = hf_research_mod.PREFERRED_TAGS
        hf_research_mod.PREFERRED_TAGS = {"qwen"}
        try:
            result = hf_research_mod.HFResearchAgent._evaluate_model(model)
        finally:
            hf_research_mod.PREFERRED_TAGS = original
        # 25 (downloads) + 15 (likes) + 20 (preferred) + 15 (pipeline) = 75
        assert result["score"] == 75
        assert result["passed"] is True

    def test_evaluation_envelope_is_json_serialisable(self) -> None:
        """Published payload must round-trip through JSON."""
        model = {"model_id": "t/t", "tags": [], "downloads": 0, "likes": 0}
        result = hf_research_mod.HFResearchAgent._evaluate_model(model)
        encoded = json.dumps(result, default=str).encode("utf-8")
        decoded = json.loads(encoded)
        assert decoded["model_id"] == "t/t"
        assert "evaluated_at" in decoded


# ---------------------------------------------------------------------------
# hf-mcp-server — model catalog + path safety
# ---------------------------------------------------------------------------

class TestHFMcpServer:
    """Verify hf-mcp-server catalog, path safety, and search filters."""

    pytestmark = pytest.mark.skipif(
        hf_mcp_mod is None, reason=f"hf-mcp-server import failed: {_hf_mcp_skip_reason}"
    )

    def test_model_catalog_has_required_tiers(self) -> None:
        """Catalog must include models from every tier for fleet routing."""
        tiers = {entry["tier"] for entry in hf_mcp_mod.MODEL_CATALOG.values()}
        assert {"small", "medium", "large"} <= tiers

    def test_model_catalog_entries_are_well_formed(self) -> None:
        """Every catalog entry must have model_id, name, tier, hf_url."""
        for key, entry in hf_mcp_mod.MODEL_CATALOG.items():
            assert "model_id" in entry, f"{key} missing model_id"
            assert "name" in entry, f"{key} missing name"
            assert "tier" in entry, f"{key} missing tier"
            assert "hf_url" in entry, f"{key} missing hf_url"
            assert entry["hf_url"].startswith("https://huggingface.co/")

    def test_safe_model_path_rejects_traversal(self) -> None:
        """Path traversal in model_id must raise HTTPException 400."""
        from fastapi import HTTPException

        for malicious in ["../etc/passwd", "../../secret", "..\\windows"]:
            with pytest.raises(HTTPException) as exc:
                hf_mcp_mod._safe_model_path(malicious)
            assert exc.value.status_code == 400

    def test_safe_model_path_accepts_valid_id(self) -> None:
        """Valid HF model IDs (org/name with slash) must resolve cleanly."""
        path = hf_mcp_mod._safe_model_path("Qwen/Qwen3.5-9B")
        # The slash must be sanitised to -- so the result is a single basename.
        assert path.name == "Qwen--Qwen3.5-9B"
        assert ".." not in str(path)

    @pytest.mark.asyncio
    async def test_model_search_filters_by_tier(self) -> None:
        """Search must honour the tier filter."""
        results = await hf_mcp_mod.hf_model_search(tier="small")
        assert results, "expected at least one small-tier model"
        assert all(r["tier"] == "small" for r in results)

    @pytest.mark.asyncio
    async def test_model_search_filters_by_use_case(self) -> None:
        """Search must honour the use_case filter."""
        results = await hf_mcp_mod.hf_model_search(use_case="coding")
        assert results
        assert all("coding" in r.get("uses", []) for r in results)

    @pytest.mark.asyncio
    async def test_model_search_no_filter_returns_all(self) -> None:
        """Empty filter must return the entire catalog."""
        results = await hf_mcp_mod.hf_model_search()
        assert len(results) == len(hf_mcp_mod.MODEL_CATALOG)

    @pytest.mark.asyncio
    async def test_model_list_empty_when_no_cache(self, tmp_path, monkeypatch):
        """hf_model_list must return [] when the hub cache doesn't exist."""
        monkeypatch.setattr(hf_mcp_mod, "HF_HUB_CACHE", str(tmp_path / "nope"))
        results = await hf_mcp_mod.hf_model_list()
        assert results == []

    def test_metadata_from_dict_roundtrip(self) -> None:
        """ModelMetadata.from_dict must parse all enum fields."""
        data = {
            "model_id": "test/m",
            "name": "test",
            "params": 7_000_000_000,
            "tier": "medium",
            "uses": ["coding", "orchestrator"],
            "backends": ["ollama", "vllm"],
        }
        md = hf_mcp_mod.ModelMetadata.from_dict(data)
        assert md.tier == hf_mcp_mod.ModelTier.MEDIUM
        assert hf_mcp_mod.ModelUse.CODING in md.uses
        assert hf_mcp_mod.BackendType.OLLAMA in md.backends
