"""Offline tests for the GitHub secret capacity reconciliation.

`gh` is stubbed, so these run with no network and no auth. What is under test is
the verdict logic and -- above all -- that an unmeasurable scope exits 3 rather
than 0.

Context: GitHub caps secrets at 100 PER SCOPE (repository, and each environment
separately). Nothing compared the CHIT manifest's declarations against that
ceiling, so the funnel could declare more than the platform can store and report
success throughout. Measured 2026-08-28: 158 declared, Prod at 100/100.

The scope is chosen at PUSH time (`push-gh-secrets.sh --env`), never in the
manifest, so a declared name may live in ANY scope. Several tests below exist
specifically to keep the audit from comparing the full declared set against one
scope and calling the difference "absent".
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE = REPO_ROOT / "pmoves" / "tools" / "github_secret_capacity_audit.py"

spec = importlib.util.spec_from_file_location("github_secret_capacity_audit", MODULE)
assert spec and spec.loader
aud = importlib.util.module_from_spec(spec)
sys.modules["github_secret_capacity_audit"] = aud
spec.loader.exec_module(aud)


def _manifest(tmp_path: Path, names: List[str]) -> Path:
    path = tmp_path / "secrets_manifest_v2.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "secrets": [
                    {"id": n.lower(), "targets": [{"github_secret": n}]} for n in names
                ]
            }
        ),
        encoding="utf-8",
    )
    return path


def _scopes(monkeypatch, scopes: Dict[Optional[str], List[str]], record=None):
    """Stub `gh` for a fleet of scopes.

    Keys are environment names; `None` is the repository scope. The audit now
    reads the environment listing AND one secrets endpoint per scope, so a
    single canned response is no longer enough to stub it.
    """
    environments = [name for name in scopes if name is not None]

    def fake(*args, **kwargs):
        endpoint = args[2]
        if record is not None:
            record.append(endpoint)
        if endpoint.endswith("/environments"):
            return "".join(f"{name}\n" for name in environments)
        if "/environments/" in endpoint:
            env = endpoint.split("/environments/")[1].split("/")[0]
            return "".join(f"{name}\n" for name in scopes.get(env, []))
        return "".join(f"{name}\n" for name in scopes.get(None, []))

    monkeypatch.setattr(aud, "_gh", fake)


def _present(monkeypatch, names: List[str], record=None):
    """The common case: a repository scope and no environments."""
    _scopes(monkeypatch, {None: names}, record=record)


def test_a_clean_scope_passes(monkeypatch, tmp_path):
    _present(monkeypatch, ["A", "B"])
    assert aud.main(["--manifest", str(_manifest(tmp_path, ["A", "B"]))]) == 0


def test_an_absent_declared_secret_is_a_finding(monkeypatch, tmp_path, capsys):
    _present(monkeypatch, ["A"])
    assert aud.main(["--manifest", str(_manifest(tmp_path, ["A", "B"]))]) == 1
    assert "absent" in capsys.readouterr().err


def test_an_orphan_is_a_finding(monkeypatch, tmp_path, capsys):
    """Present in GitHub, declared nowhere -- unmanaged, and free headroom."""
    _present(monkeypatch, ["A", "STRAY"])
    assert aud.main(["--manifest", str(_manifest(tmp_path, ["A"]))]) == 1
    err = capsys.readouterr().err
    assert "orphans" in err and "STRAY" in err


# ---------------------------------------------------------------------------
# Scope handling. The manifest names no environment, so these guard the audit
# against comparing the whole declared set to a single scope.
# ---------------------------------------------------------------------------


def test_a_secret_living_in_an_environment_is_not_absent(monkeypatch, tmp_path, capsys):
    """The defect this audit was rewritten to fix.

    `push-gh-secrets.sh --env Prod` puts a declared name in Prod, not in the
    repository scope. Reading only the repository scope would report it absent
    -- a confident wrong answer that reads as "the funnel failed to push it".
    """
    _scopes(monkeypatch, {None: ["A"], "Prod": ["B"]})
    assert aud.main(["--manifest", str(_manifest(tmp_path, ["A", "B"]))]) == 0
    assert "absent" not in capsys.readouterr().err


def test_every_scope_is_read_by_default(monkeypatch, tmp_path):
    """Absence means "present in NO scope", so every scope must be queried."""
    seen: List[str] = []
    _scopes(monkeypatch, {None: ["A"], "Prod": ["B"], "PMOVES": []}, record=seen)
    aud.main(["--manifest", str(_manifest(tmp_path, ["A", "B"]))])
    assert any(e.endswith("/actions/secrets") for e in seen), "repository scope unread"
    assert any("/environments/Prod/secrets" in e for e in seen), "Prod unread"
    assert any("/environments/PMOVES/secrets" in e for e in seen), "PMOVES unread"


def test_unlistable_environments_are_unmeasured_not_partial(monkeypatch, tmp_path):
    """If the scope list cannot be enumerated, the union is unknown.

    Falling back to "just audit the repository scope" would silently restore
    the very bug above, so this refuses rather than answering partially.
    """

    def fake(*args, **kwargs):
        if args[2].endswith("/environments"):
            raise aud.Unmeasured("gh api environments failed: 403")
        return "A\n"

    monkeypatch.setattr(aud, "_gh", fake)
    assert aud.main(["--manifest", str(_manifest(tmp_path, ["A"]))]) == 3


def test_the_environment_scope_is_addressed_separately(monkeypatch, tmp_path):
    """Repository and each environment have their OWN 100. The endpoint differs,
    and auditing the wrong one would report another scope's usage."""
    seen: List[str] = []
    _scopes(monkeypatch, {None: ["A"], "Prod": ["A"]}, record=seen)
    aud.main(["--manifest", str(_manifest(tmp_path, ["A"])), "--env", "Prod"])
    assert seen == ["repos/POWERFULMOVES/PMOVES.AI/environments/Prod/secrets"]


def test_a_single_scope_read_declares_its_own_assumption(monkeypatch, tmp_path, capsys):
    """`--env X` asserts the funnel targets X. Absence is only true if it does,
    so the output has to say which assumption it rests on."""
    _scopes(monkeypatch, {None: ["A"], "Prod": ["A"]})
    aud.main(["--manifest", str(_manifest(tmp_path, ["A"])), "--env", "Prod"])
    out = capsys.readouterr().out
    assert "only" in out and "push-gh-secrets.sh --env" in out


def test_per_scope_capacity_is_reported_for_every_scope(monkeypatch, tmp_path, capsys):
    """A full scope beside an empty one is the whole point: Prod at 100/100
    while PMOVES holds 1 is 99 slots nobody can currently address."""
    _scopes(monkeypatch, {None: ["A"], "Prod": ["A"], "PMOVES": []})
    aud.main(["--manifest", str(_manifest(tmp_path, ["A"])), "--json"])
    payload = json.loads(capsys.readouterr().out)
    scopes = {row["scope"]: row for row in payload["per_scope"]}
    assert set(scopes) == {"(repository)", "env:Prod", "env:PMOVES"}
    assert scopes["env:PMOVES"]["headroom"] == 100


def test_at_cap_is_flagged(monkeypatch, tmp_path, capsys):
    names = [f"S{i:03d}" for i in range(aud.SECRET_LIMIT)]
    _present(monkeypatch, names)
    aud.main(["--manifest", str(_manifest(tmp_path, names)), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["per_scope"][0]["at_cap"] is True


# ---------------------------------------------------------------------------
# Capacity
# ---------------------------------------------------------------------------


def test_declaring_more_than_the_ceiling_is_reported(monkeypatch, tmp_path, capsys):
    """The finding that motivated this tool.

    The funnel writes ONE scope per run, so 101 declared names cannot all be
    provisioned by a run into a 100-secret scope. Without this the funnel pushes
    until GitHub refuses and the excess is simply never stored.
    """
    names = [f"S{i:03d}" for i in range(aud.SECRET_LIMIT + 1)]
    _present(monkeypatch, names[: aud.SECRET_LIMIT])
    assert aud.main(["--manifest", str(_manifest(tmp_path, names))]) == 1
    assert "SINGLE-SCOPE OVERFLOW by 1" in capsys.readouterr().err


def test_exactly_at_the_ceiling_is_not_over_capacity(monkeypatch, tmp_path):
    """Negative control: 100 declared into a 100 scope is full, not over."""
    names = [f"S{i:03d}" for i in range(aud.SECRET_LIMIT)]
    _present(monkeypatch, names)
    assert aud.main(["--manifest", str(_manifest(tmp_path, names))]) == 0


def test_headroom_is_reported_against_the_limit(monkeypatch, tmp_path, capsys):
    _present(monkeypatch, ["A", "B"])
    aud.main(["--manifest", str(_manifest(tmp_path, ["A", "B"])), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["limit"] == 100
    assert payload["per_scope"][0]["headroom"] == 98


def test_the_listing_is_paginated(monkeypatch, tmp_path):
    """The API pages at 30. A truncated read under-reports usage and
    over-reports absences -- which is exactly how a first pass at this
    measurement produced 157 of 158 'missing'."""
    seen = {}

    def fake(*args, **kwargs):
        seen["args"] = args
        return "A\n"

    monkeypatch.setattr(aud, "_gh", fake)
    aud.main(["--manifest", str(_manifest(tmp_path, ["A"]))])
    assert "--paginate" in seen["args"]


# ---------------------------------------------------------------------------
# Refusing to guess
# ---------------------------------------------------------------------------


def test_no_gh_is_unmeasured_not_a_pass(monkeypatch, tmp_path):
    monkeypatch.setattr(aud.shutil, "which", lambda _: None)
    assert aud.main(["--manifest", str(_manifest(tmp_path, ["A"]))]) == 3


def test_an_unreadable_manifest_is_unmeasured(monkeypatch, tmp_path):
    _present(monkeypatch, ["A"])
    assert aud.main(["--manifest", str(tmp_path / "absent.yaml")]) == 3


def test_a_manifest_with_no_targets_is_unmeasured(monkeypatch, tmp_path):
    """An empty declaration set would make every present secret an 'orphan'.

    Reporting 100 orphans because the manifest failed to parse would be a
    confident wrong answer; refusing to answer is correct.
    """
    _present(monkeypatch, ["A"])
    bad = tmp_path / "bad.yaml"
    bad.write_text(yaml.safe_dump({"version": 1}), encoding="utf-8")
    assert aud.main(["--manifest", str(bad)]) == 3


def test_targets_without_github_secret_are_unmeasured(monkeypatch, tmp_path, capsys):
    """The guard above checks for `targets`, not for GitHub targets.

    A file/Docker-only manifest has entries WITH targets and no `github_secret`
    among them. That yields an empty declared set, which would make every real
    secret an orphan -- a deletion signal built from nothing.
    """
    _present(monkeypatch, ["A", "B"])
    docker_only = tmp_path / "docker_only.yaml"
    docker_only.write_text(
        yaml.safe_dump(
            {"secrets": [{"id": "a", "targets": [{"docker_secret": "a", "file": "/x"}]}]}
        ),
        encoding="utf-8",
    )
    assert aud.main(["--manifest", str(docker_only)]) == 3
    assert "no `github_secret` targets" in capsys.readouterr().err


def test_json_mode_distinguishes_unmeasured_from_clean(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(aud.shutil, "which", lambda _: None)
    aud.main(["--manifest", str(_manifest(tmp_path, ["A"])), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["measured"] is False
