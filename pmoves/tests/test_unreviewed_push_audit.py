"""The unreviewed-push audit must separate the sanctioned bypass from the rest.

`main` grants RepositoryRole an `always` bypass, and the coordination ledger
depends on it: a claim register that needs PR latency to record a claim defeats
the Village Rule it enforces. So "landed without a PR" is NOT the finding. The
finding is "landed without a PR and touched something other than the ledger".

The distinction is the entire tool, so it is what these tests pin -- including
that an API fault is reported as a fault rather than as a clean result.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOL = REPO_ROOT / "pmoves" / "tools" / "unreviewed_push_audit.py"


def _audit_module():
    spec = importlib.util.spec_from_file_location("unreviewed_push_audit", TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules["unreviewed_push_audit"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def mod(monkeypatch):
    m = _audit_module()
    # Isolate from git and the network; each test declares the world it wants.
    monkeypatch.setattr(m, "is_merge_commit", lambda sha: False)
    return m


def _wire(m, monkeypatch, *, shas, pr_map, path_map):
    monkeypatch.setattr(m.subprocess, "run", lambda *a, **k: _fake(a, shas))
    monkeypatch.setattr(m, "has_associated_pr", lambda repo, sha: pr_map[sha])
    monkeypatch.setattr(m, "changed_paths", lambda sha: path_map[sha])


class _fake:
    """Minimal stand-in for the rev-list and metadata subprocess calls."""
    def __init__(self, args, shas):
        argv = args[0]
        if "rev-list" in argv:
            self.stdout = "\n".join(shas)
        else:  # git show -s --format=...
            self.stdout = "Some Author|2026-08-25|a subject"


def test_ledger_only_push_is_not_a_finding(mod, monkeypatch):
    """The sanctioned exception. Flagging these would make the tool noise and
    invite someone to disable it, taking the real finding with it."""
    _wire(mod, monkeypatch,
          shas=["aaa"], pr_map={"aaa": False},
          path_map={"aaa": ["pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md"]})
    assert mod.audit("o/r", "X..Y") == []


def test_non_ledger_push_without_a_pr_is_a_finding(mod, monkeypatch):
    _wire(mod, monkeypatch,
          shas=["bbb"], pr_map={"bbb": False},
          path_map={"bbb": ["pmoves/tensorzero/config/tensorzero.toml"]})
    found = mod.audit("o/r", "X..Y")
    assert len(found) == 1
    assert found[0]["files_outside_ledger"] == ["pmoves/tensorzero/config/tensorzero.toml"]


def test_a_mixed_push_is_a_finding_on_its_non_ledger_files(mod, monkeypatch):
    """1b98d01a3's real shape: a ledger row committed alongside live routing
    config. Counting it as ledger-only because it touched the ledger would let
    any change ride in under a register update."""
    _wire(mod, monkeypatch,
          shas=["ccc"], pr_map={"ccc": False},
          path_map={"ccc": ["pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md",
                            "pmoves/tensorzero/config/tensorzero.toml"]})
    found = mod.audit("o/r", "X..Y")
    assert len(found) == 1
    assert found[0]["files_outside_ledger"] == ["pmoves/tensorzero/config/tensorzero.toml"]


def test_a_commit_with_a_pr_is_never_a_finding(mod, monkeypatch):
    _wire(mod, monkeypatch,
          shas=["ddd"], pr_map={"ddd": True},
          path_map={"ddd": ["pmoves/tensorzero/config/tensorzero.toml"]})
    assert mod.audit("o/r", "X..Y") == []


def test_merge_commits_are_skipped(mod, monkeypatch):
    """A merge commit on main is the result of a PR, not a bypass."""
    monkeypatch.setattr(mod, "is_merge_commit", lambda sha: True)
    _wire(mod, monkeypatch,
          shas=["eee"], pr_map={"eee": False},
          path_map={"eee": ["pmoves/tensorzero/config/tensorzero.toml"]})
    assert mod.audit("o/r", "X..Y") == []


def test_an_api_fault_is_not_reported_as_clean(mod, monkeypatch, capsys):
    """A network fault must exit 2, not 0. 'Could not check' reading as
    'nothing to report' is the silent-green failure this repo keeps hitting."""
    monkeypatch.setattr(mod, "audit", _raise)
    code = mod.main(["--range", "X..Y"])
    assert code == 2
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
