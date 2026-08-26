"""The unreviewed-push audit must separate the sanctioned bypass from the rest.

`main` grants RepositoryRole an `always` bypass, and the coordination ledger
depends on it: a claim register that needs PR latency to record a claim defeats
the Village Rule it enforces. So "landed without a PR" is NOT the finding. The
finding is "landed without a PR and touched something other than the ledger".

Two of these tests exist because the first version of the tool got review
detection wrong in ways that read as correct, and a third because it reported
a git failure as a clean result. All three are the defect the tool reports.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOL = REPO_ROOT / "pmoves" / "tools" / "unreviewed_push_audit.py"

LEDGER = "pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md"
ROUTING = "pmoves/tensorzero/config/tensorzero.toml"


def _audit_module():
    spec = importlib.util.spec_from_file_location("unreviewed_push_audit", TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules["unreviewed_push_audit"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def mod():
    return _audit_module()


def _wire(m, monkeypatch, *, shas, pr_map, path_map, merge_map=None):
    """Declare the world: which commits exist, which have PRs, what they touched."""
    merge_map = merge_map or {}

    def fake_git(args):
        if args[0] == "rev-list" and "--parents" not in args:
            return "\n".join(shas)
        if args[0] == "rev-list":
            sha = args[-1]
            # `rev-list --parents -n 1` prints "<sha> <parent>..."
            return f"{sha} p1 p2" if merge_map.get(sha) else f"{sha} p1"
        if args[0] == "show" and "-s" in args:
            return "Some Author|2026-08-26|a subject"
        if args[0] == "show":
            return "\n".join(path_map[args[-1]])
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(m, "_git", fake_git)
    monkeypatch.setattr(m, "has_associated_pr", lambda repo, sha: pr_map[sha])


def test_ledger_only_push_is_not_a_finding(mod, monkeypatch):
    """The sanctioned exception. Flagging these would make the tool noise and
    invite someone to disable it, taking the real finding with it."""
    _wire(mod, monkeypatch, shas=["aaa"], pr_map={"aaa": False},
          path_map={"aaa": [LEDGER]})
    assert mod.audit("o/r", "X..Y") == []


def test_non_ledger_push_without_a_pr_is_a_finding(mod, monkeypatch):
    _wire(mod, monkeypatch, shas=["bbb"], pr_map={"bbb": False},
          path_map={"bbb": [ROUTING]})
    found = mod.audit("o/r", "X..Y")
    assert len(found) == 1
    assert found[0]["files_outside_ledger"] == [ROUTING]
    assert found[0]["kind"] == "direct"


def test_a_mixed_push_is_a_finding_on_its_non_ledger_files(mod, monkeypatch):
    """1b98d01a3's real shape: a ledger row committed alongside live routing
    config. Counting it as ledger-only because it touched the ledger would let
    any change ride in under a register update."""
    _wire(mod, monkeypatch, shas=["ccc"], pr_map={"ccc": False},
          path_map={"ccc": [LEDGER, ROUTING]})
    found = mod.audit("o/r", "X..Y")
    assert len(found) == 1
    assert found[0]["files_outside_ledger"] == [ROUTING]


def test_a_commit_with_a_pr_is_never_a_finding(mod, monkeypatch):
    _wire(mod, monkeypatch, shas=["ddd"], pr_map={"ddd": True},
          path_map={"ddd": [ROUTING]})
    assert mod.audit("o/r", "X..Y") == []


def test_a_merge_commit_with_no_pr_IS_a_finding(mod, monkeypatch):
    """The blind spot. An earlier version skipped every merge commit, reasoning
    that "a merge commit on main is the result of a PR" -- an inference, not a
    check. An admin can create one locally and push it straight to main: two
    parents, no pull request, and the audit never looked at it."""
    _wire(mod, monkeypatch, shas=["eee"], pr_map={"eee": False},
          path_map={"eee": [ROUTING]}, merge_map={"eee": True})
    found = mod.audit("o/r", "X..Y")
    assert len(found) == 1, "a locally-crafted merge commit must not be invisible"
    assert found[0]["kind"] == "merge"


def test_a_merge_commit_with_a_pr_is_not_a_finding(mod, monkeypatch):
    """The ordinary case: PR merges are the overwhelming majority on main and
    must stay silent, or the report is unreadable."""
    _wire(mod, monkeypatch, shas=["fff"], pr_map={"fff": True},
          path_map={"fff": [ROUTING]}, merge_map={"fff": True})
    assert mod.audit("o/r", "X..Y") == []


def test_a_merge_is_inspected_against_its_first_parent(mod, monkeypatch):
    """`git show` on a merge without --first-parent prints only conflict
    resolutions -- usually nothing -- so an unreviewed merge would report zero
    changed files and be dismissed as ledger-only."""
    m = _audit_module()
    seen: list[list[str]] = []

    def fake_git(args):
        seen.append(list(args))
        if args[0] == "rev-list" and "--parents" in args:
            return "ggg p1 p2"
        if args[0] == "rev-list":
            return "ggg"
        if args[0] == "show" and "-s" in args:
            return "A|2026-08-26|s"
        return ROUTING

    monkeypatch.setattr(m, "_git", fake_git)
    monkeypatch.setattr(m, "has_associated_pr", lambda repo, sha: False)
    m.audit("o/r", "X..Y")
    show = [a for a in seen if a[0] == "show" and "--name-only" in a]
    assert show and "--first-parent" in show[0], (
        f"merge inspected without --first-parent: {show}"
    )


def test_a_failing_git_command_is_not_reported_as_clean(mod, monkeypatch, capsys):
    """`git rev-list` on an unresolvable range exits nonzero with EMPTY stdout,
    which became an empty commit list, which printed "no findings" and exited
    0. An audit that could not run must never render as an audit that found
    nothing."""
    def boom(args):
        raise RuntimeError("git rev-list failed (exit 128): unknown revision")
    monkeypatch.setattr(mod, "_git", boom)
    code = mod.main(["--range", "nonsense..range"])
    assert code == 2
    assert "could not complete" in capsys.readouterr().err


def test_an_api_fault_is_not_reported_as_clean(mod, monkeypatch, capsys):
    monkeypatch.setattr(mod, "audit", _raise)
    assert mod.main(["--range", "X..Y"]) == 2
    assert "could not complete" in capsys.readouterr().err


def _raise(*_a, **_k):
    raise RuntimeError("gh api failed: connection reset")


def test_the_allowlist_is_the_ledger_and_nothing_else():
    """Structural: widening this silently is how the audit would stop working
    while still passing. Any addition should be a deliberate, reviewed edit."""
    m = _audit_module()
    assert m.LEDGER_PREFIXES == ("pmoves/docs/AGENTS/",), (
        f"allowlist changed to {m.LEDGER_PREFIXES!r}. Every path added here is "
        "a path an admin may rewrite on main with no review."
    )


def test_the_workflow_grants_pull_request_read():
    """The API lookup needs `pull-requests: read`. With only `contents: read`
    every lookup returns "Resource not accessible by integration" and every run
    is an incomplete audit -- loud, but never once a detection."""
    wf = (REPO_ROOT / ".github" / "workflows" / "unreviewed-push-audit.yml"
          ).read_text(encoding="utf-8")
    assert "pull-requests: read" in wf, (
        "workflow lacks pull-requests: read; the commit-to-PR endpoint is "
        "unreachable without it"
    )
