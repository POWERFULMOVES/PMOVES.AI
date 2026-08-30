# pmoves/tools/tests/test_validate_tac.py
"""Tests for the validate-tac ratchet.

The ratchet is the static-analyzer half of the PR #2373 + #2371 fix:
where PR #2373 made the runner fail-closed on unknown action.type at
EXECUTION time, this ratchet fails-closed at PR-merge time. Tests:

  1. Clean tree (only allowed types) → pass
  2. Unknown action.type → fail
  3. Unknown action.type IN baseline → acknowledged, not a failure
  4. No-action / null action / `~` action → pass (no assertion to validate)
  5. action: "free-string" → fail with <non-dict-action>
  6. Depth-first traversal catches nested unknown types
  7. --tree single-file mode works
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

RATCHET = (
    Path(__file__).resolve().parents[1] / "validate_tac.py"
)
PYTHON = sys.executable
TAC_DIR = Path(__file__).resolve().parents[2] / "configs" / "tac_trees"


def _write_tmp_tree(name: str, content: str) -> Path:
    target = TAC_DIR / f"test_validate_tac.{name}.tac.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


def _cleanup(path: Path) -> None:
    if path.exists():
        path.unlink()


def _run_ratchet(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [PYTHON, str(RATCHET), *args, "--json"],
        capture_output=True, text=True,
    )


def _run_ratchet_on_tree(file: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [PYTHON, str(RATCHET), "--tree", str(file), *args, "--json"],
        capture_output=True, text=True,
    )


def test_clean_tree_passes():
    payload = """
root:
  id: r
  task: root
  children:
    - id: clean
      task: ok
      action:
        type: file_exists
        target: pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md
"""
    path = _write_tmp_tree("clean", payload)
    try:
        r = _run_ratchet_on_tree(path)
        assert r.returncode == 0, r.stdout + r.stderr
        out = json.loads(r.stdout)
        assert out["problems"] == []
        assert out["failures"] == []
    finally:
        _cleanup(path)


def test_unknown_action_type_fails():
    payload = """
root:
  id: r
  task: root
  children:
    - id: bad
      task: ok
      action:
        type: make_coffee
        target: something
"""
    path = _write_tmp_tree("unknown", payload)
    try:
        r = _run_ratchet_on_tree(path)
        assert r.returncode == 1, r.stdout
        out = json.loads(r.stdout)
        assert any(p["type"] == "make_coffee" for p in out["failures"])
        assert any(p["node"] == "bad" for p in out["failures"])
    finally:
        _cleanup(path)


def test_baseline_acknowledges_known_unknowns():
    """The ratchet should NOT fail on a type that's in the baseline.

    The baseline lives at pmoves/configs/tac_trees/_known_unknowns.yaml
    (committed, reviewable). For this test, we write a temp tree that
    uses a type the baseline lists, and verify it's acknowledged.
    """
    payload = """
root:
  id: r
  task: root
  children:
    - id: shell-node
      task: ok
      action:
        type: shell
        command: ls
"""
    path = _write_tmp_tree("baselined", payload)
    try:
        r = _run_ratchet_on_tree(path)
        # The baseline ships 'shell' as acknowledged (72 nodes today),
        # so this should not be a ratchet failure even though 'shell'
        # is not in ALLOWED_ACTION_TYPES.
        assert r.returncode == 0, r.stdout
        out = json.loads(r.stdout)
        assert any(p["type"] == "shell" for p in out["acknowledged"])
        assert not any(p["type"] == "shell" for p in out["failures"])
    finally:
        _cleanup(path)


def test_no_action_or_null_action_passes():
    """A node with no `action` key, or `action: null`, is not an
    assertion — should not be flagged."""
    payload = """
root:
  id: r
  task: root
  children:
    - id: no-action
      task: nothing
    - id: null-action
      task: also nothing
      action: null
    - id: tilde-action
      task: also nothing
      action: ~
"""
    path = _write_tmp_tree("noaction", payload)
    try:
        r = _run_ratchet_on_tree(path)
        assert r.returncode == 0, r.stdout
        out = json.loads(r.stdout)
        assert out["problems"] == []
    finally:
        _cleanup(path)


def test_non_dict_action_fails():
    """`action: 'just-a-string'` should be flagged as <non-dict-action>."""
    payload = """
root:
  id: r
  task: root
  children:
    - id: free-string-action
      task: ok
      action: just-a-string
"""
    path = _write_tmp_tree("nondict", payload)
    try:
        r = _run_ratchet_on_tree(path)
        assert r.returncode == 1
        out = json.loads(r.stdout)
        assert any(p["type"] == "<non-dict-action>" for p in out["failures"])
    finally:
        _cleanup(path)


def test_nested_unknown_caught_by_dfs():
    """A bad type buried under 2 levels of children must still be caught."""
    payload = """
root:
  id: r
  task: root
  children:
    - id: lvl1
      task: t
      children:
        - id: lvl2
          task: t
          children:
            - id: lvl3-bad
              task: t
              action:
                type: make_tea
                target: anything
"""
    path = _write_tmp_tree("nested", payload)
    try:
        r = _run_ratchet_on_tree(path)
        assert r.returncode == 1
        out = json.loads(r.stdout)
        assert any(p["node"] == "lvl3-bad" and p["type"] == "make_tea" for p in out["failures"])
    finally:
        _cleanup(path)


def test_all_allowed_types_pass():
    """Each of file_exists, grep, command, http, manual must pass."""
    payload = """
root:
  id: r
  task: root
  children:
    - id: a
      task: t
      action: { type: file_exists, target: pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md }
    - id: b
      task: t
      action: { type: grep, target: pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md, pattern: Mavis }
    - id: c
      task: t
      action: { type: command, target: "python -c 'print(1)'" }
    - id: d
      task: t
      action: { type: http, url: http://127.0.0.1:9999/healthz }
    - id: e
      task: t
      action: { type: manual }
"""
    path = _write_tmp_tree("allowed_all", payload)
    try:
        r = _run_ratchet_on_tree(path)
        assert r.returncode == 0, r.stdout
        out = json.loads(r.stdout)
        assert out["problems"] == []
    finally:
        _cleanup(path)
