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


def test_an_environment_name_is_url_quoted_in_the_api_path(monkeypatch, tmp_path):
    """`--env` is free text and lands in a path segment; a space or a slash
    must not re-shape the endpoint."""
    seen: List[str] = []
    _scopes(monkeypatch, {None: [], "Prod env": ["A"]}, record=seen)
    aud.main(["--manifest", str(_manifest(tmp_path, ["A"])), "--env", "Prod env"])
    assert seen == ["repos/POWERFULMOVES/PMOVES.AI/environments/Prod%20env/secrets"]


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


# ---------------------------------------------------------------------------
# The string form, pinned verbatim. Routing was added beside it; a manifest
# that uses only bare names must read exactly as it did.
# ---------------------------------------------------------------------------


def test_the_string_form_text_report_is_unchanged(monkeypatch, tmp_path, capsys):
    _scopes(monkeypatch, {None: ["A", "STRAY"], "Prod": ["B"], "PMOVES": []})
    assert aud.main(["--manifest", str(_manifest(tmp_path, ["A", "B", "C"]))]) == 1
    captured = capsys.readouterr()
    assert captured.out == (
        "repo: POWERFULMOVES/PMOVES.AI\n"
        "  (repository)               2/100  headroom  98\n"
        "  env:Prod                   1/100  headroom  99\n"
        "  env:PMOVES                 0/100  headroom 100\n"
        "  declared 3  present across all scopes 3\n"
    )
    assert captured.err == (
        "  absent (1): declared, present in NO scope read\n"
        "    C\n"
        "  orphans (1): present, declared nowhere --\n"
        "    unmanaged by the funnel; reconciling these is free headroom\n"
        "    STRAY\n"
    )


# ---------------------------------------------------------------------------
# The mapping form: {github_secret: {name, repo, env}}. A routed name is
# measured in the repo -- and the scope -- the manifest pins it to.
# ---------------------------------------------------------------------------

N8N = "POWERFULMOVES/PMOVES-N8N"
MAIN = "POWERFULMOVES/PMOVES.AI"


def _targets_manifest(tmp_path: Path, values) -> Path:
    """One entry per `github_secret` value -- a bare name or a mapping."""
    path = tmp_path / "secrets_manifest_v2.yaml"
    path.write_text(
        yaml.safe_dump(
            {"secrets": [{"id": f"e{i}", "targets": [{"github_secret": v}]} for i, v in enumerate(values)]}
        ),
        encoding="utf-8",
    )
    return path


def _repos(monkeypatch, repos: Dict[str, Dict[Optional[str], List[str]]], record=None):
    """Stub `gh` for several repos. Keys: repo, then scope (None = repository)."""

    def fake(*args, **kwargs):
        endpoint = args[2]
        if record is not None:
            record.append(endpoint)
        repo = "/".join(endpoint.split("/")[1:3])
        scopes = repos.get(repo)
        if scopes is None:
            raise aud.Unmeasured(f"gh api {endpoint} failed: 404")
        if endpoint.endswith("/environments"):
            return "".join(f"{name}\n" for name in scopes if name is not None)
        if "/environments/" in endpoint:
            env = endpoint.split("/environments/")[1].split("/")[0]
            if env not in scopes:
                raise aud.Unmeasured(f"gh api {endpoint} failed: 404")
            return "".join(f"{name}\n" for name in scopes[env])
        return "".join(f"{name}\n" for name in scopes.get(None, []))

    monkeypatch.setattr(aud, "_gh", fake)


def test_a_routed_name_is_measured_in_its_own_repo(monkeypatch, tmp_path, capsys):
    seen: List[str] = []
    _repos(
        monkeypatch,
        {MAIN: {None: ["A"]}, N8N: {None: [], "Prod": ["N8N_API_KEY"]}},
        record=seen,
    )
    m = _targets_manifest(tmp_path, ["A", {"name": "N8N_API_KEY", "repo": N8N, "env": "Prod"}])
    rc = aud.main(["--manifest", str(m), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0, payload
    assert f"repos/{N8N}/environments/Prod/secrets" in seen
    others = {r["repo"]: r for r in payload["other_repos"]}
    assert set(others) == {N8N}
    assert others[N8N]["absent"] == [] and others[N8N]["orphans"] == []


def test_a_routed_name_in_the_wrong_scope_is_absent(monkeypatch, tmp_path, capsys):
    """Pinned to env:Prod but sitting in the repository scope. For an unrouted
    name either would do; for a routed one the manifest said WHERE."""
    _repos(monkeypatch, {MAIN: {None: ["A"]}, N8N: {None: ["N8N_API_KEY"], "Prod": []}})
    m = _targets_manifest(tmp_path, ["A", {"name": "N8N_API_KEY", "repo": N8N, "env": "Prod"}])
    assert aud.main(["--manifest", str(m)]) == 1
    captured = capsys.readouterr()
    assert f"repo: {N8N}" in captured.out
    assert "absent (1)" in captured.err and "N8N_API_KEY" in captured.err


def test_a_repo_scoped_mapping_means_the_repository_scope(monkeypatch, tmp_path, capsys):
    _repos(monkeypatch, {MAIN: {None: ["A"]}, N8N: {None: [], "Prod": ["R_KEY"]}})
    m = _targets_manifest(tmp_path, ["A", {"name": "R_KEY", "repo": N8N}])
    assert aud.main(["--manifest", str(m)]) == 1
    assert "R_KEY" in capsys.readouterr().err


def test_a_name_routed_away_but_still_in_pmoves_ai_is_an_orphan_there(monkeypatch, tmp_path, capsys):
    """The migration signal: once N8N_API_KEY is routed to PMOVES-N8N, its old
    copy in PMOVES.AI's Prod is unmanaged, and deleting it is the headroom."""
    _repos(
        monkeypatch,
        {MAIN: {None: ["A"], "Prod": ["N8N_API_KEY"]}, N8N: {None: [], "Prod": ["N8N_API_KEY"]}},
    )
    m = _targets_manifest(tmp_path, ["A", {"name": "N8N_API_KEY", "repo": N8N, "env": "Prod"}])
    assert aud.main(["--manifest", str(m), "--json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["orphans"] == ["N8N_API_KEY"]


def test_a_routed_names_copy_in_another_scope_of_its_repo_is_stale(monkeypatch, tmp_path, capsys):
    """Moved from env:Prod to env:PMOVES, old copy left in Prod. The name is
    declared for the repo, so it is no orphan -- and without this finding the
    audit exited 0 while Prod stayed full."""
    _repos(monkeypatch, {MAIN: {None: ["A"], "Prod": ["N"], "PMOVES": ["N"]}})
    m = _targets_manifest(tmp_path, ["A", {"name": "N", "repo": MAIN, "env": "PMOVES"}])
    assert aud.main(["--manifest", str(m), "--json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["stale_copies"] == [{"name": "N", "scope": "env:Prod"}]
    assert payload["orphans"] == [] and payload["absent"] == []


def test_a_stale_copy_is_reported_in_the_text_output(monkeypatch, tmp_path, capsys):
    _repos(monkeypatch, {MAIN: {None: ["A"]}, N8N: {None: ["N"], "Prod": ["N"]}})
    m = _targets_manifest(tmp_path, ["A", {"name": "N", "repo": N8N, "env": "Prod"}])
    assert aud.main(["--manifest", str(m)]) == 1
    err = capsys.readouterr().err
    assert "stale copies (1)" in err and "N  (repository)" in err


def test_a_bare_name_in_the_same_repo_is_not_stale(monkeypatch, tmp_path, capsys):
    """Negative control: declared bare AND pinned in one repo, the bare form
    may live in any scope, so its other copies are not stale."""
    _repos(monkeypatch, {MAIN: {None: ["N"], "PMOVES": ["N"]}})
    m = _targets_manifest(tmp_path, ["N", {"name": "N", "repo": MAIN, "env": "PMOVES"}])
    assert aud.main(["--manifest", str(m), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["stale_copies"] == []


def test_the_same_name_in_two_repos_is_measured_in_both(monkeypatch, tmp_path, capsys):
    """One CHIT source pushed to several repos is the design."""
    _repos(monkeypatch, {MAIN: {None: ["K"]}, N8N: {None: []}})
    m = _targets_manifest(tmp_path, ["K", {"name": "K", "repo": N8N}])
    assert aud.main(["--manifest", str(m), "--json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["absent"] == []
    assert payload["other_repos"][0]["absent"] == ["K"]


def test_routed_names_do_not_count_toward_the_single_scope_overflow(monkeypatch, tmp_path, capsys):
    """Only unrouted names share the one scope a push run writes. Routing names
    elsewhere is precisely how the overflow is relieved."""
    plain = [f"S{i:03d}" for i in range(aud.SECRET_LIMIT)]
    routed = [f"R{i}" for i in range(5)]
    _repos(monkeypatch, {MAIN: {None: plain}, N8N: {None: routed}})
    m = _targets_manifest(tmp_path, plain + [{"name": r, "repo": N8N} for r in routed])
    assert aud.main(["--manifest", str(m)]) == 0
    assert "OVERFLOW" not in capsys.readouterr().err


def test_a_pinned_scope_declared_past_the_ceiling_is_reported(monkeypatch, tmp_path, capsys):
    routed = [f"R{i:03d}" for i in range(aud.SECRET_LIMIT + 1)]
    _repos(monkeypatch, {MAIN: {None: ["A"]}, N8N: {None: [], "Prod": routed[: aud.SECRET_LIMIT]}})
    m = _targets_manifest(tmp_path, ["A"] + [{"name": r, "repo": N8N, "env": "Prod"} for r in routed])
    assert aud.main(["--manifest", str(m)]) == 1
    assert f"{N8N} env:Prod declares {aud.SECRET_LIMIT + 1}" in capsys.readouterr().err


def test_env_narrowing_still_reads_the_pinned_scopes(monkeypatch, tmp_path):
    """`--env X` asserts where UNROUTED names go, so the main repo is read in X
    alone with no discovery. A repo with pinned scopes lists its environments
    (to resolve them) and reads only the pinned ones."""
    seen: List[str] = []
    _repos(monkeypatch, {MAIN: {None: [], "Prod": ["A"]}, N8N: {None: [], "Prod": ["N"]}}, record=seen)
    m = _targets_manifest(tmp_path, ["A", {"name": "N", "repo": N8N, "env": "Prod"}])
    assert aud.main(["--manifest", str(m), "--env", "Prod"]) == 0
    assert seen == [
        f"repos/{MAIN}/environments/Prod/secrets",
        f"repos/{N8N}/environments",
        f"repos/{N8N}/environments/Prod/secrets",
    ]


def test_a_missing_pinned_environment_under_env_is_absent_not_unmeasured(monkeypatch, tmp_path, capsys):
    """Same verdict with or without --env: it used to read the nonexistent
    environment directly, get a 404, and exit 3."""
    _repos(monkeypatch, {MAIN: {None: [], "Prod": ["A"]}, N8N: {None: []}})
    m = _targets_manifest(tmp_path, ["A", {"name": "N", "repo": N8N, "env": "Prod"}])
    assert aud.main(["--manifest", str(m), "--env", "Prod", "--json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["other_repos"][0]["absent"] == ["N"]
    assert payload["other_repos"][0]["missing_scopes"] == ["env:Prod"]


def test_repo_and_env_match_case_insensitively(monkeypatch, tmp_path, capsys):
    """GitHub matches both case-insensitively. A mapping spelled
    `powerfulmoves/pmoves.ai` / `prod` is env:Prod of the main repo -- not a
    second repo with a missing environment."""
    _repos(monkeypatch, {MAIN: {None: ["A"], "Prod": ["N"]}})
    m = _targets_manifest(tmp_path, ["A", {"name": "N", "repo": MAIN.lower(), "env": "prod"}])
    rc = aud.main(["--manifest", str(m), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0, payload
    assert payload["other_repos"] == [] and payload["missing_scopes"] == []


def test_a_pinned_environment_that_does_not_exist_is_absent_not_unmeasured(monkeypatch, tmp_path, capsys):
    """Discovery succeeded and the environment is not there: every name pinned
    to it is absent. That is a measurement, not a failure to measure."""
    _repos(monkeypatch, {MAIN: {None: ["A"]}, N8N: {None: []}})
    m = _targets_manifest(tmp_path, ["A", {"name": "N", "repo": N8N, "env": "Prod"}])
    assert aud.main(["--manifest", str(m), "--json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["other_repos"][0]["absent"] == ["N"]
    assert payload["other_repos"][0]["missing_scopes"] == ["env:Prod"]


def test_an_unreadable_routed_repo_is_unmeasured(monkeypatch, tmp_path):
    _repos(monkeypatch, {MAIN: {None: ["A"]}})
    m = _targets_manifest(tmp_path, ["A", {"name": "N", "repo": N8N}])
    assert aud.main(["--manifest", str(m)]) == 3


def test_a_malformed_routed_target_is_unmeasured(monkeypatch, tmp_path, capsys):
    _repos(monkeypatch, {MAIN: {None: ["A"]}})
    m = _targets_manifest(tmp_path, ["A", {"repo": N8N}])
    assert aud.main(["--manifest", str(m)]) == 3
    assert "name" in capsys.readouterr().err
