"""Behavioural ratchet: the smoke gate must SEE a submodule marked `ignore = all`.

THE DEFECT THIS GUARDS
----------------------
``.github/workflows/submodule-smoke.yml`` found the changed submodules with::

    git diff --name-only "$base_sha" "$head_sha"

`git diff` honours the `ignore` setting in ``.gitmodules``. This repo sets
``ignore = all`` for **PMOVES-OpenRoom** and **PMOVES-registry**, so those two
paths are INVISIBLE to ``git diff``.

MEASURED on PR #3482 (the 13-gitlink promotion lane): the diff listed only
**ELEVEN** of the **THIRTEEN** promoted submodules -- PMOVES-OpenRoom and
PMOVES-registry were missing -- and the job's own "Post results as PR comment"
step duly reported those eleven. The gate read 11 of its 13 inputs and was
one push away from reporting success. That is a FAIL-OPEN gate.

The fix derives the changed gitlinks from the two TREES (``git ls-tree`` on
base and head), which no ``.gitmodules`` setting can hide.

WHY THIS IS A BEHAVIOURAL TEST AND NOT A STRING MATCH
------------------------------------------------------
A ratchet that asserts the workflow contains ``git ls-tree`` proves only that
a word is present. The defect is about what the gate SEES, so this test
REPRODUCES the situation -- a real superproject, real submodules, a real
``ignore = all`` entry -- and then runs the workflow's OWN detection script
over it and asserts on what comes out.

The premise is asserted separately (``test_the_reproduction_actually_hides_the
_submodule_from_git_diff``): if a future git release stopped honouring
``ignore = all``, that test fails on its own, and this one keeps measuring
what it measures.

Run it directly::

    python -m pytest pmoves/tests/tools/test_submodule_smoke_detection_sees_ignored_submodules.py -q
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "submodule-smoke.yml"
PMOVES_ROOT = REPO_ROOT / "pmoves"

sys.path.insert(0, str(REPO_ROOT))
from pmoves.tools.bash_resolver import find_bash  # noqa: E402

DETECT_STEP = "Identify changed submodules"

IGNORED = "child-ignored"
PLAIN = "child-plain"


def _git(args: list[str], cwd: Path, env: dict[str, str]) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=str(cwd), env=env, capture_output=True,
        text=True, encoding="utf-8", errors="replace",
    )
    if proc.returncode != 0:
        raise AssertionError(
            f"git {' '.join(args)} failed in {cwd}:\n{proc.stdout}\n{proc.stderr}"
        )
    return proc.stdout


def _detection_script() -> str:
    """The workflow's OWN detection script, verbatim."""
    with WORKFLOW.open("r", encoding="utf-8") as fh:
        workflow = yaml.safe_load(fh)
    jobs = workflow.get("jobs") or {}
    for job in jobs.values():
        for step in job.get("steps") or []:
            if str(step.get("name") or "") == DETECT_STEP:
                return str(step.get("run") or "")
    raise AssertionError(
        f"the workflow no longer has a {DETECT_STEP!r} step -- the gate's "
        "changed-submodule detection cannot be located"
    )


def _build_superproject(root: Path, env: dict[str, str]) -> tuple[Path, str, str]:
    """A superproject with one `ignore = all` submodule and one plain one.

    Returns ``(superproject, base_sha, head_sha)`` where ``head_sha`` moves
    ONLY the ignored child's gitlink.
    """
    ignored_repo = root / "ignored-src"
    plain_repo = root / "plain-src"
    super_proj = root / "super"

    for repo in (ignored_repo, plain_repo):
        repo.mkdir(parents=True)
        _git(["init", "-b", "main"], repo, env)
        _git(["config", "user.name", "smoke-gate-ratchet"], repo, env)
        _git(["config", "user.email", "ratchet@example.invalid"], repo, env)
        (repo / "payload.txt").write_text("one\n", encoding="utf-8")
        _git(["add", "payload.txt"], repo, env)
        _git(["commit", "-m", "initial"], repo, env)

    super_proj.mkdir(parents=True)
    _git(["init", "-b", "main"], super_proj, env)
    _git(["config", "user.name", "smoke-gate-ratchet"], super_proj, env)
    _git(["config", "user.email", "ratchet@example.invalid"], super_proj, env)
    _git(["config", "protocol.file.allow", "always"], super_proj, env)

    for name, src in ((IGNORED, ignored_repo), (PLAIN, plain_repo)):
        _git(
            ["-c", "protocol.file.allow=always", "submodule", "add",
             str(src), name],
            super_proj, env,
        )

    # The exact setting the promotion lane tripped over.
    _git(["config", "-f", ".gitmodules", f"submodule.{IGNORED}.ignore", "all"],
         super_proj, env)
    _git(["add", ".gitmodules"], super_proj, env)
    _git(["commit", "-m", "add submodules"], super_proj, env)
    base_sha = _git(["rev-parse", "HEAD"], super_proj, env).strip()

    # Advance ONLY the ignored child's gitlink.
    (ignored_repo / "payload.txt").write_text("two\n", encoding="utf-8")
    _git(["add", "payload.txt"], ignored_repo, env)
    _git(["commit", "-m", "advance"], ignored_repo, env)
    new_sha = _git(["rev-parse", "HEAD"], ignored_repo, env).strip()
    _git(["update-index", "--cacheinfo", f"160000,{new_sha},{IGNORED}"],
         super_proj, env)
    _git(["commit", "-m", "bump ignored child"], super_proj, env)
    head_sha = _git(["rev-parse", "HEAD"], super_proj, env).strip()

    return super_proj, base_sha, head_sha


def _run_detection(super_proj: Path, base_sha: str, head_sha: str,
                   env: dict[str, str]) -> list[str]:
    """Run the workflow's detection script and return the submodule list."""
    bash = find_bash()
    if not bash:
        raise AssertionError(
            "no usable bash -- the detection script is bash and cannot be "
            "executed, so this test cannot measure what the gate sees"
        )

    script = _detection_script()
    script = script.replace(
        "${{ github.event.pull_request.base.sha }}", base_sha)
    script = script.replace(
        "${{ github.event.pull_request.head.sha }}", head_sha)

    with tempfile.TemporaryDirectory() as out_dir:
        out_file = Path(out_dir) / "gh_output"
        run_env = dict(env)
        run_env["GITHUB_OUTPUT"] = str(out_file)
        proc = subprocess.run(
            [bash, "-e", "-c", script],
            cwd=str(super_proj), env=run_env, capture_output=True,
            text=True, encoding="utf-8", errors="replace",
        )
        if proc.returncode != 0:
            raise AssertionError(
                "the detection script failed:\n"
                f"{proc.stdout}\n{proc.stderr}"
            )
        text = out_file.read_text(encoding="utf-8") if out_file.exists() else ""

    for line in text.splitlines():
        if line.startswith("submodules="):
            value = line.split("=", 1)[1].strip()
            return [p for p in value.split(",") if p]
    return []


def _git_env() -> dict[str, str]:
    env = dict(os.environ)
    env["GIT_AUTHOR_NAME"] = "smoke-gate-ratchet"
    env["GIT_AUTHOR_EMAIL"] = "ratchet@example.invalid"
    env["GIT_COMMITTER_NAME"] = "smoke-gate-ratchet"
    env["GIT_COMMITTER_EMAIL"] = "ratchet@example.invalid"
    env["GIT_CONFIG_GLOBAL"] = str(Path(tempfile.gettempdir()) / "nonexistent-gitconfig")
    env["GIT_CONFIG_SYSTEM"] = str(Path(tempfile.gettempdir()) / "nonexistent-gitconfig")
    return env


def test_the_reproduction_actually_hides_the_submodule_from_git_diff() -> None:
    """The premise: `git diff --name-only` really does hide an `ignore = all` path.

    If a future git release stops honouring ``ignore = all``, this test fails
    on its own -- the reproduction would no longer reproduce the defect, and
    the behavioural test beside it would be measuring nothing.
    """
    env = _git_env()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        super_proj, base_sha, head_sha = _build_superproject(root, env)
        names = _git(
            ["diff", "--name-only", base_sha, head_sha], super_proj, env
        ).split()
        assert IGNORED not in names, (
            f"`git diff --name-only` DID report {IGNORED!r} -- the reproduction "
            "no longer reproduces the defect, so the behavioural test beside "
            "it cannot measure anything"
        )


def test_the_detection_sees_a_submodule_marked_ignore_all() -> None:
    """The property: the gate's own detection finds the ignored submodule."""
    env = _git_env()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        super_proj, base_sha, head_sha = _build_superproject(root, env)
        detected = _run_detection(super_proj, base_sha, head_sha, env)

    assert IGNORED in detected, (
        f"the gate's changed-submodule detection did NOT report {IGNORED!r} "
        f"(it reported {detected}) -- that submodule is marked "
        "`ignore = all` in .gitmodules, so a diff-based detection cannot see "
        "it, and the gate would verify fewer submodules than the PR changed"
    )
    assert PLAIN not in detected, (
        f"the detection reported {PLAIN!r}, whose gitlink did not change -- "
        f"it reported {detected}"
    )
