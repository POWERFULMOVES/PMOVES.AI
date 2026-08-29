"""Tests for the container-hardening ratchet.

The tool had none. It gained them alongside the branch-scope change, because
that change relaxes a failure condition and a relaxation without a negative
control is indistinguishable from a hole.

The property under test is the ratchet's actual promise: a baseline may not rot
into a permanent allowlist. Fixing a Dockerfile and leaving its entry behind
must still fail. What must NOT fail is an entry for a file this branch does not
carry -- `PMOVES.AI-Edition-Hardened` tracks CATACLYSM Dockerfiles main has
never had, and treating those as stale made one baseline unusable across the
two trees at once.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE = REPO_ROOT / "pmoves" / "tools" / "hardening_ratchet.py"

spec = importlib.util.spec_from_file_location("hardening_ratchet", MODULE)
assert spec and spec.loader
hr = importlib.util.module_from_spec(spec)
sys.modules["hardening_ratchet"] = hr
spec.loader.exec_module(hr)


def _wire(monkeypatch, *, tracked, findings, baseline, argv=()):
    """Stub discovery, scanning and the baseline.

    `tracked` is what `git ls-files` would return for this tree; `findings` are
    the paths currently failing. The split matters: a baselined path may be
    tracked-and-fixed or absent entirely, and the whole change is that those
    two are no longer the same thing.
    """
    monkeypatch.setattr(hr, "discover_dockerfiles", lambda: list(tracked))
    monkeypatch.setattr(
        hr, "scan",
        lambda: [{"kind": "NO_USER", "where": p, "detail": ""} for p in findings],
    )
    monkeypatch.setattr(hr, "load_baseline", lambda: set(baseline))
    # `main()` parses sys.argv, so pytest's own arguments would otherwise reach
    # argparse and exit(2) before the ratchet judged anything.
    monkeypatch.setattr(sys, "argv", ["hardening_ratchet.py", *argv])


def test_a_clean_tree_passes(monkeypatch):
    _wire(monkeypatch, tracked=["a/Dockerfile"], findings=[], baseline=[])
    assert hr.main() == 0


def test_a_new_finding_fails(monkeypatch):
    _wire(monkeypatch, tracked=["a/Dockerfile"], findings=["a/Dockerfile"], baseline=[])
    assert hr.main() == 1


def test_a_baselined_finding_passes(monkeypatch):
    _wire(monkeypatch, tracked=["a/Dockerfile"], findings=["a/Dockerfile"],
          baseline=["NO_USER|a/Dockerfile"])
    assert hr.main() == 0


# --- the branch-scope split ---------------------------------------------------


def test_a_fixed_file_still_listed_is_STALE_and_fails(monkeypatch):
    """The negative control for the whole change.

    The file IS tracked here and no longer fails, so its entry is rot. Without
    this the relaxation below would be a hole: every stale entry would read as
    "some other branch's file" and the baseline would become the permanent
    allowlist the ratchet exists to prevent.
    """
    _wire(monkeypatch, tracked=["a/Dockerfile"], findings=[],
          baseline=["NO_USER|a/Dockerfile"])
    assert hr.main() == 1


def test_an_entry_for_a_file_not_in_this_tree_does_not_fail(monkeypatch):
    """The case that made one baseline unusable across two branches.

    hardened carries CATACLYSM Dockerfiles main has never had. Baseline them
    and main goes red with stale entries; omit them and hardened goes red with
    new ones. The ratchet was unsatisfiable on both trees at once.
    """
    _wire(monkeypatch, tracked=["a/Dockerfile"], findings=[],
          baseline=["NO_USER|other-branch-only/Dockerfile"])
    assert hr.main() == 0


def test_not_in_tree_entries_are_reported_not_swallowed(monkeypatch, capsys):
    """An entry NO branch carries any more is real rot, and can only be noticed
    if it is printed. Passing silently would trade one blind spot for another."""
    _wire(monkeypatch, tracked=["a/Dockerfile"], findings=[],
          baseline=["NO_USER|other-branch-only/Dockerfile"])
    hr.main()
    out = capsys.readouterr().out
    assert "NOT IN THIS TREE" in out
    assert "other-branch-only/Dockerfile" in out


def test_stale_and_not_in_tree_are_judged_independently(monkeypatch):
    """Both kinds present at once: the tracked-and-fixed one must still fail,
    and must not be excused by the presence of the other."""
    _wire(monkeypatch, tracked=["a/Dockerfile"], findings=[],
          baseline=["NO_USER|a/Dockerfile", "NO_USER|elsewhere/Dockerfile"])
    assert hr.main() == 1


def test_json_reports_the_two_kinds_separately(monkeypatch, capsys):
    """The JSON surface must expose the distinction too, or a consumer reading
    `stale` alone would see a shorter list and conclude entries vanished."""
    _wire(monkeypatch, tracked=["a/Dockerfile"], findings=[],
          baseline=["NO_USER|a/Dockerfile", "NO_USER|elsewhere/Dockerfile"],
          argv=["--json"])
    hr.main()
    payload = json.loads(capsys.readouterr().out)
    assert payload["stale"] == ["NO_USER|a/Dockerfile"]
    assert payload["not_in_tree"] == ["NO_USER|elsewhere/Dockerfile"]


def test_a_path_containing_a_pipe_is_split_only_once(monkeypatch):
    """`KIND|path` is split with maxsplit=1. A path containing '|' would
    otherwise be truncated and silently classified as not-in-tree."""
    odd = "weird|name/Dockerfile"
    _wire(monkeypatch, tracked=[odd], findings=[], baseline=[f"NO_USER|{odd}"])
    assert hr.main() == 1, "a piped path was misread as belonging to another tree"
