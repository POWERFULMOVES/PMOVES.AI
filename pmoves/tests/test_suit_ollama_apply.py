"""models_sync ollama-apply: suit ollama_config -> Ollama variant plan, drift, offload verdict."""
from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "models_sync", REPO_ROOT / "pmoves" / "tools" / "models" / "models_sync.py")
assert SPEC is not None and SPEC.loader is not None
ms = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ms)


def _suit(**over):
    doc = {"name": "s", "provider": "ollama_local",
           "model_config": {"model_name": "m:4b", "context_window": 8192,
                            "ollama_config": {"num_gpu": 999}}}
    doc.update(over)
    return doc


def test_plan_maps_context_window_to_num_ctx_and_defaults_the_variant():
    p = ms.suit_ollama_plan(_suit())
    assert p["base"] == "m:4b"
    assert p["variant"] == "m:4b-pmoves"
    assert p["parameters"] == {"num_gpu": 999, "num_ctx": 8192}


def test_explicit_num_ctx_and_variant_win():
    doc = _suit()
    doc["model_config"]["ollama_config"].update(num_ctx=2048, variant="m:custom")
    p = ms.suit_ollama_plan(doc)
    assert p["parameters"]["num_ctx"] == 2048 and p["variant"] == "m:custom"


def test_non_ollama_or_blockless_suits_yield_no_plan():
    assert ms.suit_ollama_plan(_suit(provider="anthropic")) is None
    assert ms.suit_ollama_plan({"provider": "ollama_local", "model_config": {"model_name": "x"}}) is None


def test_descriptive_keys_are_not_reported_unknown_keys_are():
    doc = _suit()
    doc["model_config"]["ollama_config"].update(quantization="Q4", ubatch=1024, mystery=1)
    assert ms.suit_ollama_plan(doc)["ignored"] == ["mystery"]


def test_drift_compares_as_strings_the_way_ollama_reports_them():
    p = ms.suit_ollama_plan(_suit())
    assert ms.suit_ollama_drift(p, {"num_gpu": "999", "num_ctx": "8192"}) == {}
    assert ms.suit_ollama_drift(p, {"num_gpu": "999"}) == {"num_ctx": (8192, None)}


def test_offload_verdicts():
    p = ms.suit_ollama_plan(_suit())
    assert ms.suit_offload_verdict(p, {}).startswith("UNDECIDED")
    full = {"m:4b-pmoves": {"size": 5_000_000_000, "size_vram": 5_000_000_000}}
    part = {"m:4b-pmoves": {"size": 5_400_000_000, "size_vram": 3_200_000_000}}
    assert ms.suit_offload_verdict(p, full).startswith("VERIFIED")
    assert ms.suit_offload_verdict(p, part).startswith("DRIFTED")


def test_the_embedding_suit_plans_its_named_variant():
    plans = ms.suit_ollama_plans("qwen3-embedding-4b")
    assert len(plans) == 1
    assert plans[0]["variant"] == "qwen3-embedding:4b-pmoves"
    assert plans[0]["parameters"] == {"num_gpu": 999, "num_ctx": 8192}
