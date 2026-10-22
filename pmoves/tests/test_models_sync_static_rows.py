"""models_sync static agent-zero manifests: every llm id shape yields a chat-lane row.

_filter_rows keeps only rows with service_name/model_type; a row missing them
silently degraded the presets to the fallback template (#3373 review).
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "models_sync", REPO_ROOT / "pmoves" / "tools" / "models" / "models_sync.py")
assert SPEC is not None and SPEC.loader is not None
ms = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ms)


@pytest.mark.parametrize("target,model,provider", [
    ({"llm": "ollama/qwen2.5:14b"}, "qwen2.5:14b", "ollama"),
    ({"llm": "qwen2.5:14b", "provider": "ollama"}, "qwen2.5:14b", "ollama"),
    ({"llm": "glm-5"}, "glm-5", "tensorzero"),
])
def test_static_manifest_rows_survive_the_chat_lane_filter(monkeypatch, tmp_path, target, model, provider):
    seen = {}
    monkeypatch.setattr(ms, "_write_a0_presets", lambda rows, *a, **k: seen.setdefault("rows", rows))
    ms._sync_agent_zero({"targets": {"n": target}}, "n", "http://tz:3000", out_override=str(tmp_path / "p.yaml"))
    lane = ms._filter_rows(seen["rows"], ("agent_zero",), ("chat",), ("chat",))
    assert [(r["model_id"], r["provider_name"]) for r in lane] == [(model, provider)]
