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

import json
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


# --------------------------------------------------------------------------
# Codex P2, review comment 3910500690 (2026-09-02): the remediation this gate
# prints could not work from the directory the gate actually runs in.
#
# Every road in is `make -C pmoves ...` (up-cipher, up-cipher-full,
# up-agents-stack, up-core-capable), so the process stands in `pmoves/` and
# `Pmoves-cipher` is a SIBLING of it. `git -C Pmoves-cipher fetch` from there is
# `fatal: cannot change to 'Pmoves-cipher'`; `git submodule update --checkout
# Pmoves-cipher` is `error: pathspec ... did not match`. The string was wrong on
# 100% of real invocations -- the only ones an operator ever sees.
#
# These tests do not assert on the SHAPE of the string. They run the tool as a
# CLI from the subdirectory, scrape the command it printed, and EXECUTE it
# there. A string that merely looks right is exactly what shipped, so looking
# right is not the property under test; being pasteable is.
# --------------------------------------------------------------------------

def _make_subdir(top: Path) -> Path:
    """`top/pmoves/` -- stands in for the cwd `make -C pmoves` runs the gate in."""
    d = top / "pmoves"
    d.mkdir(exist_ok=True)
    return d


def _cli(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run the tool as the Makefile does: a real process, with a real cwd."""
    return subprocess.run(
        [sys.executable, str(TOOLS_DIR / "submodule_build_pin_check.py"), *args],
        cwd=str(cwd), capture_output=True, text=True, check=False,
    )


def _printed_commands(stdout: str, verb: str) -> list[str]:
    return [
        line.strip()[len(verb) + 2:]
        for line in stdout.splitlines()
        if line.strip().startswith(verb + ": ")
    ]


def _sh(cmd: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    """Execute a printed command VERBATIM, in a shell, from `cwd`.

    The only env addition is protocol.file.allow, because git >= 2.38 refuses
    file:// submodule clones and this fixture's remote is a local path. That is
    a property of the fixture's transport, not of the command: the real
    Pmoves-cipher remote is https. It is passed through the ENVIRONMENT so the
    command string itself is still executed character-for-character.
    """
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "protocol.file.allow",
        "GIT_CONFIG_VALUE_0": "always",
    }
    return subprocess.run(
        cmd, shell=True, cwd=str(cwd), capture_output=True, text=True,
        check=False, env=env,
    )


def test_drift_remediation_pasted_from_the_make_subdir_heals_the_block(superproject):
    """The headline: scrape what it printed, paste it there, and it must work.

    Before the fix this failed with `fatal: cannot change to 'Pmoves-cipher'`
    (exit 128) and the drift was still there afterwards.
    """
    top, first = superproject
    _git("checkout", "-q", first, cwd=top / "Pmoves-cipher")
    sub = _make_subdir(top)

    blocked = _cli(sub, "Pmoves-cipher:Dockerfile.pmoves")
    assert blocked.returncode == 1, blocked.stdout + blocked.stderr
    cmds = _printed_commands(blocked.stdout, "fix")
    assert cmds, "a blocked operator was given nothing to run:\n" + blocked.stdout

    for cmd in cmds:
        done = _sh(cmd, cwd=sub)
        assert done.returncode == 0, (
            "the printed remediation failed when pasted from %s:\n  %s\n%s"
            % (sub, cmd, done.stdout + done.stderr)
        )

    healed = _cli(sub, "Pmoves-cipher:Dockerfile.pmoves")
    assert healed.returncode == 0, (
        "the remediation ran but did not clear the block:\n" + healed.stdout
    )


def test_uninitialized_remediation_pasted_from_the_make_subdir_heals_the_block(superproject):
    """Same defect, exit-3 lane -- not in the review, found by sweeping.

    `git submodule update --init Pmoves-cipher` from `pmoves/` is
    `error: pathspec ... did not match any file(s) known to git`, exit 1.
    """
    top, _ = superproject
    _git("submodule", "deinit", "-f", "Pmoves-cipher", cwd=top)
    sub = _make_subdir(top)

    blocked = _cli(sub, "Pmoves-cipher:Dockerfile.pmoves")
    assert blocked.returncode == 3, blocked.stdout + blocked.stderr
    cmds = _printed_commands(blocked.stdout, "run")
    assert cmds, "an unmeasured submodule left the operator nothing to run:\n" + blocked.stdout

    for cmd in cmds:
        done = _sh(cmd, cwd=sub)
        assert done.returncode == 0, (
            "the printed remediation failed when pasted from %s:\n  %s\n%s"
            % (sub, cmd, done.stdout + done.stderr)
        )

    healed = _cli(sub, "Pmoves-cipher:Dockerfile.pmoves")
    assert healed.returncode == 0, healed.stdout


def test_dirty_inspect_command_pasted_from_the_make_subdir_resolves(superproject):
    """The dirty lane's command is a read, so it must still RESOLVE from there.

    Its job is to show the operator the dirt. It gets no automatic
    `git stash --include-untracked`: on the real Pmoves-cipher that would also
    sweep the untracked runtime `data/`, and this tool's doctrine is that the
    human decides. So it is asserted to exit 0, not to heal.
    """
    top, _ = superproject
    (top / "Pmoves-cipher" / "src" / "app.ts").write_text("export const a = 999\n")
    sub = _make_subdir(top)

    blocked = _cli(sub, "Pmoves-cipher:Dockerfile.pmoves")
    assert blocked.returncode == 1
    assert "DIRTY" in blocked.stdout
    cmds = _printed_commands(blocked.stdout, "inspect")
    assert cmds, blocked.stdout
    for cmd in cmds:
        done = _sh(cmd, cwd=sub)
        assert done.returncode == 0, cmd + "\n" + done.stdout + done.stderr
        assert "src/app.ts" in done.stdout, (
            "the inspect command resolved but showed the wrong tree: " + done.stdout
        )


@pytest.mark.parametrize("spec", [
    "Pmoves-cipher:Dockerfile.absent",   # named Dockerfile unreadable
    "README",                            # path records no gitlink
])
def test_every_unmeasured_lane_prints_a_command_that_resolves_from_the_subdir(
    superproject, spec,
):
    """Sweep, not spot-fix: no exit-3 lane may print a path only the root can open.

    The property is DIRECTORY INDEPENDENCE, so it is measured directly rather
    than guessed from the shape of the string: run each printed command from two
    unrelated directories and require identical behaviour. Asserting "contains
    no relative token" would be wrong -- `git -C <abs> ls-tree HEAD README`
    carries a bare `README`, and that is a pathspec the `-C` anchor already
    resolves. What must not vary is the ANSWER.

    Both commands in this lane are reads, so running them twice is safe. A `cat`
    of a genuinely missing file exits non-zero from both directories, and that
    consistency is the point: it is a real finding, not a wrong-directory error.
    """
    top, _ = superproject
    sub = _make_subdir(top)
    elsewhere = top.parent
    got = _cli(sub, spec)
    assert got.returncode == 3, got.stdout + got.stderr

    cmds = _printed_commands(got.stdout, "inspect") + _printed_commands(got.stdout, "run")
    assert cmds, "an exit-3 lane told the operator nothing:\n" + got.stdout
    for cmd in cmds:
        from_sub = _sh(cmd, cwd=sub)
        from_elsewhere = _sh(cmd, cwd=elsewhere)
        assert (from_sub.returncode, from_sub.stdout) == \
               (from_elsewhere.returncode, from_elsewhere.stdout), (
            "the remediation means different things in different directories, so "
            "it depends on a cwd the tool does not control:\n  %s\n  from %s -> %s\n"
            "  from %s -> %s" % (cmd, sub, from_sub.returncode,
                                 elsewhere, from_elsewhere.returncode)
        )


def test_remediation_is_the_string_that_gets_printed(superproject):
    """No parallel copy: the field a test executes IS what the operator reads.

    Formatting the command a second time at print time is how the two would
    drift apart -- the same class of defect as the one being fixed here.
    """
    top, first = superproject
    _git("checkout", "-q", first, cwd=top / "Pmoves-cipher")
    sub = _make_subdir(top)

    as_json = _cli(sub, "Pmoves-cipher:Dockerfile.pmoves", "--json")
    finding = json.loads(as_json.stdout)["findings"][0]
    printed = _printed_commands(_cli(sub, "Pmoves-cipher:Dockerfile.pmoves").stdout, "fix")
    assert finding["remediation"] == printed
