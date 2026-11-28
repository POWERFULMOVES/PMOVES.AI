"""Ratchet: the launch gate counts only MEASURED passes.

Until 2026-11-27 scripts/validate_launch_layout.py returned True for every
`manual` node and for any `pytest`/`script` node whose file merely existed,
which read 33/45 on a tree that measured 24/45. These tests pin the three
verdicts so a typed-in green cannot come back.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "scripts" / "validate_launch_layout.py"


def _load():
    spec = importlib.util.spec_from_file_location("validate_launch_layout", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    # @dataclass resolves annotations through sys.modules[cls.__module__];
    # an unregistered module makes that lookup None and collection crashes.
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


V = _load()


def test_manual_is_never_a_pass():
    verdict, _ = V.check_manual("someone looked at it")
    assert verdict == V.UNVERIFIED


def test_present_test_file_is_not_a_passing_test():
    verdict, detail = V.check_pytest_file("scripts/validate_launch_layout.py")
    assert verdict == V.UNVERIFIED
    assert "NOT RUN" in detail


def test_missing_test_file_still_fails():
    verdict, _ = V.check_pytest_file("pmoves/tests/does_not_exist_xyz.py")
    assert verdict == V.FAIL


def test_make_target_no_run_is_unverified(monkeypatch):
    monkeypatch.setattr(V, "RUN_MAKE_TARGETS", False)
    verdict, _ = V.check_make_target({"target": "docs-reconcile-check"})
    assert verdict == V.UNVERIFIED


def test_gate_fails_when_blocking_nodes_are_only_unverified(tmp_path):
    tac = {
        "root": {"id": "r", "children": [{
            "id": "stage-0",
            "children": [{"id": "stage-0.a",
                          "action": {"type": "manual", "expect": "x"}}],
        }]},
        "gates": {"launch-blocking": {"requires": ["stage-0"]}},
    }
    ctx = V.ValidationContext(blocking_stages=V.collect_blocking_stages(tac))
    V.walk_nodes(tac["root"], None, ctx)
    counts = V.tally(ctx, blocking=True)
    assert counts[V.PASS] == 0 and counts[V.UNVERIFIED] == 1
    assert counts[V.PASS] != counts["total"]  # gate FAILS


def test_launch_tree_declares_stage_12_blocking():
    tac = yaml.safe_load(
        (REPO_ROOT / "pmoves/configs/tac_trees/pmoves-launch-readiness.tac.yaml")
        .read_text(encoding="utf-8"))
    assert "stage-12" in V.collect_blocking_stages(tac)
    for node in tac["root"]["children"]:
        for child in node.get("children") or []:
            t = (child.get("action") or {}).get("type")
            assert t in V.CHECK_DISPATCH, f"{child['id']}: unknown type {t}"
