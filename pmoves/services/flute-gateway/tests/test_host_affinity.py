"""Tests for voice host-affinity (persona -> engine -> NODE routing).

Two layers:
  1. YAML data integrity (no gateway import) — every engine has a valid
     host_affinity row, CPU-viable engines route to the KVMs, GPU engines
     require cuda + min_vram_mb and never list a CPU-only KVM.
  2. Resolver behaviour — persona_selector.resolve_engine_host() picks the
     preferred node, honours an available-nodes filter, and returns None for
     an unknown engine (import guarded; skips if gateway deps are absent).
"""

import os
import sys
from pathlib import Path

import pytest
import yaml

_CAP_PATH = Path(__file__).resolve().parents[3] / "configs" / "tts-engine-capabilities.yaml"

# CPU-only Hostinger VPS nodes — GPU engines must never route here.
_KVM_NODES = {"kvm4-1", "kvm4-2", "kvm2"}


@pytest.fixture(scope="module")
def cap_data() -> dict:
    with open(_CAP_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_every_engine_has_host_affinity(cap_data):
    engines = set(cap_data["engines"].keys())
    affinity = set(cap_data["host_affinity"].keys())
    missing = engines - affinity
    assert not missing, f"engines missing a host_affinity row: {sorted(missing)}"
    orphan = affinity - engines
    assert not orphan, f"host_affinity rows with no engine: {sorted(orphan)}"


def test_host_affinity_schema(cap_data):
    for engine, row in cap_data["host_affinity"].items():
        assert row.get("requires") in {"cpu", "cuda", "rocm"}, f"{engine}: bad requires"
        assert isinstance(row.get("nodes"), list) and row["nodes"], f"{engine}: nodes must be non-empty"
        assert row.get("preferred"), f"{engine}: preferred required"
        assert row["preferred"] in row["nodes"], f"{engine}: preferred not in nodes"
        if row["requires"] != "cpu":
            assert isinstance(row.get("min_vram_mb"), int), f"{engine}: GPU engine needs min_vram_mb"


def test_cpu_engines_route_to_kvms(cap_data):
    """The agents-talking-on-cheap-nodes contract: kokoro + kitten reach the KVMs."""
    for engine in ("kokoro", "kitten_tts"):
        row = cap_data["host_affinity"][engine]
        assert row["requires"] == "cpu", f"{engine} should be cpu-viable"
        assert _KVM_NODES & set(row["nodes"]), f"{engine} must be runnable on a KVM"
        assert row["preferred"] in _KVM_NODES, f"{engine} should prefer a KVM"


def test_gpu_engines_never_route_to_kvms(cap_data):
    for engine, row in cap_data["host_affinity"].items():
        if row["requires"] == "cpu":
            continue
        assert not (_KVM_NODES & set(row["nodes"])), (
            f"{engine} is a GPU engine but lists a CPU-only KVM in nodes: {row['nodes']}"
        )


# --- Resolver behaviour (guarded import — skip if gateway deps unavailable) ---

_parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _parent not in sys.path:
    sys.path.insert(0, _parent)

try:
    import persona_selector as ps
    _PS_AVAILABLE = True
except Exception:  # pragma: no cover - import chain (httpx etc.) may be absent
    _PS_AVAILABLE = False


@pytest.mark.skipif(not _PS_AVAILABLE, reason="persona_selector import chain unavailable")
def test_resolver_prefers_preferred_node():
    res = ps.resolve_engine_host("kokoro")
    assert res is not None
    assert res["selected"] == res["preferred"] == "kvm4-2"


@pytest.mark.skipif(not _PS_AVAILABLE, reason="persona_selector import chain unavailable")
def test_resolver_falls_back_when_preferred_down():
    # preferred kvm4-2 is down; next eligible up node wins.
    res = ps.resolve_engine_host("kokoro", available_nodes=["kvm4-1", "spark"])
    assert res["selected"] == "kvm4-1"


@pytest.mark.skipif(not _PS_AVAILABLE, reason="persona_selector import chain unavailable")
def test_resolver_none_when_no_eligible_node_up():
    res = ps.resolve_engine_host("indextts2", available_nodes=["kvm4-2"])  # GPU engine, only a KVM up
    assert res["selected"] is None


@pytest.mark.skipif(not _PS_AVAILABLE, reason="persona_selector import chain unavailable")
def test_resolver_unknown_engine_returns_none():
    assert ps.resolve_engine_host("no_such_engine") is None
