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
import inspect
import json
import re
import sys
import types
from pathlib import Path
from typing import Any, Dict, List, Optional

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
VALIDATE_STREAMS = REPO_ROOT / "pmoves" / "scripts" / "nats" / "validate_streams.py"
REGISTRY_PY = NODE_REGISTRY_DIR / "registry.py"
STORAGE_PY = NODE_REGISTRY_DIR / "storage.py"
REGISTRY_API_PY = NODE_REGISTRY_DIR / "api.py"
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
    # MARKED. A stub answers ANY attribute, so any check that asks the
    # structlog module about its API must be able to tell a stub from the
    # real package. Without this marker a sibling test that installs the
    # stub makes every later "ask structlog" check run against a module
    # that agrees with everything -- and a check that always agrees is a
    # check that cannot say no.
    stub.__pmoves_permissive_stub__ = True  # type: ignore[attr-defined]
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
# Helpers for the merge-gate findings (F1-F5)
# ---------------------------------------------------------------------------


def _dotted(node: ast.AST) -> str:
    """The dotted source of an attribute/name chain, e.g. `self._js.subscribe`."""
    parts: List[str] = []
    current = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if not isinstance(current, ast.Name):
        return ""
    parts.append(current.id)
    return ".".join(reversed(parts))


def _render(node: ast.AST) -> str:
    """A readable rendering of the simple expressions used by these checks."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Constant):
        return repr(node.value)
    if isinstance(node, ast.Attribute):
        return f"{_render(node.value)}.{node.attr}"
    if isinstance(node, ast.Subscript):
        return f"{_render(node.value)}[{_render(node.slice)}]"
    if isinstance(node, ast.Call):
        return f"{_render(node.func)}(...)"
    if isinstance(node, ast.Tuple):
        return "(" + ", ".join(_render(e) for e in node.elts) + ")"
    return "<expr>"


def _class_method(tree: ast.AST, class_name: str, method_name: str) -> ast.FunctionDef:
    """The source of one method of one class, by name."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef) or node.name != class_name:
            continue
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if item.name == method_name:
                    return item  # type: ignore[return-value]
    raise AssertionError(f"{class_name}.{method_name} is not in the source")


class _LoopResolver(ast.NodeVisitor):
    """Maps the name of every `for` loop target to the tuple it iterates."""

    def __init__(self) -> None:
        self.loops: Dict[str, ast.AST] = {}

    def visit_For(self, node: ast.For) -> None:
        if isinstance(node.target, ast.Name):
            self.loops[node.target.id] = node.iter
        self.generic_visit(node)


def _add_stream_blocks(script: str) -> Dict[str, List[str]]:
    """The `add_stream <NAME> ...` blocks of init_streams.sh, by stream name.

    A block is the `add_stream` line plus every continuation line (a
    continuation is a line that ends with a backslash) -- which is how the
    script itself is written.
    """
    blocks: Dict[str, List[str]] = {}
    lines = script.splitlines()
    index = 0
    while index < len(lines):
        stripped = lines[index].strip()
        if not stripped.startswith("add_stream "):
            index += 1
            continue
        name = stripped.split()[1]
        body = [stripped]
        index += 1
        while body[-1].endswith("\\"):
            body.append(lines[index].strip())
            index += 1
        blocks[name] = body
    return blocks


def _subjects_argument(block: List[str]) -> str:
    """The raw `--subjects` value declared by an `add_stream` block."""
    for line in block:
        match = re.search(r'--subjects\s+"([^"]*)"', line)
        if match:
            return match.group(1)
    raise AssertionError("the add_stream block declares no --subjects argument")


def _core_subscribed_subjects(tree: ast.AST, subjects: Dict[str, str]) -> List[str]:
    """Every subject the registry core-NATS subscribes to, fully resolved.

    A subscription argument is either `SUBJECTS["key"]` (resolved through
    the literal table) or the loop variable of a `for` over a tuple of such
    keys (the announce fallback), which is resolved through the same table.
    """
    resolver = _LoopResolver()
    resolver.visit(tree)

    resolved: List[str] = []
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and _dotted(node.func) == "self._nc.subscribe"
            and node.args
        ):
            continue
        arg = node.args[0]
        if isinstance(arg, ast.Subscript) and isinstance(arg.slice, ast.Constant):
            key = arg.slice.value
            assert isinstance(key, str)
            resolved.append(subjects[key])
        elif isinstance(arg, ast.Name):
            iterated = resolver.loops.get(arg.id)
            assert isinstance(iterated, ast.Tuple), (
                "a core-NATS subscription is made on a name that is not "
                f"resolved from the SUBJECTS table: {arg.id}"
            )
            for element in iterated.elts:
                assert isinstance(element, ast.Subscript) and isinstance(
                    element.slice, ast.Constant
                ), "the subscribed subject is not a SUBJECTS[...] lookup"
                key = element.slice.value
                assert isinstance(key, str)
                resolved.append(subjects[key])
        else:
            raise AssertionError(
                f"unrecognised subscription subject expression: {_render(arg)}"
            )
    return sorted(resolved)


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


def test_the_entry_points_use_only_structlog_api_that_exists() -> None:
    """The entry points configure structlog AT IMPORT TIME, so an API that
    was never real breaks the module in EVERY environment.

    `node_registry/main.py` passed `cache_class=structlog.WriteLogFile`.
    Neither half of that has ever existed: `WriteLogFile` is not exported by
    structlog 21.5.0, 22.3.0, 24.4.0 (the version pmoves/requirements.txt
    pins) or 26.1.0 (what the unpinned pmoves/requirements-tests.txt
    resolves to in the merge gate) -- the wheels were unpacked and grepped to
    confirm -- and `cache_class` is not in `configure()`'s signature in any of
    them either. So the call raised AttributeError, and would have raised
    TypeError even if the attribute had existed.

    WHY THIS RATCHET EXISTS: the permissive structlog STUB this file installs
    when structlog is absent (`_ensure_structlog`) answers ANY attribute, so
    the bad call sailed through on a developer machine. Only CI, which
    installs the real package, could see it. A stub that lets you import is
    not a stub that lets you TRUST the import.

    So the check is against the REAL structlog, and it skips -- with a reason
    -- when the real package is absent. CI installs it, so CI enforces it.
    """
    try:
        real = importlib.import_module("structlog")
    except ImportError:
        pytest.skip(
            "structlog is not installed here; the permissive stub would accept "
            "any API, so this check would be vacuous"
        )
    if getattr(real, "__pmoves_permissive_stub__", False):
        pytest.skip(
            "the structlog module in sys.modules is the PERMISSIVE STUB this "
            "file installs when the real package is absent -- it answers any "
            "attribute, so asking it about the API proves nothing. CI "
            "installs the real structlog, so CI enforces this check."
        )

    configure_signature = inspect.signature(real.configure).parameters
    accepted = set(configure_signature)

    offenders: List[str] = []
    for entry_point in (
        NODE_REGISTRY_DIR / "main.py",
        WORK_MARSHALING_DIR / "main.py",
        VLLM_ORCHESTRATOR_DIR / "main.py",
        RESOURCE_DETECTOR_DIR / "main.py",
    ):
        tree = ast.parse(entry_point.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            # structlog.configure(...) -- the keyword arguments it is given
            # must all be parameters the installed structlog accepts.
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "configure"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "structlog"
            ):
                continue
            for keyword in node.keywords:
                if keyword.arg is None:
                    continue
                if keyword.arg not in accepted:
                    offenders.append(
                        f"{entry_point.parent.name}/{entry_point.name}: "
                        f"structlog.configure({keyword.arg}=...) -- "
                        f"'{'/'.join(accepted)}' are the accepted parameters"
                    )

        # structlog.<attribute> -- every attribute the module reads off the
        # package must exist on the installed version.
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id == "structlog"
                and not hasattr(real, node.attr)
            ):
                offenders.append(
                    f"{entry_point.parent.name}/{entry_point.name}: "
                    f"structlog.{node.attr} does not exist in structlog "
                    f"{getattr(real, '__version__', '?')}"
                )

    assert not offenders, (
        "the entry points use structlog API that does not exist in the "
        "installed structlog, so they cannot be imported:\n  "
        + "\n  ".join(sorted(set(offenders)))
    )


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

    The registry subscribes with the stream named `COMPUTE`; no stream of
    that name was ever created, so every subscribe attempt failed and the
    registry silently fell back to core NATS -- announcements published while
    it was down were gone for good.

    JetStream stream names are case-sensitive, so the name in the registry
    has to be the name init_streams.sh creates, byte for byte.
    """
    registry = importlib.import_module("pmoves.services.node_registry.registry")
    assert registry.ANNOUNCE_STREAM == "COMPUTE"

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


# ---------------------------------------------------------------------------
# F1-F5 -- the merge-gate findings (2026-10-31)
# ---------------------------------------------------------------------------


def test_the_compute_stream_declares_its_subjects_as_a_comma_separated_list() -> None:
    """F1: the COMPUTE subject list is comma-separated.

    HONESTY NOTE FIRST, because the temptation to overstate the finding is
    worse than the finding: the nats CLI splits a `--subjects` value on a
    comma OR on whitespace, so the OLD space-separated form DID create a
    two-subject stream against the pinned CLI (nats-box 0.14.5 / nats CLI
    v0.1.5) and against v0.5.1 as well. The old form was NOT broken.

    The comma form is the CANONICAL list form: it is unambiguous, it is
    what the nats CLI documents, and it is the form the validator reads back
    out of `nats stream info COMPUTE -j`. A subject may not contain a
    space -- the server answers `invalid subject (10052)` -- so the
    separator has to be one the CLI strips, and a comma is the only
    separator that is never part of a subject.
    """
    script = INIT_STREAMS.read_text(encoding="utf-8")
    blocks = _add_stream_blocks(script)
    assert "COMPUTE" in blocks, (
        "init_streams.sh does not create the COMPUTE stream the node "
        "registry subscribes to"
    )

    subjects = _subjects_argument(blocks["COMPUTE"])
    parts = subjects.split(",")
    assert len(parts) == 2, (
        "the COMPUTE stream must declare exactly two subject families in one "
        f"comma-separated list; got {parts!r}"
    )
    assert set(parts) == {"mesh.node.announce.>", "compute.nodes.>"}, (
        f"the COMPUTE stream declares the wrong subject families: {parts!r}"
    )
    assert all(part and part.strip() == part for part in parts), (
        f"the comma-separated subject list has an empty or padded entry: {parts!r}"
    )


def test_the_registry_and_the_stream_script_name_the_same_stream() -> None:
    """F2: the registry, init_streams.sh and the validator name ONE stream.

    JetStream stream names are case-sensitive. The registry asked for
    `stream="compute"` while init_streams.sh creates `COMPUTE`, so every
    subscribe attempt failed and the registry silently fell back to core
    NATS -- losing every announcement published while it was down.

    The three sides are checked against EACH OTHER, not against a literal
    repeated in this file: a name that is right in one place and wrong in
    another is exactly the defect.
    """
    registry = importlib.import_module("pmoves.services.node_registry.registry")
    validator = _load_module_by_path("pmoves_validate_streams_f2", VALIDATE_STREAMS)
    script = INIT_STREAMS.read_text(encoding="utf-8")
    blocks = _add_stream_blocks(script)

    expected_names = {row.name for row in validator.EXPECTED_STREAMS}
    assert set(blocks) == expected_names, (
        "init_streams.sh and validate_streams.py disagree about which "
        f"streams exist: {sorted(set(blocks) ^ expected_names)}"
    )

    assert registry.ANNOUNCE_STREAM in expected_names, (
        f"the registry asks for {registry.ANNOUNCE_STREAM!r}, which no "
        "declared stream provides"
    )
    assert registry.ANNOUNCE_STREAM in blocks, (
        f"the registry asks for {registry.ANNOUNCE_STREAM!r}, which "
        "init_streams.sh does not create"
    )
    assert registry.ANNOUNCE_STREAM == "COMPUTE", (
        "the registry's stream name must be the uppercase name "
        f"init_streams.sh creates: {registry.ANNOUNCE_STREAM!r} != 'COMPUTE'"
    )

    # Every stream's subject set is agreed by the creator and the guard.
    for row in validator.EXPECTED_STREAMS:
        script_subjects = set(_subjects_argument(blocks[row.name]).split(","))
        assert script_subjects == set(row.subjects), (
            f"{row.name}: init_streams.sh declares {sorted(script_subjects)} "
            f"but validate_streams.py expects {sorted(row.subjects)}"
        )


def test_the_registry_holds_one_subscription_per_subject_family() -> None:
    """F3: the announce family is subscribed ONCE, and there is no second
    subscription for the heartbeat.

    The mesh has no separate heartbeat subject -- it re-announces every
    ANNOUNCE_SEC seconds, so the announcement IS the heartbeat. The
    registry used to hold BOTH a JetStream subscription on the announce
    family AND a core-NATS subscription on the same v1 subject, so every
    announcement was delivered TWICE and the second copy existed only to
    keep a "heartbeat" subject alive in the SUBJECTS table.

    The assertion is an EXACT SET of what the registry subscribes to, so a
    fifth subscription -- a heartbeat one -- fails this test.
    """
    registry = importlib.import_module("pmoves.services.node_registry.registry")
    tree = ast.parse(REGISTRY_PY.read_text(encoding="utf-8"))

    assert set(registry.SUBJECTS) == {
        "announce",
        "announce_v2",
        "announce_family",
        "query",
        "response",
        "drain",
    }, (
        "the registry's subject table changed shape: "
        f"{sorted(registry.SUBJECTS)}"
    )

    jetstream_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and _dotted(node.func) == "self._js.subscribe"
    ]
    assert len(jetstream_calls) == 1, (
        "the registry must hold exactly ONE JetStream subscription -- the "
        f"announce family; found {len(jetstream_calls)}"
    )

    core_subjects = _core_subscribed_subjects(tree, registry.SUBJECTS)
    assert core_subjects == [
        "compute.nodes.drain.v1",
        "compute.nodes.query.v1",
        "mesh.node.announce.v1",
        "mesh.node.announce.v2",
    ], (
        "the registry's core-NATS subscriptions are not the expected four "
        f"(the v1/v2 announce fallback, the query and the drain): {core_subjects}"
    )


def test_the_registry_tears_down_its_jetstream_subscription() -> None:
    """F3: stop() unsubscribes the JetStream subscription too.

    The JetStream subscription was never appended to `_subscriptions`, so
    `stop()` tore down the core-NATS subscriptions and left the durable
    consumer's subscription alive -- it leaked on every restart.
    """
    tree = ast.parse(REGISTRY_PY.read_text(encoding="utf-8"))

    announce = _class_method(tree, "NodeRegistry", "_subscribe_announce")
    bound: Optional[str] = None
    for node in ast.walk(announce):
        if not isinstance(node, ast.Assign):
            continue
        value = node.value
        # `js_sub = await self._js.subscribe(...)` -- the call is wrapped.
        if isinstance(value, ast.Await):
            value = value.value
        if not (
            isinstance(value, ast.Call)
            and _dotted(value.func) == "self._js.subscribe"
        ):
            continue
        assert len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
        bound = node.targets[0].id

    assert bound is not None, (
        "the JetStream subscription result is not bound to a name, so it "
        "cannot be tracked"
    )

    appended = [
        _render(call.args[0])
        for call in ast.walk(announce)
        if isinstance(call, ast.Call)
        and _dotted(call.func) == "self._subscriptions.append"
        and call.args
    ]
    assert bound in appended, (
        f"the JetStream subscription ({bound}) is never appended to "
        f"_subscriptions, so stop() cannot tear it down; appended: {appended}"
    )

    stop = _class_method(tree, "NodeRegistry", "stop")
    stop_loops = [
        _render(node.iter)
        for node in ast.walk(stop)
        if isinstance(node, ast.For)
    ]
    assert "self._subscriptions" in stop_loops, (
        f"stop() does not iterate _subscriptions: {stop_loops}"
    )
    stop_calls = [
        _render(call.func)
        for call in ast.walk(stop)
        if isinstance(call, ast.Call)
    ]
    assert "sub.unsubscribe" in stop_calls, (
        f"stop() does not unsubscribe: {stop_calls}"
    )


def test_every_datetime_that_enters_the_store_is_naive() -> None:
    """F4: the store holds NAIVE datetimes, so its naive clock can be used.

    The store compares `last_heartbeat` against a naive clock, so an AWARE
    datetime entering the store made the comparison raise
    `TypeError: can't subtract offset-naive and offset-aware datetimes` --
    `list_online()` died and the node record could not be evaluated at all.

    An ISO-8601 publisher that sends an offset ("...+05:00") or the "Z" form
    the bootstrap scripts send is exactly how an aware value arrives.
    """
    from datetime import datetime, timedelta, timezone

    registry = importlib.import_module("pmoves.services.node_registry.registry")
    storage = importlib.import_module("pmoves.services.node_registry.storage")

    # An offset is converted to UTC and stripped of its tzinfo.
    offset = registry.timestamp_from_announcement(
        {"timestamp": "2026-10-31T05:44:05+05:00"}
    )
    assert offset.tzinfo is None, "an offset timestamp stayed timezone-aware"
    assert offset == datetime(2026, 10, 31, 0, 44, 5)

    # The "Z" form the bootstrap scripts send is the same case.
    zulu = registry.timestamp_from_announcement({"timestamp": "2026-10-31T00:44:05Z"})
    assert zulu.tzinfo is None, "a Z-suffixed timestamp stayed timezone-aware"
    assert zulu == datetime(2026, 10, 31, 0, 44, 5)

    # A naive timestamp is left exactly as the publisher meant it.
    plain = registry.timestamp_from_announcement({"timestamp": "2026-10-31T00:44:05"})
    assert plain.tzinfo is None
    assert plain == datetime(2026, 10, 31, 0, 44, 5)

    # An epoch is naive too.
    epoch = registry.timestamp_from_announcement({"ts": 1_700_000_000})
    assert epoch.tzinfo is None

    # The helper itself: aware -> naive UTC, naive -> untouched.
    aware = datetime(2026, 10, 31, 5, 44, 5, tzinfo=timezone(timedelta(hours=5)))
    assert storage.naive_utc(aware) == datetime(2026, 10, 31, 0, 44, 5)
    untouched = datetime(2026, 10, 31, 0, 44, 5)
    assert storage.naive_utc(untouched) is untouched

    # The Supabase read path is the other producer: a TIMESTAMPTZ column
    # comes back with an offset.
    parsed = storage.SupabaseNodeStore.__new__(storage.SupabaseNodeStore)
    assert parsed._parse_datetime("2026-10-31T00:44:05+00:00") == datetime(
        2026, 10, 31, 0, 44, 5
    )

    # The HTTP heartbeat endpoint is the OTHER producer of a heartbeat
    # timestamp (the NATS one is gone since F3), so it normalises too.
    api_tree = ast.parse(REGISTRY_API_PY.read_text(encoding="utf-8"))
    heartbeat_timestamps = [
        _render(keyword.value)
        for node in ast.walk(api_tree)
        if isinstance(node, ast.Call)
        and _dotted(node.func) == "NodeHeartbeat"
        for keyword in node.keywords
        if keyword.arg == "timestamp"
    ]
    assert heartbeat_timestamps, "the HTTP heartbeat endpoint builds no timestamp"
    assert all(
        rendered.startswith("naive_utc(") for rendered in heartbeat_timestamps
    ), (
        "the HTTP heartbeat timestamp is not normalised to the store's "
        f"naive convention: {heartbeat_timestamps}"
    )


def test_the_validator_reads_the_real_stream_info_contract() -> None:
    """F5: the validator parses the concatenated `nats stream info -j` capture.

    The validator used to claim it read `nats stream ls -n` -- a table of
    "NAME SUBJECTS RETENTION". The nats CLI does NOT emit that: `stream ls
    -n` prints NAMES ONLY, and `stream ls` has no Subjects column and no
    Retention column. The parser was reading a format the tool never
    produces, so the guard could not have passed against a real server.

    The only output that carries both subjects and retention is
    `nats stream info <NAME> -j` -- ONE JSON object per stream, several of
    them concatenated in the capture. `json.loads` accepts exactly one
    object per document, so the parser has to walk the document with
    `raw_decode`.
    """
    validator = _load_module_by_path(
        "pmoves_validate_streams_f5a", VALIDATE_STREAMS
    )

    capture = "\n".join(
        [
            json.dumps(
                {
                    "config": {
                        "name": "GEOMETRY_CGP",
                        "subjects": ["geometry.>"],
                        "retention": "limits",
                    }
                },
                indent=2,
            ),
            json.dumps(
                {
                    "config": {
                        "name": "COMPUTE",
                        "subjects": ["mesh.node.announce.>", "compute.nodes.>"],
                        "retention": "limits",
                    }
                },
                indent=2,
            ),
        ]
    )

    rows = validator.parse_stream_info_json(capture)
    assert [row.name for row in rows] == ["GEOMETRY_CGP", "COMPUTE"], (
        f"the concatenated capture was not parsed as two streams: {rows}"
    )
    compute = rows[1]
    assert set(compute.subjects) == {"mesh.node.announce.>", "compute.nodes.>"}
    assert compute.retention == "limits"


def _capture_of_every_expected_stream(
    validator: types.ModuleType,
    compute_subjects: Optional[List[str]] = None,
    reverse_compute: bool = False,
) -> str:
    """A concatenated-JSON capture of every expected stream."""
    blocks: List[str] = []
    for row in validator.EXPECTED_STREAMS:
        subjects = list(row.subjects)
        if row.name == "COMPUTE":
            if compute_subjects is not None:
                subjects = list(compute_subjects)
            elif reverse_compute:
                subjects = list(reversed(subjects))
        blocks.append(
            json.dumps(
                {
                    "config": {
                        "name": row.name,
                        "subjects": subjects,
                        "retention": row.retention,
                    }
                },
                indent=2,
            )
        )
    return "\n".join(blocks)


def test_the_validator_matches_a_two_subject_stream_by_set(
    tmp_path: Path, capsys: Any
) -> None:
    """F5: the subject comparison is a SET comparison.

    JetStream does not promise an order for `config.subjects`, and the
    COMPUTE stream carries TWO families. Comparing the joined string --
    which is what the old validator did -- makes the guard fail on a
    stream that is exactly right, and it cannot express "both families"
    at all.

    A wrong subject set must still be REJECTED: a set comparison that
    accepted anything would be as useless as the string comparison.
    """
    validator = _load_module_by_path(
        "pmoves_validate_streams_f5b", VALIDATE_STREAMS
    )

    reversed_capture = tmp_path / "reversed.json"
    reversed_capture.write_text(
        _capture_of_every_expected_stream(validator, reverse_compute=True),
        encoding="utf-8",
    )
    assert validator.main(["validate_streams.py", str(reversed_capture)]) == 0, (
        "the validator rejected a stream that carries exactly the expected "
        "subjects in a different order -- JetStream does not promise an order"
    )

    wrong_capture = tmp_path / "wrong.json"
    wrong_capture.write_text(
        _capture_of_every_expected_stream(
            validator,
            compute_subjects=["mesh.node.announce.>", "compute.nodes.EXTRA.>"],
        ),
        encoding="utf-8",
    )
    assert validator.main(["validate_streams.py", str(wrong_capture)]) == 1, (
        "the validator accepted a COMPUTE stream with the WRONG subject set"
    )
    report = capsys.readouterr().out
    assert "WRONG_SUBJECTS" in report, (
        f"the validator did not name the subject mismatch: {report}"
    )
    assert "COMPUTE" in report, (
        f"the validator did not name the offending stream: {report}"
    )
