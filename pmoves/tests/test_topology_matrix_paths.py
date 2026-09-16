"""The docker matrix must be machine-portable, and the gate must read its shape.

Measured 2026-09-16 on the take-2 lane, against #3088's merged matrix and the
open follow-up #3089:

1. #3088 committed a matrix whose every ``canonical_path`` and ``paths`` entry
   was an absolute Windows path (``C:\\Users\\<operator>\\...``). The operator's
   checkout location leaked into a public tracked file — the exact failure
   class ``feedback_no_topology_in_commits`` exists to prevent.
2. ``_discover_real_services`` still emitted ``str(relative_to(...))``, which on
   Windows is backslash-joined. #3089's regenerated matrix carried 237
   backslash lines: regen on Linux and regen on Windows produced different
   bytes for the same tree, so every cross-OS regen is whole-file churn.
3. ``check_known_roads._matrix_owns_path`` read ``svc["paths"]`` as a dict, a
   shape the builder has never emitted (it emits ``overlays: [...]`` lists).
   Source A matching was dead code: the gate could only ever pass through the
   four hand-curated Source C ``guard_paths``. A precise-set matcher whose set
   is never consulted is an allowlist of four names.

These tests pin all three: the builder's output is invariant across separator
conventions, the consumer finds owners through the shape the builder actually
emits, and the committed matrix in this repo stays leak-free.
"""

from __future__ import annotations

import importlib.util
import inspect
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
TOPOLOGY_DIR = REPO_ROOT / "pmoves" / "tools" / "topology"
COMMITTED_MATRIX = REPO_ROOT / "pmoves" / "configs" / "topology" / "docker_matrix.yaml"


def _load_tool(name: str):
    spec = importlib.util.spec_from_file_location(name, TOPOLOGY_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def builder():
    return _load_tool("build_docker_matrix")


@pytest.fixture(scope="module")
def checker():
    return _load_tool("check_known_roads")


FIXTURE_SERVICES = {
    "alpha-worker": "pmoves/services/alpha-worker/Dockerfile",
    "beta-gateway": "pmoves/services/beta_gateway/Dockerfile.pmoves",
    "gamma-agent": "pmoves/integrations/gamma-agent/Dockerfile",
}


@pytest.fixture()
def fake_repo(tmp_path: Path) -> Path:
    root = tmp_path / "checkout-anywhere"
    for rel in FIXTURE_SERVICES.values():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("FROM scratch\n", encoding="utf-8")
    # beta_gateway exists under BOTH roots -> exercises the roots merge
    dup = root / "pmoves" / "integrations" / "beta_gateway"
    dup.mkdir(parents=True, exist_ok=True)
    (dup / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")

    compose = root / "pmoves" / "docker-compose.core.yml"
    compose.parent.mkdir(parents=True, exist_ok=True)
    compose.write_text(
        "services:\n"
        "  alpha-worker:\n"
        "    image: x\n"
        "  beta_gateway:\n"
        "    image: x\n",
        encoding="utf-8",
    )
    apps = root / "pmoves" / "docker-compose.apps.yml"
    apps.write_text(
        "services:\n"
        "  gamma-agent:\n"
        "    image: x\n",
        encoding="utf-8",
    )

    sub = root / "pmoves" / "configs" / "topology" / "submodule_services.yaml"
    sub.parent.mkdir(parents=True, exist_ok=True)
    sub.write_text(
        "- name: delta-sub\n"
        "  compose_keys: [delta-sub]\n"
        "  source_repo: PMOVES-Delta\n"
        "  source_path: Dockerfile\n"
        "  compose_overlays:\n"
        "    - pmoves/docker-compose.apps.yml\n"
        "  guard_paths:\n"
        "    - PMOVES-Delta/Dockerfile\n",
        encoding="utf-8",
    )
    return root


def _emit_matrix(builder, root: Path) -> str:
    real_services, overlays = builder._build(root)
    params = inspect.signature(builder._emit).parameters
    if "repo_root" in params:
        return builder._emit(real_services, overlays, root)
    return builder._emit(real_services, overlays)


def _build_matrix(builder, root: Path) -> dict:
    return yaml.safe_load(_emit_matrix(builder, root))


# --- builder: portability invariants ---------------------------------------


def test_matrix_has_no_absolute_or_backslash_paths(builder, fake_repo):
    matrix = _build_matrix(builder, fake_repo)
    flat = yaml.safe_dump(matrix)
    assert "\\" not in flat, "backslash separator leaked into the matrix"
    for token in (":/", "Users", str(fake_repo).split("\\")[0] if "\\" in str(fake_repo) else "C:"):
        assert token not in flat, f"machine-local path fragment leaked: {token!r}"


def test_matrix_directory_dockerfile_roots_are_posix(builder, fake_repo):
    matrix = _build_matrix(builder, fake_repo)
    by_name = {s["name"]: s for s in matrix["services"]}
    for name, rel in FIXTURE_SERVICES.items():
        entry = by_name[name]
        assert entry["directory"] == rel.rsplit("/", 1)[0]
        assert entry["dockerfile"] == rel
    assert all("/" in r or r == "pmoves/services" for s in matrix["services"] for r in s["roots"])


def test_service_in_both_roots_has_no_duplicate_roots(builder, fake_repo):
    matrix = _build_matrix(builder, fake_repo)
    beta = next(s for s in matrix["services"] if s["name"] == "beta-gateway")
    assert sorted(beta["roots"]) == ["pmoves/integrations", "pmoves/services"]


def test_regenerate_is_deterministic(builder, fake_repo):
    assert _emit_matrix(builder, fake_repo) == _emit_matrix(builder, fake_repo)


# --- consumer: reads the emitted shape --------------------------------------


def test_gate_finds_owner_for_compose_path(builder, checker, fake_repo):
    matrix = _build_matrix(builder, fake_repo)
    owners = checker._matrix_owns_path(matrix, "pmoves/docker-compose.core.yml")
    # regression for the dead-shape bug: this list was empty when the
    # consumer read svc["paths"] instead of svc["overlays"][*]["paths"]
    assert "alpha-worker" in owners
    assert "beta-gateway" in owners


def test_gate_matches_windows_style_input(builder, checker, fake_repo):
    matrix = _build_matrix(builder, fake_repo)
    assert checker._matrix_owns_path(matrix, "pmoves\\docker-compose.core.yml")


def test_gate_finds_owner_via_guard_paths(builder, checker, fake_repo):
    matrix = _build_matrix(builder, fake_repo)
    assert checker._matrix_owns_path(matrix, "PMOVES-Delta/Dockerfile") == ["delta-sub"]


def test_gate_rejects_unknown_path(builder, checker, fake_repo):
    matrix = _build_matrix(builder, fake_repo)
    assert checker._matrix_owns_path(matrix, "pmoves/services/phantom/Dockerfile") == []


def test_gate_relativizes_absolute_paths(builder, checker, fake_repo, monkeypatch):
    matrix = _build_matrix(builder, fake_repo)
    monkeypatch.setattr(checker, "REPO_ROOT", fake_repo)
    absolute = str(fake_repo / "pmoves" / "docker-compose.core.yml")
    assert "alpha-worker" in checker._matrix_owns_path(matrix, absolute)


@pytest.mark.parametrize("reason,expected", [
    ("pr:3089", True),
    ("issue:2974", True),
    ("handoff:notebook-mcp-build-2026-09-02.md", True),
    ("session:abcd1234efgh", True),
    ("lifecycle:nats-hub-cutover", True),
    ("I want to add a port", False),
    ("pr:three-oh-eight-nine", False),
])
def test_reason_reference_shapes(checker, reason, expected):
    assert checker._reason_has_valid_reference(reason) is expected


# --- ratchet: the committed matrix stays clean ------------------------------


def test_committed_matrix_is_portable():
    text = COMMITTED_MATRIX.read_text(encoding="utf-8")
    assert "Users" not in text, "operator-home path leaked into the committed matrix"
    assert ":\\\\" not in text and "\\" not in text, "backslash path in committed matrix"
    matrix = yaml.safe_load(text)
    for overlay in matrix.get("overlays", []):
        assert "/" in overlay["canonical_path"]


def test_committed_matrix_regenerates_byte_identical(builder, tmp_path):
    out = tmp_path / "regen.yaml"
    # drive the builder through its CLI surface, not internals, so the
    # committed matrix and the regen path can never drift apart
    import subprocess

    proc = subprocess.run(
        [sys.executable, str(TOPOLOGY_DIR / "build_docker_matrix.py"), "--out", str(out)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert out.read_text(encoding="utf-8") == COMMITTED_MATRIX.read_text(encoding="utf-8"), (
        "committed docker_matrix.yaml is stale — regenerate with "
        "`python pmoves/tools/topology/build_docker_matrix.py`"
    )
