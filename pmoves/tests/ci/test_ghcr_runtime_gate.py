"""Static guards for the GHCR matrix runtime gate.

Context: `ghcr.io/powerfulmoves/pmoves-yt:pmoves-latest` built green for five
months and could not start — its entrypoint raised IndexError at import. The
matrix had no step that ever ran a container, so "build succeeded" was the only
signal. See pmoves/docs/services/pmoves-yt/RUNBOOK.md section 1.3.

These tests do not run Docker. They assert the *wiring* that makes the runtime
gate exist and stay wired:

  - pmoves-yt builds from the PMOVES.YT fork, not the shim directory
  - pmoves-yt declares the verify_* keys, so its gate cannot be dropped silently
  - the workflow actually invokes the gate script, before attestation/signing
  - the gate script itself fails on bad input (it is not a no-op)
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[3]
_MATRIX = _REPO_ROOT / ".github" / "workflows" / "integrations-ghcr.matrix.json"
_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "integrations-ghcr.yml"
_GATE = _REPO_ROOT / ".github" / "scripts" / "verify-image-starts.sh"

_PMOVES_AI_URL = "https://github.com/POWERFULMOVES/PMOVES.AI.git"


def _entries() -> list[dict]:
    return json.loads(_MATRIX.read_text(encoding="utf-8"))


def _entry(name: str) -> dict:
    match = next((e for e in _entries() if e.get("name") == name), None)
    assert match is not None, f"no '{name}' entry in {_MATRIX.name}"
    return match


def _publish_steps() -> list[dict]:
    doc = yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))
    return doc["jobs"]["build-publish"]["steps"]


# --------------------------------------------------------------------------
# The image is built from the fork, not the shim
# --------------------------------------------------------------------------

def test_pmoves_yt_builds_from_the_fork_not_the_shim() -> None:
    """The shim at pmoves/services/pmoves-yt cannot produce a runnable image.

    Its yt.py walks up to a repo-root submodule that is not in that build
    context, so a `COPY . .` image has nothing to import. Publishing must use
    the fork's own context and Dockerfile — the same recipe `up-yt` builds.
    """
    entry = _entry("pmoves-yt")
    assert entry["context"] == "PMOVES.YT", (
        "pmoves-yt must build from the PMOVES.YT submodule; "
        f"got context={entry['context']!r}"
    )
    assert entry["dockerfile"] == "PMOVES.YT/pmoves_yt_service/Dockerfile"


def test_pmoves_yt_matches_the_compose_build_recipe() -> None:
    """Published and local-build paths must not drift into different images."""
    compose = yaml.safe_load(
        (_REPO_ROOT / "pmoves" / "docker-compose.yml").read_text(encoding="utf-8")
    )
    build = compose["services"]["pmoves-yt"]["build"]
    # compose paths are relative to pmoves/; the matrix's are repo-root relative
    assert build["context"] == "../PMOVES.YT"
    assert build["dockerfile"] == "pmoves_yt_service/Dockerfile"

    entry = _entry("pmoves-yt")
    assert entry["dockerfile"] == f"{entry['context']}/{build['dockerfile']}"


def _submodule_paths() -> set[str]:
    gitmodules = _REPO_ROOT / ".gitmodules"
    if not gitmodules.is_file():
        return set()
    return {
        line.split("=", 1)[1].strip()
        for line in gitmodules.read_text(encoding="utf-8").splitlines()
        if line.strip().startswith("path")
    }


@pytest.mark.parametrize(
    "entry", [e for e in _entries() if e.get("git_url") == _PMOVES_AI_URL],
    ids=lambda e: e["name"],
)
def test_in_repo_dockerfiles_exist(entry: dict) -> None:
    """A repointed context is worthless if the Dockerfile path is wrong.

    Only entries sourced from this repo can be checked here; entries that clone
    another repo have their Dockerfile in that repo.

    A path inside an uninitialized submodule is legitimately absent — a plain
    checkout or worktree has only the gitlink. We skip those rather than assert
    a falsehood, but we still require that the absence be explained by a
    declared submodule, so a genuinely wrong path is not excused.
    """
    declared = entry["dockerfile"]
    path = _REPO_ROOT / declared
    if path.is_file():
        return

    owner = next(
        (sm for sm in _submodule_paths() if declared.startswith(f"{sm}/")), None
    )
    assert owner is not None, f"{entry['name']}: missing {declared}"
    assert not any((_REPO_ROOT / owner).iterdir()), (
        f"{entry['name']}: submodule {owner} is checked out but does not "
        f"contain {declared}"
    )
    pytest.skip(f"{owner} submodule not initialized in this checkout")


# --------------------------------------------------------------------------
# The gate exists, is wired, and is declared for pmoves-yt
# --------------------------------------------------------------------------

def test_gate_script_exists_and_is_executable() -> None:
    assert _GATE.is_file(), f"missing {_GATE}"
    assert _GATE.stat().st_mode & stat.S_IXUSR, f"{_GATE.name} is not executable"


def test_pmoves_yt_declares_a_runtime_gate() -> None:
    """Without these keys the gate no-ops with a warning and the image ships
    unverified — which is exactly the state this change exists to end."""
    entry = _entry("pmoves-yt")
    assert entry.get("verify_port"), "pmoves-yt must declare verify_port"
    assert entry.get("verify_health_path"), (
        "pmoves-yt must declare verify_health_path"
    )
    assert entry["verify_port"] == "8077"
    assert entry["verify_health_path"] == "/healthz"


def test_workflow_invokes_the_gate() -> None:
    steps = _publish_steps()
    invoking = [
        s for s in steps if "verify-image-starts.sh" in (s.get("run") or "")
    ]
    assert invoking, (
        "build-publish has no step invoking .github/scripts/verify-image-starts.sh"
    )


def test_gate_runs_before_attestation_and_signing() -> None:
    """A digest that cannot start must not receive SLSA provenance or a cosign
    signature. A failed step skips the rest of the job, so ordering is the
    mechanism."""
    names = [s.get("name") or "" for s in _publish_steps()]
    runs = [s.get("run") or "" for s in _publish_steps()]

    gate_idx = next(i for i, r in enumerate(runs) if "verify-image-starts.sh" in r)
    build_idx = next(i for i, n in enumerate(names) if n.startswith("Build and push"))
    attest_idx = next(i for i, n in enumerate(names) if "Attest build provenance" in n)
    cosign_idx = next(i for i, n in enumerate(names) if n.startswith("Cosign sign"))

    assert build_idx < gate_idx < attest_idx, (
        f"gate at {gate_idx} must sit between build ({build_idx}) "
        f"and attestation ({attest_idx})"
    )
    assert gate_idx < cosign_idx


def test_gate_verifies_by_digest_not_by_tag() -> None:
    """':pmoves-latest' is mutable; a concurrent leg can move it between push
    and check. Verifying by tag would re-introduce the stale-artifact defect."""
    run = next(
        s["run"] for s in _publish_steps()
        if "verify-image-starts.sh" in (s.get("run") or "")
    )
    assert "steps.build.outputs.digest" in json.dumps(
        [s for s in _publish_steps() if "verify-image-starts.sh" in (s.get("run") or "")]
    ), "gate step must consume the build step's digest output"
    assert "@${BUILD_DIGEST}" in run, "gate must be handed a digest ref"


# --------------------------------------------------------------------------
# Submodule materialization
# --------------------------------------------------------------------------

def test_source_prep_can_materialize_non_integrations_submodules() -> None:
    """The old filter only initialized pmoves/integrations/*, so a repo-root
    submodule context (PMOVES.YT) arrived empty."""
    text = _WORKFLOW.read_text(encoding="utf-8")
    assert "| grep '^pmoves/integrations/'" not in text, (
        "source prep still hard-filters to pmoves/integrations/ and cannot "
        "materialize a repo-root submodule build context"
    )
    assert text.count("cfg_context=") == 2, (
        "both build jobs must resolve the entry's context for submodule selection"
    )


def test_source_prep_asserts_the_dockerfile_landed() -> None:
    text = _WORKFLOW.read_text(encoding="utf-8")
    assert text.count('if [ ! -f "integration-src/${cfg_dockerfile}" ]; then') == 2


# --------------------------------------------------------------------------
# The gate is not a no-op: it fails on bad input
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "argv, env",
    [
        ([], {"VERIFY_PORT": "8077", "VERIFY_HEALTH_PATH": "/healthz"}),
        (["img:tag"], {}),
        (["img:tag"], {"VERIFY_PORT": "8077"}),
        (["img:tag"], {"VERIFY_HEALTH_PATH": "/healthz"}),
    ],
    ids=["no-image-ref", "no-verify-env", "no-health-path", "no-port"],
)
def test_gate_rejects_bad_invocation(argv: list[str], env: dict) -> None:
    """Negative control at the argument layer — no Docker required.

    Requires the script to exist first: `bash <missing-file>` also exits
    non-zero, so without this guard the test would pass vacuously on a tree
    where the gate had been deleted.
    """
    assert _GATE.is_file(), f"missing {_GATE} — this test would pass vacuously"
    result = subprocess.run(
        ["bash", str(_GATE), *argv],
        capture_output=True,
        text=True,
        env={"PATH": os.environ.get("PATH", ""), **env},
    )
    assert result.returncode != 0, (
        f"gate exited 0 on a bad invocation: argv={argv} env={env}"
    )
    assert "usage:" in result.stderr or "are required" in result.stderr, (
        f"gate failed for the wrong reason: {result.stderr!r}"
    )
