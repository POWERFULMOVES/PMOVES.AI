#!/usr/bin/env python3
"""Compatibility ratchet: the mesh announcement plane <-> the node registry.

WHAT THIS RATCHET IS FOR
-------------------------
Five defects recorded in pmoves/docs/AGENTS/PRE_RESTART_PREFLIGHT_2026-08-25.md
(rows R8 and R8a) were never fixed:

  D1  mesh_exposure's live-registry assertion counted the curated set
      (`assert len(reg) == 12`) and had been RED for twelve weeks after the
      13th curated entry landed (crush.yaml, 2026-08-05, PR #2412);
  D2  the `resource-detector` package could not be imported under the name
      every importer used (`..resource_detector`), so four services could
      not be imported at all;
  D3  node-registry loaded its own modules by file path, so the relative
      imports inside them had no parent package;
  D4  the mesh published on `mesh.node.announce.v1` while the registry
      subscribed to `compute.nodes.announce.v1` -- two finished halves wired
      to different subject strings;
  D5  the `compute` JetStream stream the registry asks for was never
      created, so it silently fell back to core NATS.

This file fails if any of those comes back. It is HERMETIC: no network, no
NATS, no containers -- every assertion is read out of the source tree.

THE RULE THIS FILE FOLLOWS
--------------------------
Every assertion is POSITIVE. "The bad string is nowhere in the repo" is a
statement about absence, and absence cannot say no: a renamed subject, a
moved directory or a rewritten loader all slip past it. Each test below
names the thing that must BE true, and each import happens INSIDE the test
that needs it, so a broken import fails THAT test instead of collapsing the
whole module at collection time.
"""

from __future__ import annotations

import ast
import importlib
import importlib.util
import sys
import types
from pathlib import Path
from typing import Any, Dict, List

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SERVICES = REPO_ROOT / "pmoves" / "services"

RESOURCE_DETECTOR_DIR = SERVICES / "resource_detector"
NODE_REGISTRY_DIR = SERVICES / "node_registry"
WORK_MARSHALING_DIR = SERVICES / "work_marshaling"
VLLM_ORCHESTRATOR_DIR = SERVICES / "vllm_orchestrator"
MESH_AGENT_MAIN = SERVICES / "mesh-agent" / "main.py"

CURATED_DIR = REPO_ROOT / "pmoves" / "configs" / "pinokio-apps" / "curated"
INIT_STREAMS = REPO_ROOT / "pmoves" / "scripts" / "nats" / "init_streams.sh"
MESH_EXPOSURE_TEST = (
    SERVICES / "mesh_exposure" / "tests" / "test_app.py"
)

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _Any:
    """Permissive stand-in for a missing third-party dependency.

    Used ONLY for structlog, and ONLY when the real package is absent: the
    four service entry points call structlog.configure() at import time, so
    without the dependency they cannot be imported at all -- and the PRODUCTION
    loader is exactly the thing this ratchet has to exercise.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    def __call__(self, *args: Any, **kwargs: Any) -> "_Any":
        return _Any()

    def __getattr__(self, name: str) -> "_Any":
        return _Any()


def _ensure_structlog() -> None:
    """Install a structlog stub only when the real package is missing."""
    try:
        importlib.import_module("structlog")
        return
    except ImportError:
        pass
    stub = types.ModuleType("structlog")
    stub.__getattr__ = lambda name: _Any()  # type: ignore[attr-defined]
    sys.modules["structlog"] = stub


def _load_module_by_path(name: str, path: Path) -> types.ModuleType:
    """Load a module from a file path, the way a service entry point does."""
    spec = importlib.util.spec_from_file_location(name, str(path))
    assert spec is not None and spec.loader is not None, f"no loader for {path}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _module_constants(path: Path) -> Dict[str, str]:
    """Module-level string constants of a python file, by name."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    constants: Dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not isinstance(node.value, ast.Constant):
            continue
        if not isinstance(node.value.value, str):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                constants[target.id] = node.value.value
    return constants


def _published_subjects(path: Path) -> List[Any]:
    """The subjects a module publishes on, as AST nodes.

    Each entry is ("name", <constant name>) for a named constant or
    ("literal", <string>) for an inlined string. Keeping the distinction is
    the point: the ratchet asserts the publisher publishes on the NAMED
    constant, so nobody can quietly point the publisher at a different
    string while the constant still says the right thing.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    subjects: List[Any] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute) or func.attr != "publish":
            continue
        if not node.args:
            continue
        arg = node.args[0]
        if isinstance(arg, ast.Name):
            subjects.append(("name", arg.id))
        elif isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            subjects.append(("literal", arg.value))
    return subjects


def _mesh_exposure_expected_slugs() -> List[str]:
    """The curated slug set the mesh_exposure suite declares.

    Loaded from the real test module (single source of truth) rather than
    copied here, so the two files cannot drift apart silently.
    """
    module = _load_module_by_path(
        "pmoves_mesh_exposure_test_app", MESH_EXPOSURE_TEST
    )
    return list(module.EXPECTED_CURATED_SLUGS)


# ---------------------------------------------------------------------------
# D2 / D3 -- the four services import, and import AS packages
# ---------------------------------------------------------------------------


def test_the_four_services_import_under_their_canonical_package_names() -> None:
    """D2: every service package imports under the name its importers use.

    Before the fix, `pmoves.services.resource_detector` did not exist (the
    directory was `resource-detector`), so EVERY `from ..resource_detector...`
    in the repo raised ModuleNotFoundError and none of these four services
    could be imported at all.

    All four directories are now snake_case, so all four are REAL packages and
    a PLAIN import is the assertion. A file-path loader would have papered
    over the directory/import-name disagreement this test exists to catch.
    """
    resource_detector = importlib.import_module("pmoves.services.resource_detector")
    node_registry = importlib.import_module("pmoves.services.node_registry")
    work_marshaling = importlib.import_module("pmoves.services.work_marshaling")
    vllm_orchestrator = importlib.import_module("pmoves.services.vllm_orchestrator")

    assert resource_detector.NodeCapabilities.__name__ == "NodeCapabilities"
    assert resource_detector.NodeTier.CPU_PEER.value == "cpu_peer"
    assert node_registry.NodeRegistry.__name__ == "NodeRegistry"
    assert work_marshaling.WorkMarshaling.__name__ == "WorkMarshaling"
    assert vllm_orchestrator.VLLMOrchestrator.__name__ == "VLLMOrchestrator"


def test_the_service_entry_points_resolve_their_imports_without_a_package() -> None:
    """D3: each entry point resolves its imports when launched as a SCRIPT.

    `python pmoves/services/<service>/main.py` gives the module no package
    context -- which is exactly the case that broke: the relative imports
    inside the services raised "attempted relative import with no known
    parent package" and the services could not start at all. This exercises
    the PRODUCTION loaders in that mode, not a copy of them.
    """
    _ensure_structlog()

    resource_detector_main = _load_module_by_path(
        "pmoves_node_registry_scriptmode_resource_detector",
        RESOURCE_DETECTOR_DIR / "main.py",
    )
    node_registry_main = _load_module_by_path(
        "pmoves_node_registry_scriptmode",
        NODE_REGISTRY_DIR / "main.py",
    )
    work_marshaling_main = _load_module_by_path(
        "pmoves_work_marshaling_main", WORK_MARSHALING_DIR / "main.py"
    )
    vllm_orchestrator_main = _load_module_by_path(
        "pmoves_vllm_orchestrator_main", VLLM_ORCHESTRATOR_DIR / "main.py"
    )

    assert resource_detector_main.get_hardware_profile is not None
    assert node_registry_main.NodeRegistry.__name__ == "NodeRegistry"
    assert work_marshaling_main.WorkMarshaling.__name__ == "WorkMarshaling"
    assert vllm_orchestrator_main.VLLMOrchestrator.__name__ == "VLLMOrchestrator"


def test_the_node_registry_modules_carry_their_package_context() -> None:
    """D3: the registry's modules are imported INSIDE their package.

    `__package__` is the proof: a module loaded by file path has no package
    context, so its relative imports (`from ..resource_detector.models ...`)
    could not resolve. This is a positive assertion about the import
    mechanism, not a grep for "the bad pattern is gone".
    """
    registry = importlib.import_module("pmoves.services.node_registry.registry")
    storage = importlib.import_module("pmoves.services.node_registry.storage")
    api = importlib.import_module("pmoves.services.node_registry.api")

    assert registry.__package__ == "pmoves.services.node_registry"
    assert storage.__package__ == "pmoves.services.node_registry"
    assert api.__package__ == "pmoves.services.node_registry"


def test_the_services_share_one_resource_detector_module_identity() -> None:
    """D2: the shared models are ONE module, not several copies.

    If each service reached the models through a different path (a relative
    import in one, a file-path load in another), the classes would be
    distinct objects and every isinstance check across the boundary would
    silently fail.
    """
    resource_detector_models = importlib.import_module(
        "pmoves.services.resource_detector.models"
    )
    node_registry_registry = importlib.import_module(
        "pmoves.services.node_registry.registry"
    )
    work_marshaling = importlib.import_module("pmoves.services.work_marshaling")

    assert (
        node_registry_registry.NodeCapabilities
        is resource_detector_models.NodeCapabilities
    )
    assert work_marshaling.WorkRequest is resource_detector_models.WorkRequest


# ---------------------------------------------------------------------------
# D4 -- the mesh and the registry agree on the announce subjects
# ---------------------------------------------------------------------------


def test_the_registry_subscribes_to_the_subjects_the_mesh_publishes() -> None:
    """D4: publisher and subscriber name the SAME subject.

    The mesh published on `mesh.node.announce.v1` / `.v2` (mesh-agent, the
    deployed publisher, plus the node bootstrap scripts) while the registry
    subscribed to `compute.nodes.announce.v1`: two finished halves wired to
    different strings, so the announcements reached nobody.
    """
    constants = _module_constants(MESH_AGENT_MAIN)
    node_registry = importlib.import_module("pmoves.services.node_registry")

    assert constants["MESH_ANNOUNCE_SUBJECT_V1"] == "mesh.node.announce.v1"
    assert constants["MESH_ANNOUNCE_SUBJECT_V2"] == "mesh.node.announce.v2"

    assert node_registry.SUBJECTS["announce"] == constants["MESH_ANNOUNCE_SUBJECT_V1"]
    assert (
        node_registry.SUBJECTS["announce_v2"] == constants["MESH_ANNOUNCE_SUBJECT_V2"]
    )
    # The JetStream consumer takes the whole family in one subscription.
    assert (
        node_registry.SUBJECTS["announce_family"]
        == "mesh.node.announce.>"
    )


def test_the_mesh_agent_publishes_on_the_named_announce_subjects() -> None:
    """D4: the publisher actually publishes on those constants.

    Naming a constant is not enough -- the publish call has to use it, or the
    constant and the wire would drift apart again.
    """
    published = _published_subjects(MESH_AGENT_MAIN)
    assert ("name", "MESH_ANNOUNCE_SUBJECT_V1") in published
    assert ("name", "MESH_ANNOUNCE_SUBJECT_V2") in published
    # No publish call may hard-code a subject string.
    assert [entry for entry in published if entry[0] == "literal"] == []


def test_the_registry_understands_every_published_announcement_dialect() -> None:
    """D4: every announcement shape in the repo maps onto a node record.

    The registry used to hand announcements to the parser for its OWN full
    capability message, so every real announcement -- which carries presence,
    not hardware -- raised KeyError('node_id') and was dropped. The registry
    stayed empty even once the subject matched.
    """
    registry = importlib.import_module("pmoves.services.node_registry.registry")

    # mesh-agent v1 (pmoves/services/mesh-agent/main.py)
    v1 = {
        "type": "mesh.node.announce.v1",
        "node": "spark-01",
        "caps": {"clip": True, "rag": True},
        "host": "100.64.0.7",
        "tailscale_ip": "100.64.0.7",
        "mode": "docked",
        "ts": 1_700_000_000,
    }
    caps_v1 = registry.capabilities_from_announcement(v1)
    assert caps_v1.node_id == "spark-01"
    assert caps_v1.hostname == "spark-01"
    assert caps_v1.tier.value == "cpu_peer"
    assert caps_v1.ipv4 == "100.64.0.7"

    # mesh-agent v2 -- namespace identity + topology
    v2 = {
        "type": "mesh.node.announce.v2",
        "node": "b850-01",
        "slug": "b850",
        "caps": {"rag": True},
        "host": "100.64.0.9",
        "ts": 1_700_000_000,
        "namespace": {"project": "pmoves", "tier": "gpu_peer", "branch": "main"},
        "topology": {"mode": "auto", "supabase_runtime": "compose"},
        "peers": ["spark-01"],
        "health": {"status": "announcing"},
    }
    caps_v2 = registry.capabilities_from_announcement(v2)
    assert caps_v2.node_id == "b850"
    assert caps_v2.hostname == "b850-01"
    assert caps_v2.tier.value == "gpu_peer"

    # the node bootstrap scripts (pmoves/scripts/bootstrap-node.sh)
    bootstrap = {"node_id": "node-42", "profile": "laptop", "status": "online", "ts": 1_700_000_000}
    caps_bootstrap = registry.capabilities_from_announcement(bootstrap)
    assert caps_bootstrap.node_id == "node-42"
    assert caps_bootstrap.hostname == "node-42"

    # An announcement with no identity at all is refused, not guessed at.
    with pytest.raises(ValueError):
        registry.capabilities_from_announcement({"type": "mesh.node.announce.v1"})


def test_the_registry_does_not_invent_capacity_from_an_announcement() -> None:
    """D4: presence is not capacity.

    An announcement carries no hardware facts, so the registry must not
    register the node as having free CPU/RAM/GPU -- otherwise the work
    allocator routes jobs to a node that never said it could take them.
    """
    registry = importlib.import_module("pmoves.services.node_registry.registry")

    caps = registry.capabilities_from_announcement(
        {"node": "spark-01", "ts": 1_700_000_000}
    )
    assert caps.available_cpu_slots == 0
    assert caps.available_memory_mb == 0
    assert caps.available_gpu_slots == 0
    assert caps.available_vram_mb == 0
    assert caps.gpus == []


# ---------------------------------------------------------------------------
# D1 -- the curated registry set
# ---------------------------------------------------------------------------


def test_the_curated_registry_set_matches_the_curated_directory() -> None:
    """D1: the mesh exposes exactly the curated set, and the set is named.

    The old assertion was `assert len(reg) == 12`: a count rotted the moment
    the curated set legitimately grew, and it stayed red for twelve weeks
    because a red test in an optional service suite is easy to miss. The
    contract is now the SLUG SET -- it says which apps the mesh exposes, it
    fails when an entry disappears, and it fails when one is added (which is
    then an intentional, visible diff).
    """
    sys.path.insert(0, str(SERVICES))
    try:
        from mesh_exposure.state import Registry  # type: ignore
    finally:
        sys.path.remove(str(SERVICES))

    expected = _mesh_exposure_expected_slugs()
    on_disk = sorted(path.stem for path in CURATED_DIR.glob("*.yaml"))

    assert on_disk == expected, (
        "the curated directory and the declared slug set disagree -- an entry "
        "was added or removed without the contract being updated"
    )

    reg = Registry.load_from_dir(str(CURATED_DIR))
    assert reg.slugs == expected
    assert len(reg) == len(expected)


# The four exposure layers the slice-4 contract names, and the ONLY names
# `pmoves/services/mesh_exposure/state.py` reads.
CANONICAL_EXPOSURE_LAYERS = (
    "l1_venv",
    "l2_container_same_host",
    "l3_mesh",
    "l4_public",
)


def test_the_curated_entries_declare_the_canonical_exposure_layers() -> None:
    """Every curated entry declares the four layers under the names the planner reads.

    `crush.yaml` was authored against the `layer_1..layer_4` vocabulary of the
    CRUSH_IN_PINOKIO_PLAN_2026-08-04 handoff. The four concepts are the same,
    so the entry PARSED -- and the planner, which reads `l3_mesh` / `l4_public`
    only, saw crush as having NO exposure contract at all. The mesh was blind
    to a curated app that the registry listed.

    The alias was the worst kind of tolerance: a TEST that accepted the legacy
    spelling while the PRODUCT ignored it. So the check is exact, and the entry
    has been migrated.
    """
    import yaml

    offenders: List[str] = []
    for path in sorted(CURATED_DIR.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        exposure = data.get("network_exposure") or {}
        declared = set(exposure)
        if declared != set(CANONICAL_EXPOSURE_LAYERS):
            offenders.append(
                f"{path.name}: {sorted(declared)} != "
                f"{sorted(CANONICAL_EXPOSURE_LAYERS)}"
            )
            continue
        for layer in CANONICAL_EXPOSURE_LAYERS:
            if "reachable" not in (exposure.get(layer) or {}):
                offenders.append(f"{path.name}: layer '{layer}' has no 'reachable'")

    assert not offenders, (
        "curated entries must declare the canonical exposure layers the "
        "mesh_exposure planner reads -- an entry in another vocabulary parses "
        "but contributes NO exposure rules:\n  " + "\n  ".join(offenders)
    )


# ---------------------------------------------------------------------------
# D5 -- the `compute` JetStream stream
# ---------------------------------------------------------------------------


def test_the_compute_stream_carries_the_announce_family() -> None:
    """D5: the stream the registry asks for exists and covers its subjects.

    The registry subscribes with `stream="compute"`; no stream named
    `compute` was ever created, so every subscribe attempt failed and the
    registry silently fell back to core NATS -- announcements published while
    it was down were gone for good.
    """
    registry = importlib.import_module("pmoves.services.node_registry.registry")
    assert registry.ANNOUNCE_STREAM == "compute"

    script = INIT_STREAMS.read_text(encoding="utf-8")
    assert "add_stream COMPUTE \\" in script, (
        "init_streams.sh does not create the COMPUTE stream the node "
        "registry subscribes to"
    )

    block = script.split("add_stream COMPUTE \\", 1)[1]
    subjects_line = next(
        line for line in block.splitlines() if "--subjects" in line
    )
    assert "mesh.node.announce.>" in subjects_line, (
        "the COMPUTE stream does not cover the mesh announcement family -- "
        "the registry's JetStream consumer would fall back to core NATS"
    )
    assert "compute.nodes.>" in subjects_line
    assert "--retention limits" in block, (
        "the COMPUTE stream must use `limits` retention: under `interest` a "
        "message with no bound consumer is discarded silently"
    )


def test_the_registry_does_not_subscribe_to_a_subject_nobody_publishes() -> None:
    """D4: the registry's own protocol subjects stay on the compute family.

    The announce subjects moved to the mesh family (that is the fix); the
    registry's query/drain protocol stays where it is, and the mesh family is
    the one the publishers actually use.
    """
    node_registry = importlib.import_module("pmoves.services.node_registry")

    assert node_registry.SUBJECTS["announce"].startswith("mesh.node.announce.")
    assert node_registry.SUBJECTS["announce_v2"].startswith("mesh.node.announce.")
    assert node_registry.SUBJECTS["query"].startswith("compute.nodes.")
    assert node_registry.SUBJECTS["drain"].startswith("compute.nodes.")
