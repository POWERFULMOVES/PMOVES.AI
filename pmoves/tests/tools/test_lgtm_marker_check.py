"""Tests for the `lgtm[]` suppression-marker gate.

The gate exists because a marker that suppresses nothing reads as triage. A
gate that only ever passes has the same defect, so the tests here are mostly
negative controls: the cases that must FAIL are the point, and a change that
quietly stops detecting one of them would otherwise look green forever.

Two of these lock in behaviour that is easy to regress in opposite directions:
`test_prose_mention_is_not_a_finding` (over-matching would force a rewrite of
the one file that documents this defect) and `test_could_not_measure_is_not_a_pass`
(under-reporting -- returning 0 having judged nothing -- is the exact shape the
gate was built to remove).
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE = REPO_ROOT / "pmoves" / "tools" / "lgtm_marker_check.py"

spec = importlib.util.spec_from_file_location("lgtm_marker_check", MODULE)
assert spec and spec.loader
lmc = importlib.util.module_from_spec(spec)
sys.modules["lgtm_marker_check"] = lmc
spec.loader.exec_module(lmc)


# The fixtures below must contain marker strings without this FILE containing a
# marker -- otherwise the gate flags its own test suite and the only fixes are a
# self-exemption (an allowlist that rots) or deleting the coverage. CI caught
# exactly that on the first push of this branch: the gate ran clean locally
# while the test file was still untracked, then failed once committed, because
# `git ls-files` does not see untracked files. Assembling the pragma at runtime
# keeps the gate with ZERO exemptions, which is the property worth protecting.
P = "lgtm"


def _m(rule: str, comment: str = "#") -> str:
    """Build a marker string at runtime. Never write one literally in this file."""
    return f"{comment} {P}[{rule}]"


def _tree(monkeypatch, tmp_path, files: dict[str, str]):
    """Materialise `files` under tmp_path and point the gate at that tree."""
    for rel, body in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
    monkeypatch.setattr(lmc, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(lmc, "discover_tracked_files", lambda: sorted(files))


# ── the gate must say NO ──────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "line",
    [
        "x = 1  " + _m("py/path-injection"),
        "el.innerHTML = v; " + _m("js/xss-through-dom", "//"),
        f"foo()  # {P} [py/a-rule]",                      # space before bracket
        "foo()  " + _m("py/a-rule, js/b-rule"),           # multi-rule list
        "x = 1  " + _m("py/clear-text-storage-sensitive-data") + " -- with trailing prose",
    ],
)
def test_marker_forms_are_findings(monkeypatch, tmp_path, line):
    """Every spelling that a reader would take as a suppression must fail."""
    _tree(monkeypatch, tmp_path, {"pmoves/services/s.py": line + "\n"})
    assert lmc.main() == 1


def test_reintroducing_a_marker_fails_a_clean_tree(monkeypatch, tmp_path):
    """The regression this gate exists to prevent, end to end."""
    clean = {"pmoves/services/s.py": "x = 1  # plain explanatory comment\n"}
    _tree(monkeypatch, tmp_path, clean)
    assert lmc.main() == 0

    dirty = dict(clean)
    dirty["pmoves/services/s.py"] = "x = 1  " + _m("py/path-injection") + "\n"
    _tree(monkeypatch, tmp_path, dirty)
    assert lmc.main() == 1


def test_could_not_measure_is_not_a_pass(monkeypatch, tmp_path):
    """Discovery failure must exit 3, never 0.

    A gate that cannot enumerate the tree and reports OK anyway is the same
    class of defect as the marker: a green result that measured nothing.
    """
    monkeypatch.setattr(lmc, "REPO_ROOT", tmp_path)

    def _boom():
        raise subprocess.CalledProcessError(128, ["git", "ls-files", "-z"])

    monkeypatch.setattr(lmc, "discover_tracked_files", _boom)
    assert lmc.main() == 3


def test_empty_discovery_is_not_a_pass(monkeypatch, tmp_path):
    """Zero tracked files means the scan never ran -- exit 3, not 0."""
    monkeypatch.setattr(lmc, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(lmc, "discover_tracked_files", list)
    assert lmc.main() == 3


# ── the gate must say YES ─────────────────────────────────────────────────────

def test_prose_mention_is_not_a_finding(monkeypatch, tmp_path):
    """Documenting the defect must stay possible.

    pmoves/tools/github_secret_capacity_audit.py explains why this pragma does
    not work. If the gate flagged that, the only way to pass would be to delete
    the explanation -- so the gate would suppress the knowledge that the marker
    suppresses nothing.
    """
    _tree(monkeypatch, tmp_path, {
        "pmoves/tools/audit.py": (
            "# resolved by DISMISSING the alert with this justification, not by a\n"
            "# comment marker -- `# " + P + "[...]` is LGTM.com syntax that GitHub\n"
            "# scanning ignores. Do not copy it expecting suppression.\n"
        )
    })
    assert lmc.main() == 0


def test_backticked_rule_id_is_prose(monkeypatch, tmp_path):
    """A quoted, fully-spelled rule id is still someone explaining the syntax."""
    _tree(monkeypatch, tmp_path, {
        "pmoves/tools/audit.py": "# we used to write `" + _m("js/resource-exhaustion") + "` here\n"
    })
    assert lmc.main() == 0


def test_plain_rationale_comment_is_welcome(monkeypatch, tmp_path):
    """The reasoning is the valuable part; only the fake pragma is the defect."""
    _tree(monkeypatch, tmp_path, {
        "pmoves/tools/t.py": (
            "# env_content holds secret KEY NAMES only, values always left blank.\n"
            "# CodeQL py/clear-text-storage-sensitive-data flags it regardless.\n"
            "f.write(env_content)\n"
        )
    })
    assert lmc.main() == 0


def test_markdown_is_skipped(monkeypatch, tmp_path):
    """Historical narrative in the audit dashboard/AGNOTE must not be rewritten."""
    assert ".md" in lmc.SKIP_SUFFIXES


# ── the real tree ─────────────────────────────────────────────────────────────

def test_this_repository_is_clean():
    """The tree this test runs in carries no markers. Runs the real discovery."""
    assert lmc.main() == 0
