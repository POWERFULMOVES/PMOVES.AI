"""Unit tests for tools/node_capability_tier.py (capability-adaptive standalone).

Covers: node-type mapping per glances-autodetect class, raw-threshold fallback
and its boundaries, PMOVES_NODE_TIER override, and per-tier service sets.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_MOD_PATH = Path(__file__).resolve().parents[1] / "tools" / "node_capability_tier.py"
_spec = importlib.util.spec_from_file_location("node_capability_tier", _MOD_PATH)
nct = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(nct)


# ── node-type mapping (one per known glances-autodetect class) ──────────────
@pytest.mark.parametrize(
    "node_type,expected",
    [
        ("kvm4-1", "lean"),
        ("kvm4-2", "lean"),
        ("kvm2", "lean"),
        ("pve-member", "capable"),
        ("pve-member-fresh", "capable"),
        ("gpu-5090", "gpu"),
        ("rdna4-workstation", "gpu"),
        ("dgx-spark", "gpu"),
    ],
)
def test_node_type_mapping(node_type, expected):
    v = nct.classify(node_type=node_type)
    assert v["tier"] == expected
    assert v["source"] == "node-type"


def test_node_type_from_probe_field():
    v = nct.classify({"suggested_node_type": "gpu-5090"})
    assert v["tier"] == "gpu"
    assert v["source"] == "node-type"


# ── raw-threshold fallback ─────────────────────────────────────────────────
def test_threshold_lean_small_vps():
    v = nct.classify({"cpu": {"cores_logical": 4}, "ram_gb": 16, "gpus": []})
    assert v["tier"] == "lean"
    assert v["source"] == "thresholds"


def test_threshold_capable_strong_cpu_no_gpu():
    v = nct.classify({"cpu": {"cores_logical": 16}, "ram_gb": 64, "gpus": []})
    assert v["tier"] == "capable"


def test_threshold_gpu_capable_plus_gpu():
    v = nct.classify(
        {"cpu": {"cores_logical": 20}, "ram_gb": 64,
         "gpus": [{"vendor": "nvidia", "vram_gb": 32}]}
    )
    assert v["tier"] == "gpu"


def test_threshold_boundary_exact_capable():
    # exactly at the threshold counts as capable
    v = nct.classify({"cpu": {"cores_logical": 8}, "ram_gb": 32, "gpus": []})
    assert v["tier"] == "capable"


def test_threshold_just_below_capable_is_lean():
    v = nct.classify({"cpu": {"cores_logical": 8}, "ram_gb": 31, "gpus": []})
    assert v["tier"] == "lean"


def test_gpu_on_weak_node_stays_lean():
    # a big GPU on a weak CPU/RAM node cannot run the data tier -> lean
    v = nct.classify(
        {"cpu": {"cores_logical": 4}, "ram_gb": 16,
         "gpus": [{"vram_gb": 24}]}
    )
    assert v["tier"] == "lean"


def test_small_gpu_below_vram_floor_is_capable():
    v = nct.classify(
        {"cpu": {"cores_logical": 16}, "ram_gb": 64,
         "gpus": [{"vram_gb": 8}]}
    )
    assert v["tier"] == "capable"


def test_unknown_node_type_falls_back_to_thresholds():
    v = nct.classify(
        {"suggested_node_type": "mystery-box",
         "cpu": {"cores_logical": 16}, "ram_gb": 64, "gpus": []}
    )
    assert v["tier"] == "capable"
    assert v["source"] == "thresholds"
    assert "mystery-box" in v["rationale"]


# ── override ───────────────────────────────────────────────────────────────
@pytest.mark.parametrize("ov", ["lean", "capable", "gpu", "GPU", " Capable "])
def test_override_valid(ov):
    v = nct.classify({"cpu": {"cores_logical": 1}, "ram_gb": 1}, override=ov)
    assert v["tier"] == ov.strip().lower()
    assert v["source"] == "override"


def test_override_invalid_raises():
    with pytest.raises(ValueError):
        nct.classify({}, override="supercomputer")


# ── service sets ───────────────────────────────────────────────────────────
def test_services_extra_lean_empty():
    assert nct.services_extra("lean") == []


def test_services_extra_capable_has_data_tier():
    s = nct.services_extra("capable")
    assert {"supabase-local", "neo4j", "hi-rag-gateway-v2",
            "consciousness-service", "cipher-api", "archon"} <= set(s)
    assert "hi-rag-gateway-v2-gpu" not in s


def test_services_extra_gpu_superset_of_capable():
    cap = set(nct.services_extra("capable"))
    gpu = set(nct.services_extra("gpu"))
    assert cap <= gpu
    assert {"hi-rag-gateway-v2-gpu", "media-video", "media-audio"} <= gpu


def test_verdict_shape():
    v = nct.classify(node_type="gpu-5090")
    assert set(v) == {"tier", "rationale", "source", "services_extra"}


# ── empty/garbage probe ────────────────────────────────────────────────────
def test_empty_probe_is_lean():
    assert nct.classify({})["tier"] == "lean"
    assert nct.classify(None)["tier"] == "lean"


def test_garbage_fields_dont_crash():
    v = nct.classify({"cpu": {"cores_logical": "n/a"}, "ram_gb": None,
                      "gpus": [{"vram_gb": "x"}]})
    assert v["tier"] == "lean"
