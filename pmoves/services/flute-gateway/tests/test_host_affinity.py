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


def test_all_nodes_exist_in_fleet_registries(cap_data):
    """Every configured slug must be a real fleet node — operator_nodes.yaml
    node_ids plus the CPU-only Hostinger KVMs. Guards against drift like
    'b850' (hardware name) vs 'knuckles' (registry node_id): a slug matching
    no registry means registry-fed resolution silently never routes there."""
    op_path = Path(__file__).resolve().parents[3] / "config" / "operator_nodes.yaml"
    with open(op_path, encoding="utf-8") as f:
        op_data = yaml.safe_load(f)
    known = {str(n["node_id"]) for n in op_data["nodes"]} | _KVM_NODES
    for engine, row in cap_data["host_affinity"].items():
        unknown = {str(n) for n in row["nodes"]} - known
        assert not unknown, (
            f"{engine}: node slugs {sorted(unknown)} match no fleet registry "
            f"(operator_nodes.yaml node_ids + KVMs = {sorted(known)})"
        )


def test_all_node_ids_are_strings(cap_data):
    """Numeric slugs like 5090/4090 must be quoted — bare YAML ints break the
    str membership check in resolve_engine_host()."""
    for engine, row in cap_data["host_affinity"].items():
        for node in row["nodes"]:
            assert isinstance(node, str), f"{engine}: node {node!r} is not a str (quote it in YAML)"
        assert isinstance(row["preferred"], str), f"{engine}: preferred {row['preferred']!r} is not a str"


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


@pytest.mark.skipif(not _PS_AVAILABLE, reason="persona_selector import chain unavailable")
def test_resolver_numeric_node_slug_matches_as_string():
    # higgs prefers the numeric-slug node "5090"; it must resolve when up.
    res = ps.resolve_engine_host("higgs", available_nodes=["5090"])
    assert res["selected"] == "5090"


@pytest.mark.skipif(not _PS_AVAILABLE, reason="persona_selector import chain unavailable")
def test_resolver_tolerates_int_available_node():
    # Defense-in-depth: an int node id from a caller still matches the string slug.
    res = ps.resolve_engine_host("higgs", available_nodes=[5090])
    assert str(res["selected"]) == "5090"


# --- resolve_engine_target: the synthesis-path host-affinity seam ---

_CONFIGURED = "http://host.docker.internal:7860"


@pytest.mark.skipif(not _PS_AVAILABLE, reason="persona_selector import chain unavailable")
def test_target_disabled_returns_configured_url():
    # Opt-in OFF → single-configured-URL behaviour, no node.
    url, node = ps.resolve_engine_target("kokoro", _CONFIGURED, enabled=False)
    assert url == _CONFIGURED
    assert node is None


@pytest.mark.skipif(not _PS_AVAILABLE, reason="persona_selector import chain unavailable")
def test_target_host_swaps_to_preferred_node():
    # Enabled + preferred up → host swapped to pmoves-<node>, port preserved.
    url, node = ps.resolve_engine_target("kokoro", _CONFIGURED, enabled=True)
    assert node == "kvm4-2"
    assert url == "http://pmoves-kvm4-2:7860"


@pytest.mark.skipif(not _PS_AVAILABLE, reason="persona_selector import chain unavailable")
def test_target_falls_back_to_next_up_node():
    url, node = ps.resolve_engine_target(
        "kokoro", _CONFIGURED, available_nodes=["kvm4-1", "spark"], enabled=True,
    )
    assert node == "kvm4-1"
    assert url == "http://pmoves-kvm4-1:7860"


@pytest.mark.skipif(not _PS_AVAILABLE, reason="persona_selector import chain unavailable")
def test_target_numeric_node_becomes_hostname():
    url, node = ps.resolve_engine_target(
        "higgs", _CONFIGURED, available_nodes=["5090"], enabled=True,
    )
    assert node == "5090"
    assert url == "http://pmoves-5090:7860"


@pytest.mark.skipif(not _PS_AVAILABLE, reason="persona_selector import chain unavailable")
def test_target_no_eligible_node_falls_back():
    # GPU engine, only a CPU KVM up → no node selected → configured URL.
    url, node = ps.resolve_engine_target(
        "indextts2", _CONFIGURED, available_nodes=["kvm4-2"], enabled=True,
    )
    assert url == _CONFIGURED
    assert node is None


@pytest.mark.skipif(not _PS_AVAILABLE, reason="persona_selector import chain unavailable")
def test_target_unknown_engine_falls_back():
    # e.g. the omnivoice branch: no host_affinity row → configured URL used.
    url, node = ps.resolve_engine_target("omnivoice", _CONFIGURED, enabled=True)
    assert url == _CONFIGURED
    assert node is None


@pytest.mark.skipif(not _PS_AVAILABLE, reason="persona_selector import chain unavailable")
def test_target_preserves_path_and_query():
    url, node = ps.resolve_engine_target(
        "kokoro", "https://host.docker.internal:8002/tts?fmt=wav", enabled=True,
    )
    assert node == "kvm4-2"
    assert url == "https://pmoves-kvm4-2:8002/tts?fmt=wav"


@pytest.mark.skipif(not _PS_AVAILABLE, reason="persona_selector import chain unavailable")
def test_target_preserves_userinfo_in_url():
    # Routing keeps embedded credentials in the target URL (so the cast still
    # authenticates), while the info log uses only the credential-free host:port
    # (guards against clear-text password logging — CodeQL py/clear-text-logging).
    url, node = ps.resolve_engine_target(
        "kokoro", "http://user:secretpw@host.docker.internal:7860", enabled=True,
    )
    assert node == "kvm4-2"
    assert url == "http://user:secretpw@pmoves-kvm4-2:7860"


@pytest.mark.skipif(not _PS_AVAILABLE, reason="persona_selector import chain unavailable")
def test_node_to_host_prefixes_and_passthrough():
    assert ps.node_to_host("spark") == "pmoves-spark"
    assert ps.node_to_host("5090") == "pmoves-5090"
    assert ps.node_to_host("pmoves-kvm4-2") == "pmoves-kvm4-2"  # already prefixed
