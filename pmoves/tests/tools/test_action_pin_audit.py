"""Offline tests for the action-pin gate.

The network layer is stubbed so these run in CI without API calls; what is under
test is the parser, the error/warning split, and — most importantly — that an
unreachable API produces exit 3 rather than exit 0.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = REPO_ROOT / "pmoves" / "tools" / "action_pin_audit.py"

spec = importlib.util.spec_from_file_location("action_pin_audit", MODULE_PATH)
assert spec and spec.loader
apa = importlib.util.module_from_spec(spec)
sys.modules["action_pin_audit"] = apa
spec.loader.exec_module(apa)

REAL_SHA = "a" * 40
FAKE_SHA = "b" * 40


def write_workflow(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "wf.yml"
    path.write_text(body, encoding="utf-8")
    return path


def fake_api(known_commits: set[str], known_tags: set[str]):
    def _get(path: str, cache: dict) -> object | None:
        if "/commits/" in path:
            return {"sha": path.rsplit("/", 1)[1]} if path.rsplit("/", 1)[1] in known_commits else None
        if "/git/ref/tags/" in path:
            return {"ref": path} if path.rsplit("/", 1)[1] in known_tags else None
        raise AssertionError(f"unexpected path {path}")
    return _get


# ── parsing ──────────────────────────────────────────────────────────────────

def test_collects_sha_pin_with_version_comment(tmp_path):
    path = write_workflow(tmp_path, f"      - uses: actions/checkout@{REAL_SHA} # v7.0.1\n")
    pins = apa.collect_pins([path])
    assert len(pins) == 1
    assert pins[0]["owner"] == "actions"
    assert pins[0]["repo"] == "checkout"
    assert pins[0]["sha"] == REAL_SHA
    assert pins[0]["version"] == "v7.0.1"
    assert pins[0]["line"] == 1


def test_ignores_tag_and_branch_refs(tmp_path):
    path = write_workflow(tmp_path, "      - uses: actions/checkout@v4\n      - uses: foo/bar@main\n")
    assert apa.collect_pins([path]) == []


def test_handles_subpath_actions(tmp_path):
    """github/codeql-action/init@sha must resolve against github/codeql-action."""
    path = write_workflow(tmp_path, f"      - uses: github/codeql-action/init@{REAL_SHA} # v3\n")
    pins = apa.collect_pins([path])
    assert len(pins) == 1
    assert (pins[0]["owner"], pins[0]["repo"]) == ("github", "codeql-action")


def test_pin_without_comment_has_no_version(tmp_path):
    path = write_workflow(tmp_path, f"      - uses: actions/checkout@{REAL_SHA}\n")
    assert apa.collect_pins([path])[0]["version"] is None


def test_uses_without_leading_dash(tmp_path):
    path = write_workflow(tmp_path, f"        uses: actions/checkout@{REAL_SHA} # v7.0.1\n")
    assert len(apa.collect_pins([path])) == 1


# ── verdicts ─────────────────────────────────────────────────────────────────

def test_resolvable_pin_passes(tmp_path, monkeypatch):
    monkeypatch.setattr(apa, "_get", fake_api({REAL_SHA}, {"v7.0.1"}))
    path = write_workflow(tmp_path, f"      - uses: actions/checkout@{REAL_SHA} # v7.0.1\n")
    errors, warnings = apa.audit(apa.collect_pins([path]))
    assert errors == [] and warnings == []


def test_unresolvable_sha_is_an_error(tmp_path, monkeypatch):
    """The exact defect: a SHA that exists nowhere kills the workflow at setup."""
    monkeypatch.setattr(apa, "_get", fake_api({REAL_SHA}, {"v7.0.1"}))
    path = write_workflow(tmp_path, f"      - uses: actions/upload-artifact@{FAKE_SHA} # v8.0.0\n")
    errors, warnings = apa.audit(apa.collect_pins([path]))
    assert len(errors) == 1
    assert "no such commit" in errors[0]["reason"]


def test_fabricated_version_comment_is_a_warning(tmp_path, monkeypatch):
    """The other half of the defect: a real SHA labelled with a version that
    was never released still misinforms every future reader."""
    monkeypatch.setattr(apa, "_get", fake_api({REAL_SHA}, {"v7.0.1"}))
    path = write_workflow(tmp_path, f"      - uses: actions/upload-artifact@{REAL_SHA} # v8.0.0\n")
    errors, warnings = apa.audit(apa.collect_pins([path]))
    assert errors == []
    assert len(warnings) == 1
    assert "v8.0.0" in warnings[0]["reason"]


def test_bad_sha_short_circuits_version_check(tmp_path, monkeypatch):
    """A pin with a bad SHA is reported once, not twice — the comment is moot."""
    monkeypatch.setattr(apa, "_get", fake_api(set(), set()))
    path = write_workflow(tmp_path, f"      - uses: actions/upload-artifact@{FAKE_SHA} # v8.0.0\n")
    errors, warnings = apa.audit(apa.collect_pins([path]))
    assert len(errors) == 1 and warnings == []


def test_pin_without_comment_never_warns(tmp_path, monkeypatch):
    monkeypatch.setattr(apa, "_get", fake_api({REAL_SHA}, set()))
    path = write_workflow(tmp_path, f"      - uses: actions/checkout@{REAL_SHA}\n")
    errors, warnings = apa.audit(apa.collect_pins([path]))
    assert errors == [] and warnings == []


# ── refusing to guess ────────────────────────────────────────────────────────

def test_unreachable_api_exits_3_not_0(tmp_path, monkeypatch):
    """An instrument that greens out when it could not measure is the defect
    this whole gate exists to prevent."""
    def boom(path, cache):
        raise apa.Unreachable("network down")
    monkeypatch.setattr(apa, "_get", boom)
    monkeypatch.setattr(apa, "workflow_files", lambda: [
        write_workflow(tmp_path, f"      - uses: actions/checkout@{REAL_SHA} # v7.0.1\n")
    ])
    assert apa.main([]) == 3


def test_failing_gate_returns_1(tmp_path, monkeypatch):
    monkeypatch.setattr(apa, "_get", fake_api(set(), set()))
    monkeypatch.setattr(apa, "workflow_files", lambda: [
        write_workflow(tmp_path, f"      - uses: actions/upload-artifact@{FAKE_SHA} # v8.0.0\n")
    ])
    assert apa.main([]) == 1


def test_passing_gate_returns_0(tmp_path, monkeypatch):
    monkeypatch.setattr(apa, "_get", fake_api({REAL_SHA}, {"v7.0.1"}))
    monkeypatch.setattr(apa, "workflow_files", lambda: [
        write_workflow(tmp_path, f"      - uses: actions/checkout@{REAL_SHA} # v7.0.1\n")
    ])
    assert apa.main([]) == 0


def test_version_warning_alone_does_not_fail_the_gate(tmp_path, monkeypatch):
    monkeypatch.setattr(apa, "_get", fake_api({REAL_SHA}, set()))
    monkeypatch.setattr(apa, "workflow_files", lambda: [
        write_workflow(tmp_path, f"      - uses: actions/checkout@{REAL_SHA} # v9.9.9\n")
    ])
    assert apa.main([]) == 0


def test_no_workflows_is_a_usage_error(monkeypatch):
    monkeypatch.setattr(apa, "workflow_files", lambda: [])
    assert apa.main([]) == 4


# ── the live tree ────────────────────────────────────────────────────────────

def test_repo_workflows_are_discoverable():
    """Guards the discovery path itself: if this ever returns nothing, the gate
    would pass vacuously on every PR."""
    paths = apa.workflow_files()
    assert len(paths) > 10
    assert len(apa.collect_pins(paths)) > 50


def test_composite_actions_are_scanned():
    """`.github/actions/**/action.yml` was outside this tool's scan until
    2026-08-21. A composite action pins third-party actions exactly like a
    workflow does, and an unresolvable pin there fails the CALLING workflow at
    setup — the same invisible startup_failure, one level down. Found while
    chasing build-nats-workers, which kept failing at setup after every pin in
    .github/workflows/ already resolved."""
    paths = [str(p) for p in apa.workflow_files()]
    assert any("/.github/actions/" in p or p.startswith(".github/actions/")
               for p in paths), "composite actions are not being scanned"


def test_composite_action_pins_are_collected(tmp_path, monkeypatch):
    action = tmp_path / "action.yml"
    action.write_text(
        "runs:\n  using: composite\n  steps:\n"
        f"    - uses: docker/setup-buildx-action@{REAL_SHA} # v4\n",
        encoding="utf-8",
    )
    pins = apa.collect_pins([action])
    assert len(pins) == 1
    assert (pins[0]["owner"], pins[0]["repo"]) == ("docker", "setup-buildx-action")
