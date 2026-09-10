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
import os
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


def _m(rule: str, comment: str = "#", token: str | None = None) -> str:
    """Build a marker string at runtime. Never write one literally in this file.

    `token` exists so the case-variant tests can build `LGTM[...]` / `Lgtm[...]`
    without this file containing either spelling literally -- the same
    zero-exemption property the lowercase fixtures protect.
    """
    return f"{comment} {token or P}[{rule}]"


def _git_init(root) -> None:
    """A throwaway repo that does not depend on the runner having a git identity."""
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    for k, v in (("user.email", "t@example.invalid"), ("user.name", "t")):
        subprocess.run(["git", "-C", str(root), "config", k, v], check=True)


def _tree(monkeypatch, tmp_path, files: dict[str, str]):
    """Materialise `files` under tmp_path and point the gate at that tree."""
    for rel, body in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
    monkeypatch.setattr(lmc, "REPO_ROOT", tmp_path)
    # Only the git-plumbing half of discovery is stubbed. `is_judgeable` -- the
    # real scope predicate -- still runs, so a fixture the gate is supposed to
    # skip is actually skipped here rather than merely asserted about.
    monkeypatch.setattr(
        lmc, "discover_tracked_files",
        lambda: [f for f in sorted(files) if lmc.is_judgeable(f)],
    )


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


@pytest.mark.parametrize("rel", ["docs/AUDIT.md", "docs/n.rst", "docs/n.txt", "docs/N.MD"])
def test_prose_suffixes_are_skipped(monkeypatch, tmp_path, rel):
    """Historical narrative in the audit dashboard/AGNOTE must not be rewritten.

    Asserted through main() on a real fixture rather than over the constant:
    `".md" in SKIP_SUFFIXES` is true even if nothing ever consults the set.
    """
    _tree(monkeypatch, tmp_path, {
        rel: "we added " + _m("js/resource-exhaustion") + " here\n",
        # a judgeable sibling: an all-skipped tree is empty discovery, which is
        # correctly exit 3, and would pass this test for the wrong reason.
        "pmoves/services/s.py": "x = 1\n",
    })
    assert lmc.main() == 0


# ── case is not an evasion, it is typing (PR #2857 review, P2) ────────────────

@pytest.mark.parametrize("token", ["LGTM", "Lgtm", "lGtM"])
def test_marker_case_variants_are_findings(monkeypatch, tmp_path, token):
    """`# LGTM[py/x]` suppresses exactly as much as `# lgtm[py/x]`: nothing.

    The matcher was case-SENSITIVE while the cheap-reject beside it already used
    `text.lower()`, so half of an intended case-insensitive design shipped. An
    uppercase marker is the single most likely real spelling to reach a gate
    whose whole job is catching this comment -- nobody has to be evading
    anything for it to happen.
    """
    _tree(monkeypatch, tmp_path, {
        "pmoves/services/s.py": "x = 1  " + _m("py/path-injection", token=token) + "\n"
    })
    assert lmc.main() == 1


def test_backticked_prose_is_still_prose_in_any_case(monkeypatch, tmp_path):
    """Case-insensitivity must not turn the documentation exemption into a finding."""
    _tree(monkeypatch, tmp_path, {
        "pmoves/tools/audit.py": "# we used to write `" + _m("js/x", token="LGTM") + "` here\n"
    })
    assert lmc.main() == 0


# ── a file we could not read is not a clean file (PR #2857 review, P2) ────────

@pytest.mark.skipif(sys.platform == "win32", reason="POSIX mode bits")
@pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0,
                    reason="root ignores the read bit, so chmod 000 proves nothing")
def test_unreadable_file_is_not_counted_clean(monkeypatch, tmp_path):
    """An unopenable tracked file must exit 3, never 0.

    Before this, `except (OSError, ValueError): return []` swallowed the failure
    AND the file still counted toward the "N tracked files" success line -- a
    green result that measured nothing, which is the exact defect the module
    docstring names.
    """
    _tree(monkeypatch, tmp_path, {
        "pmoves/services/s.py": "x = 1  " + _m("py/path-injection") + "\n"
    })
    target = tmp_path / "pmoves" / "services" / "s.py"
    target.chmod(0o000)
    try:
        assert lmc.main() == 3
    finally:
        target.chmod(0o644)


def test_unreadable_file_does_not_mask_a_real_finding(monkeypatch, tmp_path):
    """Findings still print when another file was unmeasurable; exit stays non-zero."""
    _tree(monkeypatch, tmp_path, {
        "pmoves/services/a.py": "x = 1  " + _m("py/path-injection") + "\n",
        "pmoves/services/b.py": "y = 2\n",
    })
    monkeypatch.setattr(lmc, "scan", _raise_on("pmoves/services/b.py", lmc.scan))
    assert lmc.main() == 1


def _raise_on(bad: str, real):
    def _scan(path: str):
        if path == bad:
            raise lmc.UnreadableFile(path, PermissionError(13, "Permission denied"))
        return real(path)
    return _scan


# ── scope is reported honestly (PR #2857 review, P2) ─────────────────────────

def test_success_line_reports_only_what_was_read(monkeypatch, tmp_path, capsys):
    """The count must be files OPENED, and submodule scope must be stated."""
    _tree(monkeypatch, tmp_path, {"pmoves/services/s.py": "x = 1\n"})
    assert lmc.main() == 0
    out = capsys.readouterr().out
    assert "Read 1 tracked file(s)" in out
    assert "OUT OF SCOPE" in out


def test_discovery_excludes_submodule_gitlinks(tmp_path, monkeypatch):
    """Gitlinks are commit pointers, not files -- never counted as scanned.

    Fabricated with `update-index --cacheinfo` so this does not need a real
    submodule checkout.
    """
    _git_init(tmp_path)
    (tmp_path / "real.py").write_text("x = 1\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "real.py"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", "seed"], check=True)
    sha = subprocess.run(["git", "-C", str(tmp_path), "rev-parse", "HEAD"],
                         capture_output=True, text=True, check=True).stdout.strip()
    subprocess.run(
        ["git", "-C", str(tmp_path), "update-index", "--add",
         "--cacheinfo", f"160000,{sha},sub/mod"],
        check=True,
    )
    monkeypatch.setattr(lmc, "REPO_ROOT", tmp_path)
    found = lmc.discover_tracked_files()
    assert "real.py" in found
    assert "sub/mod" not in found


def test_no_gitlink_is_counted_in_the_real_tree():
    """Same property, asserted against the repository this actually runs in."""
    tracked = lmc.discover_tracked_files()
    raw = subprocess.run(
        ["git", "ls-files", "-s", "-z"], cwd=str(lmc.REPO_ROOT),
        capture_output=True, check=True,
    ).stdout.decode("utf-8", errors="surrogateescape")
    gitlinks = {
        rec.split("\t", 1)[1]
        for rec in raw.split("\0")
        if rec and rec.split(" ", 1)[0] == lmc.GITLINK_MODE
    }
    assert gitlinks, "expected this repo to track submodules; test would be vacuous"
    assert not gitlinks.intersection(tracked)


# ── skip lists match path SEGMENTS, not substrings (PR #2857 review, P3) ──────

def test_myvendor_is_not_vendor(tmp_path, monkeypatch):
    """`myvendor/` is our code. Substring matching silently excluded it.

    Not hypothetical: on the real tree this bug hid 12 tracked, hand-written
    launcher scripts under `pmoves/docs/ARTSTUFF/Ultimate-TTS-Studio.git/`,
    because the substring `.git/` matched that directory name.
    """
    _git_init(tmp_path)
    for rel in ("myvendor/a.py", "vendor/b.py", "x.git/c.py", "node_modules/d.js"):
        f = tmp_path / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("x = 1\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=True)
    monkeypatch.setattr(lmc, "REPO_ROOT", tmp_path)
    found = lmc.discover_tracked_files()
    assert "myvendor/a.py" in found          # was silently skipped
    assert "x.git/c.py" in found             # was silently skipped
    assert "vendor/b.py" not in found        # real vendored tree, still skipped
    assert "node_modules/d.js" not in found


# ── the backtick exemption drops the SPAN, not the line (PR #2857, P3) ───────

def test_backtick_decoy_does_not_hide_a_real_marker(monkeypatch, tmp_path):
    """A quoted mention sharing a line with a live marker must not launder it."""
    line = ("x = 1  # see `" + _m("js/foo") + "` above  "
            + _m("py/path-injection") + "\n")
    _tree(monkeypatch, tmp_path, {"pmoves/services/s.py": line})
    assert lmc.main() == 1


# ── comment styles beyond #, //, --, /* (PR #2857 review, P3) ────────────────

@pytest.mark.parametrize("comment", ["%", ";"])
def test_other_comment_prefixes_are_findings(monkeypatch, tmp_path, comment):
    """MATLAB/Erlang `%` and ini/Lisp `;` markers mislead a reader identically."""
    _tree(monkeypatch, tmp_path, {
        "pmoves/tools/t.cfg": "k = v  " + _m("py/a-rule", comment) + "\n"
    })
    assert lmc.main() == 1


# ── the real tree ─────────────────────────────────────────────────────────────

def test_this_repository_is_clean():
    """The tree this test runs in carries no markers. Runs the real discovery."""
    assert lmc.main() == 0
