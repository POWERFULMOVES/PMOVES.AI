"""Gate: an integration image must be built from the RECORDED commit, not from
a moving branch.

WHY THIS GATE EXISTS
--------------------
`integrations-ghcr.yml` resolved a fork-backed entry's build context with

    git clone --depth=1 --branch "$cfg_ref" "$cfg_url" integration-src

`$cfg_ref` is the fork's `PMOVES.AI-Edition-Hardened` branch -- a MOVING
ref. The image the lane publishes is therefore not reproducible from the
repository state: two runs a week apart produce two different artifacts under
the same tag, and no commit in PMOVES.AI names what was built.

PMOVES.AI already records the answer for every fork it tracks as a submodule:
the **gitlink**. `build-images.yml` already builds from those pins -- it
checks out with `submodules: recursive` and builds `github.workspace/<repo>`,
which IS the recorded commit. `integrations-ghcr.yml` did not.

WHAT THIS TEST DOES
-------------------
It drives the REAL code, in two links:

  * `pmoves/tools/resolve_recorded_pin.py` is executed against the REAL tree
    and must return the commit that `git ls-tree -r HEAD` records;
  * the workflow's REAL steps -- sliced out of the workflow file -- are
    executed under bash: the resolution step must emit the recorded commit,
    and the prepare step must CHECK OUT that commit rather than the branch.

It does NOT re-type the resolution or the checkout in Python. A test that
re-types the expression it is testing proves only that the author believed the
expression -- which is the failure mode this whole gate exists to catch.

FAIL CLOSED
-----------
The resolver's exit codes are a contract, and the workflow step must honour
them: 0 resolved, 3 not tracked (a branch is then the only source), 4
ambiguous, 5 declared-but-unrecorded, 6 unreadable. 4, 5 and 6 must FAIL the
step -- a build that resolves a different commit than the recorded one is the
defect this gate exists to remove, so it must not be papered over with a
fallback.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from pmoves.tools.bash_resolver import find_bash  # never System32's WSL stub

REPO_ROOT = Path(__file__).resolve().parents[3]
TOOL = REPO_ROOT / "pmoves" / "tools" / "resolve_recorded_pin.py"
WORKFLOW_FILE = REPO_ROOT / ".github" / "workflows" / "integrations-ghcr.yml"

FORK_URL = "https://github.com/POWERFULMOVES/PMOVES-Open-Notebook.git"
FORK_SUBMODULE = "PMOVES-Open-Notebook"

EXIT_RESOLVED = 0
EXIT_NOT_TRACKED = 3
EXIT_AMBIGUOUS = 4
EXIT_INCONSISTENT = 5
EXIT_UNREADABLE = 6

# The workflow step that resolves the commit, and the step that uses it.
RESOLVE_STEP = "Resolve the recorded commit"
PREPARE_STEP = "Prepare integration source"


def _bash() -> str | None:
    """A usable bash, or None.

    Delegates to the house resolver. `shutil.which("bash")` is NOT enough: on
    Windows it returns `C:\Windows\System32\bash.exe` -- the WSL
    launcher -- before PATH is ever consulted, so the child would silently run
    in a different OS. `pmoves/tests/test_no_bare_bash_argv.py` gates that.
    """
    return find_bash()


def _workflow():
    yaml = pytest.importorskip("yaml")
    assert WORKFLOW_FILE.exists(), f"the workflow must exist: {WORKFLOW_FILE}"
    workflow = yaml.safe_load(WORKFLOW_FILE.read_text(encoding="utf-8"))
    assert isinstance(workflow, dict), "the workflow must parse into a mapping"
    return workflow


def _step_run_block(job_name: str, step_name: str) -> str:
    """A named step's shell, sliced out of the workflow file.

    FAIL CLOSED: if the step cannot be located, this raises rather than
    returning something vacuous.
    """
    workflow = _workflow()
    jobs = workflow.get("jobs") or {}
    assert job_name in jobs, f"the workflow has no job {job_name!r}"
    for step in (jobs[job_name].get("steps") or []):
        step = step or {}
        if step.get("name") == step_name:
            run = str(step.get("run") or "")
            assert run, f"step {step_name!r} in {job_name!r} has no run block"
            return run
    raise AssertionError(
        f"the step {step_name!r} was not found in job {job_name!r}; the "
        f"workflow's shape changed, and the gate would pass vacuously"
    )


def _recorded_pin() -> str:
    """The commit PMOVES.AI records for the fork, read from the tree."""
    out = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-tree", "-r", "HEAD", "--", FORK_SUBMODULE],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert out.returncode == 0, out.stderr
    fields = out.stdout.strip().split()
    assert fields and fields[0] == "160000", (
        f"{FORK_SUBMODULE} is not a submodule in this tree: {out.stdout!r}"
    )
    return fields[2]


def _run_tool(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(TOOL), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(cwd) if cwd else None, timeout=300,
    )


# ---------------------------------------------------------------------------
# The tool, against the REAL tree
# ---------------------------------------------------------------------------


def test_the_tool_resolves_the_recorded_commit_for_a_tracked_fork() -> None:
    """The whole point: the fork URL resolves to the commit the tree records."""
    result = _run_tool("--url", FORK_URL)
    assert result.returncode == EXIT_RESOLVED, (
        f"the resolver failed for a tracked fork (exit {result.returncode})\n"
        f"{result.stdout}\n{result.stderr}"
    )
    assert result.stdout.strip() == _recorded_pin(), (
        f"the resolver returned {result.stdout.strip()!r}; the tree records "
        f"{_recorded_pin()!r}"
    )


def test_the_tool_reports_an_untracked_fork_as_not_tracked() -> None:
    """Exit 3 is NOT an error: nothing is recorded, so a branch is the source.

    It must be distinguishable from the failure codes, or the workflow cannot
    tell "there is no pin" from "the pin cannot be resolved".
    """
    result = _run_tool("--url", "https://github.com/POWERFULMOVES/not-a-submodule.git")
    assert result.returncode == EXIT_NOT_TRACKED, (
        f"an untracked fork returned exit {result.returncode}; the workflow "
        f"cannot tell that apart from a failure\n{result.stdout}\n{result.stderr}"
    )
    assert result.stdout.strip() == "", (
        f"an untracked fork produced a commit: {result.stdout!r}"
    )


def test_the_tool_fails_closed_when_the_tree_cannot_be_read(tmp_path: Path) -> None:
    """A resolver that cannot read its input must FAIL, not return a guess."""
    result = _run_tool("--url", FORK_URL, "--repo-root", str(tmp_path))
    assert result.returncode == EXIT_UNREADABLE, (
        f"an unreadable repository returned exit {result.returncode}\n"
        f"{result.stdout}\n{result.stderr}"
    )
    assert result.stdout.strip() == "", (
        f"an unreadable repository still produced a commit: {result.stdout!r}"
    )


def test_the_tool_fails_closed_when_a_declared_submodule_has_no_gitlink(
    tmp_path: Path,
) -> None:
    """A submodule that declares a fork but records no commit is INCONSISTENT.

    The tool must not fall back to "not tracked" (3) here: the repository says
    it tracks this fork, so the absence of a commit is a defect to surface,
    not a fact to paper over.

    The fixture is a REAL repository -- a directory with a `.gitmodules` and no
    git would fail earlier, with "the tree could not be read", which is a
    different failure with a different exit code.
    """
    subprocess.run(
        ["git", "init", "-q", str(tmp_path)],
        capture_output=True, text=True, timeout=120,
    )
    (tmp_path / ".gitmodules").write_text(
        '[submodule "PMOVES-Ghost"]\n'
        "\tpath = PMOVES-Ghost\n"
        "\turl = https://github.com/POWERFULMOVES/PMOVES-Ghost.git\n",
        encoding="utf-8",
    )
    subprocess.run(
        ["git", "-C", str(tmp_path), "add", ".gitmodules"],
        capture_output=True, text=True, timeout=120,
    )
    commit = subprocess.run(
        [
            "git", "-C", str(tmp_path),
            "-c", "user.email=gate@example.invalid",
            "-c", "user.name=gate",
            "commit", "-q", "-m", "declare a submodule without recording it",
        ],
        capture_output=True, text=True, timeout=120,
    )
    assert commit.returncode == 0, commit.stderr

    result = _run_tool(
        "--url", "https://github.com/POWERFULMOVES/PMOVES-Ghost.git",
        "--repo-root", str(tmp_path),
    )
    assert result.returncode == EXIT_INCONSISTENT, (
        f"a declared-but-unrecorded submodule returned exit {result.returncode}; "
        f"it must be distinguishable from 'not tracked'\n"
        f"{result.stdout}\n{result.stderr}"
    )
    assert result.stdout.strip() == "", (
        f"an inconsistent repository still produced a commit: {result.stdout!r}"
    )


# ---------------------------------------------------------------------------
# The workflow's REAL steps, executed under bash
# ---------------------------------------------------------------------------


def _python3_shim(tmp_path: Path) -> Path:
    """A `python3` on PATH that the runner shell will find.

    Git Bash PREPENDS `/mingw64/bin:/usr/bin` to PATH, so a PATH-based stub is
    honoured only for binaries Git Bash does not ship -- and it does not ship
    `python3`. The shim therefore wins, which is exactly why this test may
    use a PATH stub here and may NOT use one for `git`.

    The shim runs the REAL interpreter. The resolver's FAILURE codes are
    exercised elsewhere: `_run_resolve_step` overwrites this file with a shim
    that exits with the code under test, so the STEP's handling of each code
    can be driven without corrupting the tree.
    """
    shim_dir = tmp_path / "bin"
    shim_dir.mkdir(exist_ok=True)
    shim = shim_dir / "python3"
    shim.write_text(
        "#!/usr/bin/env bash\n"
        f'exec "{sys.executable}" "$@"\n',
        encoding="utf-8",
    )
    shim.chmod(0o755)
    return shim_dir


def _run_resolve_step(
    tmp_path: Path,
    *,
    url: str,
    resolver_exit: int | None = None,
) -> tuple[subprocess.CompletedProcess, dict[str, str]]:
    """Run the workflow's REAL resolution step under bash.

    `resolver_exit` replaces the resolver with a stub that exits with that
    code, so the step's handling of 4/5/6 can be exercised.
    """
    bash = _bash()
    if bash is None:
        pytest.skip("no working bash on this host (the gate runs on CI)")

    shim_dir = _python3_shim(tmp_path)
    if resolver_exit is not None:
        failing = shim_dir / "python3"
        failing.write_text(
            "#!/usr/bin/env bash\n"
            f"echo 'stub resolver' >&2\n"
            f"exit {resolver_exit}\n",
            encoding="utf-8",
        )
        failing.chmod(0o755)

    block = _step_run_block("build-validate-pr", RESOLVE_STEP)
    block = block.replace("${{ steps.cfg.outputs.git_url }}", url)

    script = tmp_path / "resolve.sh"
    script.write_text(block, encoding="utf-8", newline="\n")

    output_file = tmp_path / "github-output.txt"
    output_file.write_text("", encoding="utf-8")

    env = dict(os.environ)
    env["PATH"] = f"{shim_dir}{os.pathsep}{env.get('PATH', '')}"
    env["GITHUB_OUTPUT"] = str(output_file)

    result = subprocess.run(
        [bash, str(script)],
        capture_output=True, text=True, encoding="utf-8",
        env=env, timeout=300, cwd=str(REPO_ROOT),
    )
    outputs = {}
    for line in output_file.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            outputs[key.strip()] = value.strip()
    return result, outputs


def test_the_workflow_step_emits_the_recorded_commit(tmp_path: Path) -> None:
    """The workflow's own step must resolve the RECORDED commit."""
    result, outputs = _run_resolve_step(tmp_path, url=FORK_URL)

    assert result.returncode == 0, (
        f"the workflow's resolution step failed:\n{result.stdout}\n{result.stderr}"
    )
    assert outputs.get("pin") == _recorded_pin(), (
        f"the step emitted pin={outputs.get('pin')!r}; the tree records "
        f"{_recorded_pin()!r}"
    )


@pytest.mark.parametrize("exit_code", [EXIT_AMBIGUOUS, EXIT_INCONSISTENT, EXIT_UNREADABLE])
def test_the_workflow_step_fails_closed_on_a_resolver_failure(
    tmp_path: Path, exit_code: int
) -> None:
    """A resolver failure must FAIL the step, not fall back to the branch.

    Falling back would rebuild exactly the defect this gate exists to remove:
    the lane would quietly publish an artifact that no commit in PMOVES.AI
    names.
    """
    result, outputs = _run_resolve_step(
        tmp_path, url=FORK_URL, resolver_exit=exit_code
    )

    assert result.returncode != 0, (
        f"the step SUCCEEDED with a resolver exit of {exit_code}:\n"
        f"{result.stdout}\n{result.stderr}"
    )
    assert "::error::" in result.stderr or "::error::" in result.stdout, (
        f"the step failed without an error annotation:\n{result.stdout}\n{result.stderr}"
    )


def test_the_prepare_step_checks_out_the_recorded_commit(tmp_path: Path) -> None:
    """The prepare step must CHECK OUT the recorded commit, not the branch.

    The real step is executed with a stubbed `git` (a shell FUNCTION -- a PATH
    stub would be shadowed by Git Bash's own `/mingw64/bin/git`), and the
    recorded commands are read back.
    """
    bash = _bash()
    if bash is None:
        pytest.skip("no working bash on this host (the gate runs on CI)")

    pin = _recorded_pin()
    block = _step_run_block("build-validate-pr", PREPARE_STEP)
    for expression, value in (
        ("${{ steps.cfg.outputs.git_url }}", FORK_URL),
        ("${{ steps.cfg.outputs.ref }}", "PMOVES.AI-Edition-Hardened"),
        ("${{ steps.cfg.outputs.context }}", "."),
        ("${{ steps.cfg.outputs.dockerfile }}", "Dockerfile"),
        ("${{ steps.pin.outputs.pin }}", pin),
    ):
        block = block.replace(expression, value)

    # The pattern is HOISTED out of the f-string on purpose: a backslash inside
    # an f-string's expression part is valid in Python 3.12 (PEP 701) and a
    # SyntaxError in 3.11, and this repository declares `requires-python =
    # ">=3.11"` -- so the CI interpreter is the one that decides.
    leftover = sorted(set(re.findall(r"\$\{\{[^}]*\}\}", block)))
    assert "${{" not in block, (
        f"the prepare step still contains an unsubstituted expression; the "
        f"workflow's shape changed: {leftover}"
    )

    git_log = tmp_path / "git.log"
    stub = (
        "git() {\n"
        '  echo "git $*" >> "$GIT_LOG"\n'
        '  case "$*" in\n'
        '    *clone*) mkdir -p integration-src && : > integration-src/Dockerfile ;;\n'
        "  esac\n"
        "  return 0\n"
        "}\n"
    )
    script = tmp_path / "prepare.sh"
    script.write_text(stub + block, encoding="utf-8", newline="\n")

    env = dict(os.environ)
    env["GIT_LOG"] = str(git_log)

    result = subprocess.run(
        [bash, str(script)],
        capture_output=True, text=True, encoding="utf-8",
        env=env, timeout=300, cwd=str(tmp_path),
    )
    assert result.returncode == 0, (
        f"the prepare step failed:\n{result.stdout}\n{result.stderr}"
    )

    commands = git_log.read_text(encoding="utf-8")
    assert f"checkout --detach {pin}" in commands, (
        f"the prepare step did NOT check out the recorded commit {pin}.\n"
        f"Recorded git calls:\n{commands}"
    )
    assert f"fetch --depth=1 origin {pin}" in commands, (
        f"the prepare step did not fetch the recorded commit {pin}.\n"
        f"Recorded git calls:\n{commands}"
    )


def test_every_lane_that_clones_a_fork_pins_it() -> None:
    """Wiring: BOTH lanes that clone a fork must pin what they clone.

    The publish lane is the one that pushes the image, so a lane that pins
    only the validation path would leave the published artifact unpinned --
    which is the defect itself.
    """
    workflow = _workflow()
    lanes = []
    for job_name, job in (workflow.get("jobs") or {}).items():
        job = job or {}
        step_names = [str((s or {}).get("name") or "") for s in (job.get("steps") or [])]
        if PREPARE_STEP in step_names:
            lanes.append(job_name)

    assert len(lanes) >= 2, (
        f"expected the prepare step in at least two lanes (the PR validation "
        f"lane and the publish lane); found {lanes}"
    )

    for job_name in lanes:
        steps = (workflow["jobs"][job_name].get("steps") or [])
        by_name = {str((s or {}).get("name") or ""): (s or {}) for s in steps}

        assert RESOLVE_STEP in by_name, (
            f"job {job_name!r} prepares the integration source but has no "
            f"{RESOLVE_STEP!r} step; it would clone a moving branch"
        )
        resolve_index = [str((s or {}).get("name") or "") for s in steps].index(
            RESOLVE_STEP
        )
        prepare_index = [
            str((s or {}).get("name") or "") for s in steps
        ].index(PREPARE_STEP)
        assert resolve_index < prepare_index, (
            f"job {job_name!r} runs {PREPARE_STEP!r} BEFORE {RESOLVE_STEP!r}; the "
            f"prepare step would read an output that does not exist yet"
        )

        prepare = str(by_name[PREPARE_STEP].get("run") or "")
        assert "checkout --detach" in prepare, (
            f"job {job_name!r} prepares the source without checking out the "
            f"recorded commit"
        )


# ---------------------------------------------------------------------------
# The tree-reading edge cases, on fixtures
# ---------------------------------------------------------------------------


def _fixture_repo(tmp_path: Path) -> Path:
    """A real git repository the resolver can read."""
    subprocess.run(
        ["git", "init", "-q", str(tmp_path)],
        capture_output=True, text=True, timeout=120,
    )
    return tmp_path


def _commit_all(repo: Path, message: str) -> None:
    """Commit what is in the index, without disturbing the gitlinks.

    `git add -A` would DROP the `--info-only` gitlink entries, because their
    paths do not exist on disk -- so only `.gitmodules` is staged here.
    """
    subprocess.run(
        ["git", "-C", str(repo), "add", "--", ".gitmodules"],
        capture_output=True, text=True, timeout=120,
    )
    commit = subprocess.run(
        [
            "git", "-C", str(repo),
            "-c", "user.email=gate@example.invalid",
            "-c", "user.name=gate",
            "commit", "-q", "-m", message,
        ],
        capture_output=True, text=True, timeout=120,
    )
    assert commit.returncode == 0, commit.stderr


def _add_gitlink(repo: Path, path: str, sha: str) -> None:
    """Record a gitlink at `path` without needing the commit object.

    `--info-only` registers the mode-160000 entry without the object, which
    is exactly what the resolver reads: the gitlink, not the fork.
    """
    parent = Path(path).parent
    if str(parent) not in (".", ""):
        (repo / parent).mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "-C", str(repo), "update-index", "--add", "--info-only",
         "--cacheinfo", f"160000,{sha},{path}"],
        capture_output=True, text=True, timeout=120, check=True,
    )


def test_the_tool_resolves_a_nested_submodule(tmp_path: Path) -> None:
    """A submodule INSIDE a directory is still a submodule.

    A non-recursive `git ls-tree HEAD` lists only the top level, so this repo
    -- whose only submodule is at `pmoves/integrations/archon` -- would be read
    as tracking nothing. PMOVES.AI nests submodules exactly this way, so the
    tree has to be read RECURSIVELY.
    """
    repo = _fixture_repo(tmp_path)
    (repo / ".gitmodules").write_text(
        '[submodule "pmoves/integrations/archon"]\n'
        "\tpath = pmoves/integrations/archon\n"
        "\turl = https://github.com/POWERFULMOVES/PMOVES-Archon.git\n",
        encoding="utf-8",
    )
    sha = "8d135dabaafd090ff1da9dd966f7fd18d74da484"
    _add_gitlink(repo, "pmoves/integrations/archon", sha)
    _commit_all(repo, "record a nested submodule")

    result = _run_tool(
        "--url", "https://github.com/POWERFULMOVES/PMOVES-Archon.git",
        "--repo-root", str(repo),
    )
    assert result.returncode == EXIT_RESOLVED, (
        f"a NESTED submodule was not resolved (exit {result.returncode}); the "
        f"tree is read non-recursively\n{result.stdout}\n{result.stderr}"
    )
    assert result.stdout.strip() == sha, (
        f"the resolver returned {result.stdout.strip()!r}; the tree records {sha!r}"
    )


def test_the_tool_refuses_an_ambiguous_fork(tmp_path: Path) -> None:
    """Two submodules that disagree about the same fork is AMBIGUOUS (4).

    It must not be reported as "not tracked" (3): the repository says it
    tracks the fork, and the caller has to be told that the answer is not
    knowable rather than that there is no answer.
    """
    repo = _fixture_repo(tmp_path)
    (repo / ".gitmodules").write_text(
        '[submodule "PMOVES-Dup-A"]\n'
        "\tpath = PMOVES-Dup-A\n"
        "\turl = https://github.com/POWERFULMOVES/PMOVES-Dup.git\n"
        '[submodule "PMOVES-Dup-B"]\n'
        "\tpath = PMOVES-Dup-B\n"
        "\turl = https://github.com/POWERFULMOVES/PMOVES-Dup.git\n",
        encoding="utf-8",
    )
    _add_gitlink(repo, "PMOVES-Dup-A", "a" * 40)
    _add_gitlink(repo, "PMOVES-Dup-B", "b" * 40)
    _commit_all(repo, "record two submodules for one fork")

    result = _run_tool(
        "--url", "https://github.com/POWERFULMOVES/PMOVES-Dup.git",
        "--repo-root", str(repo),
    )
    assert result.returncode == EXIT_AMBIGUOUS, (
        f"an ambiguous fork returned exit {result.returncode}; it must be "
        f"distinguishable from 'not tracked'\n{result.stdout}\n{result.stderr}"
    )
    assert result.stdout.strip() == "", (
        f"an ambiguous fork still produced a commit: {result.stdout!r}"
    )


def test_the_tool_prefers_the_top_level_submodule() -> None:
    """When two submodules track one fork, the TOP-LEVEL one is the answer.

    MEASURED 2026-11-05 in this repo:

        160000 commit 490d74bcedec73b846e10a89a7610aecfd1f601d  PMOVES-Archon
        160000 commit 8d135dabaafd090ff1da9dd966f7fd18d74da484  pmoves/integrations/archon

    Both point at `PMOVES-Archon` and they pin DIFFERENT commits. The
    top-level one is the answer because `build-images.yml` builds
    `github.workspace/<repo>` -- the top-level path. Choosing the nested one
    would make the two publishers disagree about what they are building.
    """
    result = _run_tool("--url", "https://github.com/POWERFULMOVES/PMOVES-Archon.git")
    assert result.returncode == EXIT_RESOLVED, (
        f"the resolver failed for PMOVES-Archon (exit {result.returncode})\n"
        f"{result.stdout}\n{result.stderr}"
    )

    top_level = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-tree", "HEAD", "--", "PMOVES-Archon"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    ).stdout.split()
    nested = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-tree", "-r", "HEAD",
         "--", "pmoves/integrations/archon"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    ).stdout.split()

    assert top_level and nested, "the fixture submodules are not in the tree"
    assert top_level[2] != nested[2], (
        "the two archon submodules now record the SAME commit, so this gate's "
        "premise no longer holds and it needs rethinking"
    )
    assert result.stdout.strip() == top_level[2], (
        f"the resolver returned {result.stdout.strip()!r}; the TOP-LEVEL "
        f"submodule records {top_level[2]!r} and the nested one records "
        f"{nested[2]!r}"
    )


# ---------------------------------------------------------------------------
# The MATRIX is the population -- and it is the real one
# ---------------------------------------------------------------------------

MATRIX_FILE = REPO_ROOT / ".github" / "workflows" / "integrations-ghcr.matrix.json"

_SHA_RE = re.compile(r"\b[0-9a-f]{40}\b")


def _matrix_entries() -> list[dict]:
    import json

    assert MATRIX_FILE.exists(), f"the matrix must exist: {MATRIX_FILE}"
    entries = json.loads(MATRIX_FILE.read_text(encoding="utf-8"))
    assert entries, "the integration matrix is empty"
    for entry in entries:
        assert entry.get("name") and entry.get("git_url"), (
            f"a matrix entry is missing a name or a git_url: {entry!r}"
        )
    return entries


def test_every_matrix_entry_resolves_to_exactly_one_recorded_pin() -> None:
    """The MATRIX is the population, and every other test here uses a FIXTURE.

    A fixture proves the resolver does what it was told to do. It cannot tell
    you what the matrix ACTUALLY contains, and the matrix is what decides
    which artifacts get published. So this drives the REAL resolver over the
    REAL `.github/workflows/integrations-ghcr.matrix.json` and asserts that
    every entry lands in exactly one of the two HONEST outcomes:

      exit 0 -- one recorded pin, and it is a full 40-character commit id
      exit 3 -- nothing is recorded for it, so the branch ref is the source

    and NOT in a failure code. The two failure codes that matter here are
    AMBIGUOUS (4) and INCONSISTENT (5): a fork tracked twice with disagreeing
    pins, or a declared submodule with no gitlink. Both make the PUBLISH lane
    fail -- and the first sign of either would be a red publish run on main,
    with the artifact due and no warning beforehand. The build does fail
    closed, so nothing wrong ships; but a warning that arrives too late to be
    useful is not a warning. This is the check that turns it into a CI failure
    instead.

    Both branches are exercised on the real population: the forks resolve, and
    PMOVES.AI itself is not a submodule of PMOVES.AI, so it is honestly
    reported as not tracked.
    """
    entries = _matrix_entries()
    gitmodules = (REPO_ROOT / ".gitmodules").read_text(encoding="utf-8")

    resolved: list[str] = []
    not_tracked: list[str] = []

    for entry in entries:
        name = str(entry["name"])
        url = str(entry["git_url"])
        result = _run_tool("--url", url)

        assert result.returncode in (EXIT_RESOLVED, EXIT_NOT_TRACKED), (
            f"matrix entry {name!r} ({url}) did not resolve to exactly one "
            f"recorded pin: exit {result.returncode}\n"
            f"{result.stdout}\n{result.stderr}"
        )

        if result.returncode == EXIT_RESOLVED:
            pins = _SHA_RE.findall(result.stdout)
            assert len(pins) == 1, (
                f"matrix entry {name!r} resolved to {len(pins)} commit id(s) in "
                f"its output; there must be exactly one\n{result.stdout!r}"
            )
            resolved.append(name)
        else:
            # "Not tracked" must be TRUE, not a euphemism for "we gave up".
            assert url not in gitmodules, (
                f"matrix entry {name!r} ({url}) was reported as not tracked, but "
                f".gitmodules names it -- the resolver and the tree disagree"
            )
            not_tracked.append(name)

    assert resolved, (
        "no matrix entry resolved to a recorded pin; the matrix and the "
        "submodule tree have drifted apart and this gate would pass vacuously"
    )
    assert not_tracked, (
        "every matrix entry resolved to a recorded pin; the 'not tracked' "
        "branch is dead on the real population, so its assertion above is "
        "never exercised"
    )


def test_the_declared_submodules_and_the_recorded_gitlinks_agree() -> None:
    """The `.gitmodules` map and the TREE must describe the same submodules.

    Two ways they can drift, and both are invisible to a reader of either
    file alone:

      * a declared path with no gitlink -- the `missing` set. The resolver
        fails closed on it for a fork, but the drift itself is silent.
      * a gitlink with no declaration -- a submodule in the tree that
        `.gitmodules` does not describe, so no URL can ever reach it.

    MEASURED 2026-11-05 in this repo: the sets are EQUAL -- every declared
    path is recorded and every recorded path is declared. That is the state
    the resolver's fail-closed `missing` rule is designed for: the stricter
    contract therefore changes nothing for the real tree, and this assertion
    is what keeps it that way.

    It is also what makes the two counts in this lane's provenance tree-
    computed rather than quoted: they are the size of these two sets.
    """
    from pmoves.tools.resolve_recorded_pin import read_gitlinks, read_submodules

    declared_paths: set[str] = set()
    for paths in read_submodules(REPO_ROOT).values():
        declared_paths.update(paths)
    recorded_paths = set(read_gitlinks(REPO_ROOT))

    missing = sorted(declared_paths - recorded_paths)
    undeclared = sorted(recorded_paths - declared_paths)
    assert not missing, (
        f"these submodules are declared in .gitmodules but have no gitlink in "
        f"the tree: {missing}. The resolver fails closed on them for their "
        f"fork, but the drift itself is silent."
    )
    assert not undeclared, (
        f"these gitlinks are in the tree but declared in no .gitmodules entry: "
        f"{undeclared}. No fork URL can ever reach them, so the resolver "
        f"cannot resolve them."
    )


def test_every_declared_url_reduces_to_a_clean_fork_key() -> None:
    """Every declared URL must reduce to `<org>/<repo>` -- with no residue.

    A URL the tool cannot reduce looks exactly like a fork that is NOT
    tracked, and "not tracked" tells the caller to build the MOVING BRANCH.

    MEASURED 2026-11-05: no entry in this repo's `.gitmodules` used the
    scp-like `git@host:org/repo` spelling, so the hole was LATENT -- and a
    latent hole in the one answer that says "build the branch" is still a
    hole. The scp spelling is reduced now; this assertion is what keeps it
    reduced, and it would catch a URL spelling the reducer cannot handle.
    """
    from pmoves.tools.resolve_recorded_pin import normalise_url, read_submodules

    for url, paths in read_submodules(REPO_ROOT).items():
        key = normalise_url(url)
        assert "@" not in key and ":" not in key, (
            f"the declared url {url!r} (at {sorted(paths)}) does not reduce to "
            f"a clean <org>/<repo> key -- it reduces to {key!r}, which cannot "
            f"match a fork url"
        )
        assert key.count("/") == 1, (
            f"the declared url {url!r} reduces to {key!r}, which is not an "
            f"<org>/<repo> key"
        )


# ---------------------------------------------------------------------------
# The review round: four defects the bots found, each one gated
# ---------------------------------------------------------------------------


def test_the_tool_fails_closed_when_a_sibling_declaration_has_no_gitlink(
    tmp_path: Path,
) -> None:
    """A MISSING sibling makes the repository INCONSISTENT -- even when another
    declaration IS recorded.

    The tree can hold two submodules for one fork and record a gitlink for
    only one of them. The recorded one is a real answer, but it is not the
    PREFERRED one: the top-level submodule is the path `build-images.yml`
    builds, so falling back to the sibling would make the two publishers
    disagree about what they are building.

    The documented contract says exit 5 for a declared-but-unrecorded
    submodule, and it does not carry an "unless another one happens to be
    there" clause.
    """
    repo = _fixture_repo(tmp_path)
    (repo / ".gitmodules").write_text(
        '[submodule "PMOVES-Sibling"]\n'
        "\tpath = PMOVES-Sibling\n"
        "\turl = https://github.com/POWERFULMOVES/PMOVES-Sibling.git\n"
        '[submodule "integrations/PMOVES-Sibling"]\n'
        "\tpath = integrations/PMOVES-Sibling\n"
        "\turl = https://github.com/POWERFULMOVES/PMOVES-Sibling.git\n",
        encoding="utf-8",
    )
    # Only the NESTED one is recorded. The top-level one -- the preferred
    # candidate -- is declared and missing.
    _add_gitlink(repo, "integrations/PMOVES-Sibling", "a" * 40)
    _commit_all(repo, "record one of two declarations for the same fork")

    result = _run_tool(
        "--url", "https://github.com/POWERFULMOVES/PMOVES-Sibling.git",
        "--repo-root", str(repo),
    )
    assert result.returncode == EXIT_INCONSISTENT, (
        f"a fork with an unrecorded sibling returned exit {result.returncode}; "
        f"the repository state is inconsistent, and the caller must not be "
        f"told to build a branch\n{result.stdout}\n{result.stderr}"
    )
    assert result.stdout.strip() == "", (
        f"an inconsistent repository still produced a commit: {result.stdout!r}"
    )


def test_the_tool_normalises_the_scp_style_url(tmp_path: Path) -> None:
    """The SCP-LIKE remote spelling must resolve like the https one.

    `git@host:org/repo.git` is the spelling git itself prints for an SSH
    remote, so a fork's `.gitmodules` entry can carry it. If the tool cannot
    reduce it to `<org>/<repo>`, the fork reads as NOT TRACKED -- and "not
    tracked" tells the caller to build the MOVING BRANCH, which is the exact
    defect this tool exists to remove.

    MEASURED 2026-11-05: no `.gitmodules` entry in this repo uses the scp
    form, so the hole was LATENT. A latent hole in the one answer that says
    "build the branch" is still a hole.
    """
    repo = _fixture_repo(tmp_path)
    (repo / ".gitmodules").write_text(
        '[submodule "PMOVES-Scp"]\n'
        "\tpath = PMOVES-Scp\n"
        "\turl = git@github.com:POWERFULMOVES/PMOVES-Scp.git\n",
        encoding="utf-8",
    )
    _add_gitlink(repo, "PMOVES-Scp", "b" * 40)
    _commit_all(repo, "declare a submodule with an scp-style url")

    result = _run_tool(
        "--url", "https://github.com/POWERFULMOVES/PMOVES-Scp.git",
        "--repo-root", str(repo),
    )
    assert result.returncode == EXIT_RESOLVED, (
        f"an scp-style url returned exit {result.returncode}; the fork IS "
        f"tracked, and a url spelling must not make it read as absent\n"
        f"{result.stdout}\n{result.stderr}"
    )
    assert result.stdout.strip() == "b" * 40, (
        f"the resolver returned {result.stdout.strip()!r}; the tree records "
        f"{'b' * 40!r}"
    )


def test_the_tool_does_not_report_an_unrelated_lookup_error_as_not_tracked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A stray KeyError inside the resolution must NOT read as "not tracked".

    `KeyError` and `IndexError` are `LookupError` subclasses, so a broad
    `except LookupError` around the resolution turns any subscript mistake
    inside it into exit 3 -- "this fork is not tracked, build the branch".
    That is the exact defect this tool exists to remove, reached through a
    crash instead of through a branch.

    A failure the caller must not paper over cannot share a door with the one
    failure it is allowed to paper over. So the tool must let a real
    LookupError CRASH LOUDLY.
    """
    from pmoves.tools import resolve_recorded_pin as tool

    def boom(repo_root: Path) -> dict[str, str]:
        raise KeyError("a subscript that should never have been taken")

    monkeypatch.setattr(tool, "read_gitlinks", boom)

    with pytest.raises(KeyError):
        tool.resolve(REPO_ROOT, FORK_URL)

    # And the CLI must not turn it into "not tracked" either.
    with pytest.raises(KeyError):
        tool.main(["--url", FORK_URL, "--repo-root", str(REPO_ROOT)])


def test_the_workflow_runs_when_a_recorded_pin_can_change() -> None:
    """A PIN that advances must RE-PUBLISH, so every pin input must trigger it.

    This lane publishes from the RECORDED commit, which makes the pin STATIC:
    before, the build followed a moving branch, so a stale publish was
    self-correcting on the next run; now, a pin that advances without
    re-publishing leaves the published image on the PREVIOUS commit.

    So every input that can change a resolved pin must be in the workflow's
    `push.paths` AND `pull_request.paths`: the submodule paths whose gitlink
    IS the pin, `.gitmodules` (it maps a fork URL to those paths), and the
    resolver (it decides which path wins).

    The required set is DERIVED from the matrix and the tree, not hand-listed,
    so a new fork-backed entry cannot be added without also being covered here.
    """
    from pmoves.tools.resolve_recorded_pin import normalise_url, read_submodules

    workflow = _workflow()
    triggers = workflow.get(True) or workflow.get("on") or {}
    assert isinstance(triggers, dict), "the workflow has no `on:` block"

    matrix = json.loads(
        (REPO_ROOT / ".github" / "workflows" / "integrations-ghcr.matrix.json")
        .read_text(encoding="utf-8")
    )
    by_url = read_submodules(REPO_ROOT)

    required: set[str] = {
        ".gitmodules",
        "pmoves/tools/resolve_recorded_pin.py",
        ".github/workflows/integrations-ghcr.matrix.json",
    }
    for entry in matrix:
        url = str(entry.get("git_url") or "")
        if not url or url.rstrip("/").endswith("POWERFULMOVES/PMOVES.AI.git"):
            # PMOVES.AI itself is not tracked as a submodule; its branch ref
            # stays the source and there is no recorded pin to advance.
            continue
        paths = by_url.get(normalise_url(url))
        assert paths, (
            f"the matrix entry {entry.get('name')!r} points at {url!r}, which "
            f"the tree does not track as a submodule; the resolver would "
            f"report 'not tracked' and the build would use a moving branch"
        )
        required.update(paths)

    for trigger in ("push", "pull_request"):
        paths = list((triggers.get(trigger) or {}).get("paths") or [])
        missing = sorted(p for p in required if p not in paths)
        assert not missing, (
            f"the workflow's `{trigger}.paths` filter does not cover "
            f"{missing}; advancing one of those pins would not re-publish, "
            f"and the published image would stay on the previous commit"
        )
