# pmoves/tools/tests/test_image_staleness_ratchet.py
"""Tests for the image-staleness ratchet gate.

The ratchet is the fleet's "can these images stay fresh?" number. It must:
  1. PASS on the real pmoves/images.yaml + .github/workflows/build-images.yml
     (after the schedule: trigger landed).
  2. REPORT a manual-only workflow (the 65-day flute-gateway bug).
  3. REPORT a bogus dockerfile path.
  4. REPORT a matrix entry missing a builder-required field.
  5. Say UNDECIDED (NOT DRIFTED) for a submodule-backed entry whose
     submodule is not checked out here -- "I could not check" and "it is
     broken" are different answers, and the gate must not go red on a
     CI runner that has no submodules.
  6. NOT mistake the buildx `--push` flag (`push: true` under `with:`) for
     a workflow trigger.

Hermetic: no network, no docker, no gh, no registry API. Runs on Linux and
Windows (no POSIX-only path handling, no shell).
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

RATCHET = (
    Path(__file__).resolve().parents[1] / "image_staleness_ratchet.py"
)
REPO_ROOT = Path(__file__).resolve().parents[3]
PYTHON = sys.executable


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def _run(
    images: Path,
    workflow: Path,
    gitmodules: Path,
    repo_root: Path,
) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            PYTHON,
            str(RATCHET),
            "--images", str(images),
            "--workflow", str(workflow),
            "--gitmodules", str(gitmodules),
            "--repo-root", str(repo_root),
            "--json",
        ],
        capture_output=True, text=True,
    )


def _tree(
    tmp_path: Path,
    *,
    images_yaml: str,
    workflow_yaml: str,
    gitmodules: str = "",
    files: dict | None = None,
) -> tuple[Path, Path, Path, Path]:
    """Materialise a mini repo tree and return (images, workflow, gitmodules, root)."""
    root = tmp_path / "repo"
    (root / ".github" / "workflows").mkdir(parents=True, exist_ok=True)
    images_path = root / "pmoves" / "images.yaml"
    images_path.parent.mkdir(parents=True, exist_ok=True)
    images_path.write_text(images_yaml, encoding="utf-8")
    workflow_path = root / ".github" / "workflows" / "build-images.yml"
    workflow_path.write_text(workflow_yaml, encoding="utf-8")
    gitmodules_path = root / ".gitmodules"
    gitmodules_path.write_text(gitmodules, encoding="utf-8")
    for rel, body in (files or {}).items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
    return images_path, workflow_path, gitmodules_path, root


GOOD_WORKFLOW = """\
name: build-images-matrix

on:
  workflow_dispatch:
  schedule:
    - cron: '23 4 * * *'

jobs:
  build:
    name: Image Build
    runs-on: [self-hosted, Linux, X64]
    steps:
      - uses: docker/build-push-action@v7
        with:
          context: ${{ matrix.context }}
          file: ${{ matrix.dockerfile }}
          push: true
"""

MANUAL_ONLY_WORKFLOW = """\
name: build-images-matrix

on:
  workflow_dispatch:

jobs:
  build:
    name: Manual Image Build
    runs-on: [self-hosted, Linux, X64]
    steps:
      - uses: docker/build-push-action@v7
        with:
          push: true
"""

ONE_IMAGE = """\
images:
  - name: pmoves-flute-gateway
    context: pmoves
    dockerfile: services/flute-gateway/Dockerfile
    image: ghcr.io/powerfulmoves/pmoves-flute-gateway
"""

DOCKERFILE_BODY = "FROM scratch\n"


def _claims(out: dict, image: str, probe: str) -> dict:
    for claim in out["claims"]:
        if claim["image"] == image and claim["probe"] == probe:
            return claim
    raise AssertionError(f"no claim for {image}/{probe}: {out['claims']}")


# --------------------------------------------------------------------------
# the real tree
# --------------------------------------------------------------------------
def test_real_matrix_and_workflow_pass():
    """The REAL pmoves/images.yaml + REAL build-images.yml pass the ratchet."""
    r = subprocess.run(
        [PYTHON, str(RATCHET), "--json"], capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    out = json.loads(r.stdout)
    assert out["total"] == 30, out["total"]
    assert out["counts"]["DRIFTED"] == 0, out["problems"]
    assert out["problems"] == []
    # Every image must have a non-manual rebuild path, or the fleet can
    # silently go stale again -- that is the whole point of the ratchet.
    for claim in out["claims"]:
        if claim["probe"] == "build_path":
            assert claim["verdict"] == "VERIFIED", claim
    # And every image must carry the fields the builder consumes.
    for claim in out["claims"]:
        if claim["probe"] == "matrix_fields":
            assert claim["verdict"] == "VERIFIED", claim


def test_real_workflow_has_a_non_manual_trigger():
    """The real build-images.yml declares `schedule:` -- the direct fix."""
    sys.path.insert(0, str(RATCHET.parent))
    try:
        import image_staleness_ratchet as ratchet
    finally:
        sys.path.pop(0)

    text = (
        REPO_ROOT / ".github" / "workflows" / "build-images.yml"
    ).read_text(encoding="utf-8")
    triggers, err = ratchet.parse_workflow_triggers(text)
    assert err is None, err
    assert "schedule" in triggers, triggers
    assert "workflow_dispatch" in triggers, triggers


def test_real_matrix_parses_to_thirty_images():
    sys.path.insert(0, str(RATCHET.parent))
    try:
        import image_staleness_ratchet as ratchet
    finally:
        sys.path.pop(0)

    text = (REPO_ROOT / "pmoves" / "images.yaml").read_text(encoding="utf-8")
    images = ratchet.parse_images_matrix(text)
    assert len(images) == 30, len(images)
    names = {i["name"] for i in images}
    assert "pmoves-flute-gateway" in names
    assert "pmoves-agent-zero" in names


# --------------------------------------------------------------------------
# NEGATIVE CONTROL: the ratchet must be able to fail
# --------------------------------------------------------------------------
def test_manual_only_workflow_is_drifted(tmp_path):
    """A workflow with only `workflow_dispatch:` cannot keep the fleet fresh."""
    images, workflow, gitmodules, root = _tree(
        tmp_path,
        images_yaml=ONE_IMAGE,
        workflow_yaml=MANUAL_ONLY_WORKFLOW,
        files={"pmoves/services/flute-gateway/Dockerfile": DOCKERFILE_BODY},
    )
    r = _run(images, workflow, gitmodules, root)
    assert r.returncode == 1, r.stdout
    out = json.loads(r.stdout)
    assert out["triggers"] == ["workflow_dispatch"], out["triggers"]
    claim = _claims(out, "pmoves-flute-gateway", "build_path")
    assert claim["verdict"] == "DRIFTED", claim
    assert "workflow_dispatch" in claim["evidence"], claim
    assert any("build_path" in p for p in out["problems"]), out["problems"]


def test_bogus_dockerfile_path_is_drifted(tmp_path):
    """A dockerfile path that does not exist means the image cannot be rebuilt."""
    images, workflow, gitmodules, root = _tree(
        tmp_path,
        images_yaml=ONE_IMAGE,
        workflow_yaml=GOOD_WORKFLOW,
        # NOTE: no Dockerfile written -- the path is bogus on purpose.
    )
    r = _run(images, workflow, gitmodules, root)
    assert r.returncode == 1, r.stdout
    out = json.loads(r.stdout)
    claim = _claims(out, "pmoves-flute-gateway", "build_inputs")
    assert claim["verdict"] == "DRIFTED", claim
    assert "build input missing" in claim["evidence"], claim


def test_missing_builder_field_is_drifted(tmp_path):
    """An entry without `image` is unbuildable no matter what is on disk."""
    bad = """\
images:
  - name: pmoves-flute-gateway
    context: pmoves
    dockerfile: services/flute-gateway/Dockerfile
"""
    images, workflow, gitmodules, root = _tree(
        tmp_path,
        images_yaml=bad,
        workflow_yaml=GOOD_WORKFLOW,
        files={"pmoves/services/flute-gateway/Dockerfile": DOCKERFILE_BODY},
    )
    r = _run(images, workflow, gitmodules, root)
    assert r.returncode == 1, r.stdout
    out = json.loads(r.stdout)
    claim = _claims(out, "pmoves-flute-gateway", "matrix_fields")
    assert claim["verdict"] == "DRIFTED", claim
    assert "image" in claim["evidence"], claim


# --------------------------------------------------------------------------
# UNDECIDED vs DRIFTED: the distinction the gate depends on
# --------------------------------------------------------------------------
SUBMODULE_IMAGE = """\
images:
  - name: pmoves-agent-zero
    repo: PMOVES-Agent-Zero
    ref: heads/PMOVES.AI-Edition-Hardened
    context: .
    dockerfile: DockerfileLocal
    image: ghcr.io/powerfulmoves/pmoves-agent-zero
"""

GITMODULES = """\
[submodule "PMOVES-Agent-Zero"]
\tpath = PMOVES-Agent-Zero
\turl = https://github.com/POWERFULMOVES/PMOVES-Agent-Zero.git
"""


def test_uninitialised_submodule_is_undecided_not_drifted(tmp_path):
    """A submodule that is not checked out here is UNDECIDED, and the gate
    stays green -- a CI runner without submodules must not go permanently red."""
    images, workflow, gitmodules, root = _tree(
        tmp_path,
        images_yaml=SUBMODULE_IMAGE,
        workflow_yaml=GOOD_WORKFLOW,
        gitmodules=GITMODULES,
        # NOTE: PMOVES-Agent-Zero/ is deliberately absent (not checked out).
    )
    r = _run(images, workflow, gitmodules, root)
    assert r.returncode == 0, r.stdout + r.stderr
    out = json.loads(r.stdout)
    claim = _claims(out, "pmoves-agent-zero", "build_inputs")
    assert claim["verdict"] == "UNDECIDED", claim
    assert claim["verdict"] != "DRIFTED"
    assert "not checked out" in claim["evidence"], claim
    assert out["counts"]["DRIFTED"] == 0
    assert out["counts"]["UNDECIDED"] == 1
    assert out["problems"] == []


def test_checked_out_submodule_with_missing_dockerfile_is_drifted(tmp_path):
    """Same submodule, now checked out, and the dockerfile really is gone:
    THAT is DRIFTED. The UNDECIDED verdict above is not a blanket excuse."""
    images, workflow, gitmodules, root = _tree(
        tmp_path,
        images_yaml=SUBMODULE_IMAGE,
        workflow_yaml=GOOD_WORKFLOW,
        gitmodules=GITMODULES,
        # The submodule directory exists with content (checked out) but
        # holds no DockerfileLocal.
        files={"PMOVES-Agent-Zero/README.md": "submodule content\n"},
    )
    r = _run(images, workflow, gitmodules, root)
    assert r.returncode == 1, r.stdout
    out = json.loads(r.stdout)
    claim = _claims(out, "pmoves-agent-zero", "build_inputs")
    assert claim["verdict"] == "DRIFTED", claim
    assert out["counts"]["UNDECIDED"] == 0


def test_non_submodule_missing_path_is_drifted(tmp_path):
    """A `repo:` that is NOT a declared submodule is genuinely absent -> DRIFTED."""
    images, workflow, gitmodules, root = _tree(
        tmp_path,
        images_yaml=SUBMODULE_IMAGE,
        workflow_yaml=GOOD_WORKFLOW,
        gitmodules="",  # PMOVES-Agent-Zero is not a declared submodule here
    )
    r = _run(images, workflow, gitmodules, root)
    assert r.returncode == 1, r.stdout
    out = json.loads(r.stdout)
    claim = _claims(out, "pmoves-agent-zero", "build_inputs")
    assert claim["verdict"] == "DRIFTED", claim


# --------------------------------------------------------------------------
# trigger parsing
# --------------------------------------------------------------------------
def test_buildx_push_flag_is_not_a_workflow_trigger(tmp_path):
    """`push: true` under `with:` is the buildx --push flag, not a trigger."""
    workflow_only_push_flag = """\
name: build-images-matrix

on:
  workflow_dispatch:

jobs:
  build:
    runs-on: ubuntu-24.04
    steps:
      - uses: docker/build-push-action@v7
        with:
          push: true
"""
    images, workflow, gitmodules, root = _tree(
        tmp_path,
        images_yaml=ONE_IMAGE,
        workflow_yaml=workflow_only_push_flag,
        files={"pmoves/services/flute-gateway/Dockerfile": DOCKERFILE_BODY},
    )
    r = _run(images, workflow, gitmodules, root)
    out = json.loads(r.stdout)
    assert "push" not in out["triggers"], out["triggers"]
    claim = _claims(out, "pmoves-flute-gateway", "build_path")
    assert claim["verdict"] == "DRIFTED", claim


def test_good_tree_is_all_verified(tmp_path):
    """Positive control: a correct tree verifies every claim."""
    images, workflow, gitmodules, root = _tree(
        tmp_path,
        images_yaml=ONE_IMAGE,
        workflow_yaml=GOOD_WORKFLOW,
        files={"pmoves/services/flute-gateway/Dockerfile": DOCKERFILE_BODY},
    )
    r = _run(images, workflow, gitmodules, root)
    assert r.returncode == 0, r.stdout + r.stderr
    out = json.loads(r.stdout)
    assert out["total"] == 1
    assert out["counts"] == {"VERIFIED": 1, "DRIFTED": 0, "UNDECIDED": 0}
    for claim in out["claims"]:
        assert claim["verdict"] == "VERIFIED", claim
        assert claim["evidence"], claim


def test_missing_matrix_file_returns_2():
    r = subprocess.run(
        [PYTHON, str(RATCHET), "--images", "/nonexistent/images.yaml"],
        capture_output=True, text=True,
    )
    assert r.returncode == 2
    assert "not found" in r.stderr.lower()


# --------------------------------------------------------------------------
# zero-network guarantee
# --------------------------------------------------------------------------
def test_tool_imports_no_network_modules():
    """The ratchet must stay zero-network: no urllib/requests/socket/http."""
    source = RATCHET.read_text(encoding="utf-8")
    for banned in ("import urllib", "import requests", "import socket",
                   "import http", "from urllib", "from requests"):
        assert banned not in source, f"{banned} found in the ratchet"


def test_tool_uses_stdlib_only():
    """No third-party imports (PyYAML especially) -- the gate runs anywhere."""
    source = RATCHET.read_text(encoding="utf-8")
    assert "import yaml" not in source
    assert "from yaml" not in source


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
