# pmoves/tools/tests/test_fork_registry_ratchet.py
"""Tests for the fork-registry ratchet gate.

The ratchet is the operator's "fork coverage" number. It must:
  1. Pass when every fork has sync (bool) + reason (non-empty str).
  2. Fail when any fork is missing the decision.
  3. Fail when any fork uses the deprecated `skip` field.
  4. Treat `_schema`, `_doc`, `_generated`, `_source`, `_excluded`,
     and any future underscore-prefixed meta keys as NOT forks.
  5. Fail when a registry fork with `sync: true` is absent from the
     fork-sync workflow's FORKS block or from the GitHub App token scope.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

RATCHET = (
    Path(__file__).resolve().parents[1] / "fork_registry_ratchet.py"
)
PYTHON = sys.executable

REPO_ROOT = Path(__file__).resolve().parents[3]
REAL_REGISTRY = REPO_ROOT / "pmoves" / "config" / "fork_registry.json"
REAL_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "fork-sync.yml"

# The two pipecat forks the 2026-10-30 provenance audit found unregistered
# entirely (gap 2): no registry entry, no workflow entry, no GH App scope
# and no .gitmodules submodule.
NEW_PIECAT_FORKS = {
    "Pmoves-pipecat-client-web-transports": "pipecat-ai/pipecat-client-web-transports",
    "Pmoves-pipecat-mcp-server": "pipecat-ai/pipecat-mcp-server",
}


def _run_on(payload: dict) -> subprocess.CompletedProcess:
    """Run the ratchet on an in-memory registry and return the result."""
    import tempfile
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as f:
        json.dump(payload, f)
        path = f.name
    try:
        return subprocess.run(
            [PYTHON, str(RATCHET), "--registry", path, "--json"],
            capture_output=True, text=True,
        )
    finally:
        Path(path).unlink(missing_ok=True)


def _registry(forks: dict, extra: dict | None = None) -> dict:
    return {
        "forks": forks,
        **(extra or {}),
    }


def test_all_decided_passes():
    payload = _registry({
        "F-A": {"upstream": "u/a", "sync": True, "reason": "auto-sync on cron"},
        "F-B": {"upstream": "u/b", "sync": False, "reason": "frozen snapshot"},
    })
    r = _run_on(payload)
    assert r.returncode == 0, r.stdout + r.stderr
    out = json.loads(r.stdout)
    assert out["decided"] == 2
    assert out["total"] == 2
    assert out["problems"] == []


def test_missing_sync_fails():
    payload = _registry({
        "F-A": {"upstream": "u/a"},  # no sync
    })
    r = _run_on(payload)
    assert r.returncode == 1, r.stdout
    out = json.loads(r.stdout)
    assert out["decided"] == 0
    assert any("missing 'sync'" in p for p in out["problems"])


def test_missing_reason_fails():
    payload = _registry({
        "F-A": {"upstream": "u/a", "sync": True},  # no reason
    })
    r = _run_on(payload)
    assert r.returncode == 1
    out = json.loads(r.stdout)
    assert any("missing non-empty 'reason'" in p for p in out["problems"])


def test_empty_reason_fails():
    payload = _registry({
        "F-A": {"upstream": "u/a", "sync": True, "reason": "   "},
    })
    r = _run_on(payload)
    assert r.returncode == 1
    out = json.loads(r.stdout)
    assert any("missing non-empty 'reason'" in p for p in out["problems"])


def test_deprecated_skip_field_fails():
    payload = _registry({
        "F-A": {"upstream": "u/a", "skip": "synced"},
    })
    r = _run_on(payload)
    assert r.returncode == 1
    out = json.loads(r.stdout)
    assert any("deprecated 'skip'" in p for p in out["problems"])
    # The deprecated `skip` field does NOT count as decided, even
    # if the value is truthy — operators must explicitly migrate.
    assert out["decided"] == 0


def test_non_bool_sync_fails():
    payload = _registry({
        "F-A": {"upstream": "u/a", "sync": "yes", "reason": "r"},
    })
    r = _run_on(payload)
    assert r.returncode == 1
    out = json.loads(r.stdout)
    assert any("'sync' must be bool" in p for p in out["problems"])


def test_meta_keys_ignored():
    """Underscore-prefixed top-level keys are meta, not forks."""
    payload = _registry(
        {
            "F-A": {"upstream": "u/a", "sync": True, "reason": "r"},
        },
        extra={
            "_doc": "docs",
            "_generated": "2026-08-03",
            "_source": "src",
            "_schema": {"x": "y"},
            "_excluded": {"Pmoves-cipher": "no common ancestor"},
        },
    )
    r = _run_on(payload)
    assert r.returncode == 0, r.stdout
    out = json.loads(r.stdout)
    assert out["total"] == 1, f"meta keys must not be counted as forks: {out}"
    assert out["decided"] == 1


def test_missing_registry_file_returns_2():
    r = subprocess.run(
        [PYTHON, str(RATCHET), "--registry", "/nonexistent/path/registry.json"],
        capture_output=True, text=True,
    )
    assert r.returncode == 2
    assert "not found" in r.stderr.lower()


# ---------------------------------------------------------------------------
# Rule 5 — registry -> workflow coverage.
#
# The registry and .github/workflows/fork-sync.yml are two INDEPENDENT
# hand-maintained lists. Before this cross-check existed, a `sync: true`
# could exist with NO mechanism behind it: the ratchet reported the fork as
# "decided" and exited 0 while the workflow never touched it. The pipecat
# fork provenance audit measured six such forks (gap 1 of
# pmoves/docs/services/PIPECAT_FORK_PROVENANCE_AUDIT_2026-10-30.md).
#
# Every assertion below is POSITIVE: it states that a named fork IS present.
# A statement about absence ("nothing is missing") cannot say no.
# ---------------------------------------------------------------------------


def _read_real_registry() -> dict:
    return json.loads(REAL_REGISTRY.read_text(encoding="utf-8"))


def _workflow_scope_names(workflow_text: str) -> set[str]:
    """Repo names in the GH App `repositories:` scope block."""
    names: set[str] = set()
    in_block = False
    key_indent = 0
    for raw in workflow_text.splitlines():
        stripped = raw.strip()
        if not in_block:
            if stripped.startswith("repositories:"):
                in_block = True
                key_indent = len(raw) - len(raw.lstrip())
            continue
        if not stripped:
            continue
        if len(raw) - len(raw.lstrip()) <= key_indent:
            break
        names.add(stripped)
    return names


def _workflow_fork_names(workflow_text: str) -> set[str]:
    """Fork names in the workflow's FORKS="..." block."""
    names: set[str] = set()
    in_block = False
    for raw in workflow_text.splitlines():
        stripped = raw.strip()
        if not in_block:
            if stripped.startswith('FORKS="'):
                in_block = True
            continue
        if stripped.startswith('"'):
            break
        if not stripped or "|" not in stripped:
            continue
        parts = stripped.split("|")
        if len(parts) >= 2 and parts[1]:
            names.add(parts[1])
    return names


def _sync_true_forks(registry: dict) -> set[str]:
    return {
        name
        for name, entry in registry.get("forks", {}).items()
        if entry.get("sync") is True
    }


def test_every_sync_true_registry_fork_is_in_the_workflow_forks_block():
    """POSITIVE: each sync:true fork IS named in the workflow's FORKS block."""
    registry = _read_real_registry()
    forks = _workflow_fork_names(REAL_WORKFLOW.read_text(encoding="utf-8"))
    sync_true = _sync_true_forks(registry)
    assert sync_true, "the registry must have sync:true forks for this to mean anything"
    missing = sorted(sync_true - forks)
    assert not missing, (
        "registry forks with sync:true are absent from the fork-sync FORKS "
        f"block: {missing}"
    )


def test_every_sync_true_registry_fork_is_in_the_github_app_scope():
    """POSITIVE: each sync:true fork IS in the GH App token scope block."""
    registry = _read_real_registry()
    scope = _workflow_scope_names(REAL_WORKFLOW.read_text(encoding="utf-8"))
    sync_true = _sync_true_forks(registry)
    assert sync_true, "the registry must have sync:true forks for this to mean anything"
    missing = sorted(sync_true - scope)
    assert not missing, (
        "registry forks with sync:true are absent from the GitHub App "
        f"'repositories:' scope: {missing}"
    )


def test_the_two_workflow_lists_have_identical_membership():
    """The FORKS block and the App scope must name the same repos.

    A fork in one list but not the other is a silent no-op: the token
    cannot reach a fork it was not scoped to.
    """
    text = REAL_WORKFLOW.read_text(encoding="utf-8")
    scope = _workflow_scope_names(text)
    forks = _workflow_fork_names(text)
    assert scope == forks, (
        "the FORKS block and the GitHub App scope disagree: "
        f"only in FORKS={sorted(forks - scope)} only in scope={sorted(scope - forks)}"
    )


def test_the_new_pipecat_forks_are_registered_with_the_required_fields():
    """Both unregistered pipecat forks are now registry entries, fully decided."""
    forks = _read_real_registry().get("forks", {})
    for name, upstream in NEW_PIECAT_FORKS.items():
        assert name in forks, f"{name} is not registered"
        entry = forks[name]
        assert entry.get("upstream") == upstream
        assert entry.get("sync") is True, f"{name} must be sync: true"
        assert entry.get("branch"), f"{name} must declare a branch"
        assert str(entry.get("reason", "")).strip(), f"{name} needs a non-empty reason"


def test_the_new_pipecat_forks_are_in_both_workflow_lists():
    """The newly registered forks are reachable by the workflow, not just claimed."""
    text = REAL_WORKFLOW.read_text(encoding="utf-8")
    scope = _workflow_scope_names(text)
    forks = _workflow_fork_names(text)
    for name in NEW_PIECAT_FORKS:
        assert name in forks, f"{name} is missing from the workflow FORKS block"
        assert name in scope, f"{name} is missing from the GitHub App scope"


def test_the_real_registry_and_workflow_report_no_problems():
    """The ratchet exits 0 against the real (now-consistent) files."""
    r = subprocess.run(
        [PYTHON, str(RATCHET), "--json"],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    out = json.loads(r.stdout)
    assert out["problems"] == []
    assert out["workflow_cross_check"] is True


# ---------------------------------------------------------------------------
# NEGATIVE CONTROL — the most important test in this file.
#
# A ratchet that can only assert absence cannot say no. This breaks a
# copy of the workflow (a sync:true fork is dropped from the FORKS block
# and from the App scope) and asserts the ratchet REPORTS the gap. Without
# it, the tests above would still pass if _validate_workflow_coverage
# returned an empty list unconditionally.
# ---------------------------------------------------------------------------


def _workflow_with_fork_removed(workflow_text: str, fork_name: str) -> str:
    """Return the workflow text with `fork_name` removed from both lists."""
    out: list[str] = []
    in_scope = False
    in_forks = False
    scope_indent = 0
    for raw in workflow_text.splitlines():
        stripped = raw.strip()
        if not in_scope and stripped.startswith("repositories:"):
            in_scope = True
            scope_indent = len(raw) - len(raw.lstrip())
            out.append(raw)
            continue
        if in_scope and not in_forks:
            if stripped and len(raw) - len(raw.lstrip()) <= scope_indent:
                in_scope = False
            elif stripped == fork_name:
                continue  # drop it from the scope
            out.append(raw)
            continue
        if stripped.startswith('FORKS="'):
            in_forks = True
            out.append(raw)
            continue
        if in_forks:
            if stripped.startswith('"'):
                in_forks = False
                out.append(raw)
                continue
            parts = stripped.split("|")
            if len(parts) >= 2 and parts[1] == fork_name:
                continue  # drop it from the FORKS block
            out.append(raw)
            continue
        out.append(raw)
    return "\n".join(out) + "\n"


def test_the_ratchet_reports_a_sync_true_fork_missing_from_the_workflow(tmp_path):
    """NEGATIVE CONTROL: break the workflow, the ratchet must say so."""
    registry = _read_real_registry()
    victim = sorted(_sync_true_forks(registry))[0]
    broken = tmp_path / "fork-sync-broken.yml"
    broken.write_text(
        _workflow_with_fork_removed(REAL_WORKFLOW.read_text(encoding="utf-8"), victim),
        encoding="utf-8",
    )

    # The broken copy really is broken — prove the fixture bites before
    # asserting on the tool's output.
    broken_text = broken.read_text(encoding="utf-8")
    assert victim not in _workflow_fork_names(broken_text)
    assert victim not in _workflow_scope_names(broken_text)

    r = subprocess.run(
        [
            PYTHON, str(RATCHET),
            "--registry", str(REAL_REGISTRY),
            "--workflow", str(broken),
            "--json",
        ],
        capture_output=True, text=True,
    )
    assert r.returncode == 1, f"the ratchet did not fail: {r.stdout}{r.stderr}"
    out = json.loads(r.stdout)
    assert out["workflow_cross_check"] is True
    problems = out["problems"]
    assert problems, "the ratchet reported no problems for a broken workflow"
    assert any(victim in p for p in problems), (
        f"the ratchet did not name the missing fork {victim}: {problems}"
    )
    assert any("FORKS block" in p for p in problems), (
        f"the ratchet did not report the FORKS-block gap: {problems}"
    )


def test_the_ratchet_reports_a_sync_true_fork_missing_from_the_app_scope(tmp_path):
    """NEGATIVE CONTROL, second half: scope-only gap is also reported.

    A fork in the FORKS block but not in the App scope gets a token that
    cannot reach it — a silent no-op rather than a visible failure.
    """
    registry = _read_real_registry()
    victim = sorted(_sync_true_forks(registry))[0]
    text = REAL_WORKFLOW.read_text(encoding="utf-8")
    # Remove ONLY the scope entry, leaving the FORKS block intact.
    broken = tmp_path / "fork-sync-no-scope.yml"
    broken.write_text(
        "\n".join(
            line
            for line in text.splitlines()
            if line.strip() != victim
            or f"|{victim}|" in line
        )
        + "\n",
        encoding="utf-8",
    )
    broken_text = broken.read_text(encoding="utf-8")
    assert victim in _workflow_fork_names(broken_text)
    assert victim not in _workflow_scope_names(broken_text)

    r = subprocess.run(
        [
            PYTHON, str(RATCHET),
            "--registry", str(REAL_REGISTRY),
            "--workflow", str(broken),
            "--json",
        ],
        capture_output=True, text=True,
    )
    assert r.returncode == 1, f"the ratchet did not fail: {r.stdout}{r.stderr}"
    problems = json.loads(r.stdout)["problems"]
    assert problems
    assert any(victim in p and "scope" in p for p in problems), (
        f"the ratchet did not report the App-scope gap for {victim}: {problems}"
    )


def test_the_ratchet_detects_a_gap_against_a_matched_temp_pair(tmp_path):
    """NEGATIVE CONTROL, hermetic pair: a temp registry + temp workflow.

    The ratchet must still say no when BOTH files are synthetic, so the
    gap-detection path is not secretly tied to the repo's own files.
    """
    registry = {"forks": {"F-Gap": {"upstream": "u/a", "sync": True, "reason": "r"}}}
    workflow = tmp_path / "fork-sync.yml"
    workflow.write_text(
        "name: x\n"
        "jobs:\n"
        "  sync:\n"
        "    steps:\n"
        "      - uses: a\n"
        "        with:\n"
        "          repositories: |\n"
        "            F-Other\n"
        "      - name: Sync forks\n"
        "        run: |\n"
        '          FORKS="\n'
        "          u/b|F-Other|\n"
        '          "\n',
        encoding="utf-8",
    )
    reg_file = tmp_path / "registry.json"
    reg_file.write_text(json.dumps(registry), encoding="utf-8")

    r = subprocess.run(
        [
            PYTHON, str(RATCHET),
            "--registry", str(reg_file),
            "--workflow", str(workflow),
            "--json",
        ],
        capture_output=True, text=True,
    )
    assert r.returncode == 1, f"the ratchet did not fail: {r.stdout}{r.stderr}"
    problems = json.loads(r.stdout)["problems"]
    assert any("F-Gap" in p for p in problems), (
        f"the ratchet did not report the missing fork: {problems}"
    )
