"""Tests for pmoves/tools/submodule_build_pin_check.py

The defect this gate exists to stop is invisible to CI by construction: a
submodule WORKTREE drifted off the recorded gitlink is node-local state. A
fresh clone is always correct, so nothing in the repo and nothing in a
pipeline can see it. On B850 that let cipher's MCP transport answer

    HTTP 400  InternalServerError: stream is not readable

for two weeks while `main` carried the fix, because the build road's
`build.context` is the worktree and docker reads files, not gitlinks.

So these tests build REAL git repositories with a real gitlink and drift them
on purpose. Mocking `git` here would test the mock, not the property.

The property that must never regress: a submodule the check could not read is
NOT reported as clean. Every "could not measure" case exits 3, and 3 wins over
any number of clean siblings.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS_DIR))

import submodule_build_pin_check as sbpc  # noqa: E402


def _git(*args: str, cwd: Path) -> str:
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
        # A developer's own global config must not decide whether this passes.
        "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull,
    }
    out = subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True,
        check=True, env=env,
    )
    return out.stdout.strip()


@pytest.fixture
def superproject(tmp_path: Path) -> tuple[Path, str]:
    """A superproject with one real submodule, pinned at its second commit.

    Returns (superproject_path, first_commit_sha) — the sha is what the drift
    tests check the worktree back to.
    """
    sub = tmp_path / "sub-origin"
    sub.mkdir()
    _git("init", "-q", "-b", "main", cwd=sub)
    (sub / "f.txt").write_text("one\n")
    # Shaped like Pmoves-cipher: a Dockerfile that copies SOME of the worktree.
    # `f.txt` is deliberately outside every COPY, so it is the "dirt docker will
    # never read" case; `src/` is inside, so it is the "dirt docker compiles" case.
    (sub / "package.json").write_text("{}\n")
    (sub / "src").mkdir()
    (sub / "src" / "app.ts").write_text("export const a = 1\n")
    (sub / "Dockerfile.pmoves").write_text(
        "FROM node:22-slim AS builder\n"
        "WORKDIR /app\n"
        "COPY package.json ./\n"
        "COPY src/ ./src/\n"
        "FROM node:22-slim\n"
        "COPY --from=builder /app/dist ./dist\n"
    )
    _git("add", "-A", cwd=sub)
    _git("commit", "-qm", "one", cwd=sub)
    first = _git("rev-parse", "HEAD", cwd=sub)
    (sub / "f.txt").write_text("two\n")
    _git("commit", "-qam", "two", cwd=sub)

    top = tmp_path / "top"
    top.mkdir()
    _git("init", "-q", "-b", "main", cwd=top)
    (top / "README").write_text("x\n")
    _git("add", "README", cwd=top)
    _git("commit", "-qm", "init", cwd=top)
    _git("-c", "protocol.file.allow=always", "submodule", "add", "-q",
         str(sub), "Pmoves-cipher", cwd=top)
    _git("commit", "-qm", "add submodule", cwd=top)

    return top, first


def _run(cwd: Path, *paths: str) -> tuple[int, list[dict]]:
    """Invoke the check with cwd set — the tool anchors on CWD by design."""
    prev = Path.cwd()
    os.chdir(cwd)
    try:
        # REPO_ROOT is resolved at import time; re-resolve for this cwd.
        sbpc.REPO_ROOT = sbpc._repo_root()
        return sbpc.check(list(paths))
    finally:
        os.chdir(prev)


def test_synced_worktree_is_clean(superproject):
    top, _ = superproject
    code, findings = _run(top, "Pmoves-cipher")
    assert code == 0
    assert findings[0]["status"] == "clean"
    assert findings[0]["gitlink"] == findings[0]["worktree"]


def test_drifted_worktree_is_reported(superproject):
    """The exact B850 shape: worktree behind the pin, nothing else wrong."""
    top, first = superproject
    _git("checkout", "-q", first, cwd=top / "Pmoves-cipher")
    code, findings = _run(top, "Pmoves-cipher")
    assert code == 1
    assert findings[0]["status"] == "drift"
    assert findings[0]["gitlink"] != findings[0]["worktree"]


def test_drift_is_detected_when_worktree_is_AHEAD_too(superproject):
    """Ahead is drift as well.

    An unpushed local commit is the friendlier-looking case and exactly as
    unreproducible: the image would carry a commit that exists on one disk.
    """
    top, _first = superproject
    subdir = top / "Pmoves-cipher"
    (subdir / "f.txt").write_text("three\n")
    _git("commit", "-qam", "three", cwd=subdir)
    code, _ = _run(top, "Pmoves-cipher")
    assert code == 1


def test_uninitialized_submodule_is_unmeasured_not_clean(superproject):
    """The whole point of the exit-3 lane.

    An empty submodule directory reads as "no drift found" to any check that
    only compares what it managed to read.
    """
    top, _ = superproject
    subdir = top / "Pmoves-cipher"
    (subdir / ".git").unlink()
    code, findings = _run(top, "Pmoves-cipher")
    assert code == 3
    assert findings[0]["status"] == "unmeasured"


def test_path_that_is_not_a_gitlink_is_unmeasured(superproject):
    """A typo'd or renamed path must not silently pass."""
    top, _ = superproject
    code, findings = _run(top, "README")
    assert code == 3
    assert findings[0]["status"] == "unmeasured"


def test_unmeasured_beats_clean_siblings(superproject):
    """3 takes precedence. One readable submodule cannot vouch for another."""
    top, _ = superproject
    code, findings = _run(top, "Pmoves-cipher", "README")
    assert code == 3
    assert {f["status"] for f in findings} == {"clean", "unmeasured"}


def test_outside_a_git_tree_returns_none_rather_than_guessing(tmp_path: Path):
    prev = Path.cwd()
    os.chdir(tmp_path)
    try:
        assert sbpc._repo_root() is None
    finally:
        os.chdir(prev)


# --------------------------------------------------------------------------
# F1 (review 2026-09-02): a DIRTY worktree whose HEAD matches the pin.
#
# `git submodule status` shows no `+` in this state, so the whole `+`-prefix
# family is blind to it — and it is the single most common real drift: a
# developer mid-change. `Pmoves-cipher/Dockerfile.pmoves` does `COPY src/ ./src/`
# and the submodule has no `.dockerignore`, so that edit is compiled into the
# image. HEAD matching the pin does not make the build reproducible; only the
# FILES matching do, and files are what docker reads.
# --------------------------------------------------------------------------

def test_dirty_tracked_file_at_the_pin_is_not_clean(superproject):
    """The F1 shape: HEAD == pin, tracked file under a COPY'd path edited."""
    top, _ = superproject
    (top / "Pmoves-cipher" / "src" / "app.ts").write_text("export const a = 999\n")
    code, findings = _run(top, "Pmoves-cipher:Dockerfile.pmoves")
    assert findings[0]["gitlink"] == findings[0]["worktree"], (
        "precondition: HEAD must still match the pin, or this tests drift instead"
    )
    assert findings[0]["status"] == "dirty"
    assert code == 1


def test_untracked_file_under_a_copied_path_is_not_clean(superproject):
    """`COPY src/ ./src/` with no .dockerignore copies untracked files too."""
    top, _ = superproject
    (top / "Pmoves-cipher" / "src" / "sneak.ts").write_text("export const b = 2\n")
    code, findings = _run(top, "Pmoves-cipher:Dockerfile.pmoves")
    assert findings[0]["status"] == "dirty"
    assert code == 1


def test_dirty_is_still_caught_with_no_dockerfile_named(superproject):
    """Without a Dockerfile the tool cannot narrow, so it watches the whole tree.

    Widest answer, not the most convenient one: a build road that does not tell
    the gate what docker reads gets the conservative check.
    """
    top, _ = superproject
    (top / "Pmoves-cipher" / "f.txt").write_text("edited\n")
    code, findings = _run(top, "Pmoves-cipher")
    assert findings[0]["status"] == "dirty"
    assert code == 1


def test_dirt_outside_every_COPY_does_not_block(superproject):
    """The reason this is narrowed rather than whole-tree for cipher.

    The REAL Pmoves-cipher worktree on B850 carries an untracked `data/` — a
    runtime artifact no COPY reads. A gate that blocks on it would be switched
    off with CIPHER_BUILD_PIN=warn inside a day, which is the failure mode this
    tool's own docstring warns about for submodule_integrity.py.
    """
    top, _ = superproject
    (top / "Pmoves-cipher" / "data").mkdir()
    (top / "Pmoves-cipher" / "data" / "blob.bin").write_text("x\n")
    (top / "Pmoves-cipher" / "f.txt").write_text("edited\n")
    code, findings = _run(top, "Pmoves-cipher:Dockerfile.pmoves")
    assert findings[0]["status"] == "clean", findings
    assert code == 0


def test_dirty_and_drifted_reports_the_drift(superproject):
    """Both wrong at once must not read as only-dirty; drift is the bigger claim."""
    top, first = superproject
    _git("checkout", "-q", first, cwd=top / "Pmoves-cipher")
    (top / "Pmoves-cipher" / "src" / "app.ts").write_text("export const a = 999\n")
    code, findings = _run(top, "Pmoves-cipher:Dockerfile.pmoves")
    assert findings[0]["status"] == "drift"
    assert findings[0]["dirty"] is True
    assert code == 1


def test_named_dockerfile_that_is_missing_is_unmeasured(superproject):
    """Refusing to guess, extended to the build context.

    If the tool cannot read which files docker copies it cannot say the build is
    reproducible. Falling back to "check nothing" would be the exact
    read-nothing-report-clean failure the exit-3 lane exists to stop.
    """
    top, _ = superproject
    code, findings = _run(top, "Pmoves-cipher:Dockerfile.absent")
    assert code == 3
    assert findings[0]["status"] == "unmeasured"
    assert "Dockerfile.absent" in findings[0]["detail"]


def test_copy_of_the_whole_context_widens_back_to_the_whole_tree(superproject):
    """`COPY . .` means every file is a build input, including f.txt."""
    top, _ = superproject
    sub = top / "Pmoves-cipher"
    (sub / "Dockerfile.wide").write_text("FROM scratch\nCOPY . /app\n")
    (sub / "f.txt").write_text("edited\n")
    code, findings = _run(top, "Pmoves-cipher:Dockerfile.wide")
    assert findings[0]["status"] == "dirty"
    assert code == 1


# --------------------------------------------------------------------------
# F5 (review 2026-09-02): the 160000/commit guard in recorded_gitlink() was
# unbound by any test — mutation M4 (drop the guard) survived the whole suite.
# `test_path_that_is_not_a_gitlink_is_unmeasured` passes for the wrong reason:
# `README` has no `.git`, so it lands in the unmeasured lane via worktree_head()
# and never reaches the guard. This binds it with a path that DOES have a `.git`
# but is recorded as a tree, where dropping the guard produces a "DRIFT" whose
# "recorded gitlink" is a tree sha — nonsense, and a false block.
# --------------------------------------------------------------------------

def test_tracked_directory_holding_a_nested_git_is_unmeasured_not_drift(superproject):
    top, _ = superproject
    plain = top / "plaindir"
    plain.mkdir()
    (plain / "keep.txt").write_text("k\n")
    _git("add", "plaindir/keep.txt", cwd=top)
    _git("commit", "-qm", "plain dir", cwd=top)
    # A nested repo checked out under a path the superproject records as a TREE.
    # It must have a COMMIT: with an unborn HEAD the path falls into the
    # unmeasured lane via worktree_head() and the guard is never reached --
    # which is exactly how the original test passed for the wrong reason.
    _git("init", "-q", "-b", "main", cwd=plain)
    (plain / "inner.txt").write_text("i\n")
    _git("add", "inner.txt", cwd=plain)
    _git("commit", "-qm", "inner", cwd=plain)
    assert sbpc.run_git("rev-parse", "HEAD", cwd=plain).returncode == 0, (
        "precondition: the nested repo must resolve a HEAD, or the guard is untested"
    )

    entry = _git("ls-tree", "HEAD", "plaindir", cwd=top)
    assert entry.split()[1] == "tree", "precondition: recorded as a tree, not a gitlink"

    code, findings = _run(top, "plaindir")
    assert findings[0]["status"] == "unmeasured", (
        "a tree sha is not a pin; reporting DRIFT against one is a false block"
    )
    assert code == 3


def test_a_dockerfile_that_only_copies_from_a_stage_is_unmeasured(superproject):
    """`COPY --from=<stage>` reads a previous stage, never the build context.

    Cipher's runtime stage copies /app/dist and /app/node_modules from the
    builder; neither is a worktree file. Counting those as build inputs would
    narrow the check to paths that cannot exist and report a confident `clean`
    about a tree nobody looked at.
    """
    top, _ = superproject
    sub = top / "Pmoves-cipher"
    (sub / "Dockerfile.stageonly").write_text(
        "FROM scratch AS builder\nFROM scratch\nCOPY --from=builder /app/dist ./dist\n"
    )
    (sub / "src" / "app.ts").write_text("export const a = 999\n")
    code, findings = _run(top, "Pmoves-cipher:Dockerfile.stageonly")
    assert findings[0]["status"] == "unmeasured"
    assert code == 3


def test_git_status_failing_is_unmeasured_not_clean(superproject):
    """The silent-handler case: the dirty read fails, so nothing is known.

    Not mocked. A corrupt `.git/index` is a real shape (an interrupted git
    process leaves one), and it splits the two reads: `rev-parse HEAD` reads
    refs and still succeeds, so HEAD == pin, while `git status` exits 128. If
    that error were swallowed as "no dirt found", the gate would print a
    confident `clean` off a read that never happened -- which is the whole
    reason the exit-3 lane exists.
    """
    top, _ = superproject
    sub = top / "Pmoves-cipher"
    gitfile = (sub / ".git").read_text().split("gitdir:", 1)[1].strip()
    (sub / gitfile / "index").write_bytes(b"garbage")

    assert sbpc.run_git("rev-parse", "HEAD", cwd=sub).returncode == 0, (
        "precondition: HEAD must still resolve, or this tests the wrong lane"
    )
    code, findings = _run(top, "Pmoves-cipher:Dockerfile.pmoves")
    assert findings[0]["status"] == "unmeasured"
    assert code == 3
