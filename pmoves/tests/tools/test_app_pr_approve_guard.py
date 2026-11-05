"""Gate: the guarded PR-approval workflow ACCEPTS the verdicts the check-runs
API actually returns.

WHY THIS GATE EXISTS
--------------------
`app-pr-approve.yml` is the repo's intended way to clear `REVIEW_REQUIRED`
WITHOUT the admin bypass. Its guard reads every check at head and refuses
unless all of them are verdicts it accepts.

MEASURED 2026-11-05: the guard compared UPPERCASE patterns
(`SUCCESS|SKIPPED|NEUTRAL`) against the REST check-runs API's LOWERCASE
conclusions (`success`, `skipped`, `neutral`, `cancelled`). The GraphQL
`statusCheckRollup` returns UPPERCASE, which is where the wrong spelling came
from. The case statement therefore matched NOTHING and every check fell
through to its default branch: the run printed

    BAD: merge-decision is success

for a GREEN check, and then refused with

    REFUSED: 30 check(s) not green at head ...

The workflow had never run before that dispatch, so the defect had never been
observed -- and it made the non-admin approval path unusable, so every merge
silently fell back to the admin bypass.

WHAT THIS TEST DOES
-------------------
It runs the workflow's REAL guard -- the actual shell lines, sliced out of the
workflow file -- under bash, against the API's REAL output shape, captured
from the live API.

It does NOT re-type the guard's logic in Python. A test that re-types the
expression it is testing proves only that the test author believed the
expression, which is the failure mode this whole gate exists to catch.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from pmoves.tools.bash_resolver import find_bash  # never System32's WSL stub

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKFLOW_FILE = REPO_ROOT / ".github" / "workflows" / "app-pr-approve.yml"

# CAPTURED 2026-11-05 from the live API, at main head
# 7b590f8b7e7794b16547212fb2c664afacf64615, with the command the guard uses:
#   gh api "repos/POWERFULMOVES/PMOVES.AI/commits/<head>/check-runs" \
#     --jq '.check_runs[] | "\(.conclusion // "PENDING") \(.name)"'
# The verdicts are LOWERCASE. That is the whole point of the capture.
LIVE_API_OUTPUT = """\
success merge-decision
success python-tests
success hardening-validation
success verify
success submodule-gitlink-gate
success audit
success Kilo Code Review
success Validate open-notebook (PR)
skipped CodeQL
skipped CodeRabbit
skipped Submodule Smoke Test
skipped chit-routing-comment
"""

# The guard's accepted set, as the API spells a cancelled review bot.
CANCELLED_REVIEW_BOT = "cancelled Kilo Code Review"
CANCELLED_OTHER = "cancelled Some CI Job"
FAILED_CHECK = "failure python-tests"


def _bash() -> str | None:
    """A usable bash, or None.

    Delegates to the house resolver. `shutil.which("bash")` is NOT enough: on
    Windows it returns `C:\Windows\System32\bash.exe` -- the WSL
    launcher -- before PATH is ever consulted, so the child would silently run
    in a different OS. `pmoves/tests/test_no_bare_bash_argv.py` gates that.
    """
    return find_bash()


def _guard_block() -> str:
    """The guard's shell lines, sliced out of the workflow file.

    FAIL CLOSED: if the block cannot be located, this raises rather than
    returning something vacuous.
    """
    yaml = pytest.importorskip("yaml")
    assert WORKFLOW_FILE.exists(), f"the approval workflow must exist: {WORKFLOW_FILE}"
    workflow = yaml.safe_load(WORKFLOW_FILE.read_text(encoding="utf-8"))
    assert isinstance(workflow, dict), "the workflow must parse into a mapping"

    scripts = []
    for job in (workflow.get("jobs") or {}).values():
        for step in ((job or {}).get("steps") or []):
            run = str((step or {}).get("run") or "")
            if run:
                scripts.append(run)

    for script in scripts:
        lines = script.splitlines()
        start = next(
            (i for i, ln in enumerate(lines) if 'checks="$(gh api' in ln),
            None,
        )
        if start is None:
            continue
        end = next(
            (
                i for i, ln in enumerate(lines)
                if "no check runs at head" in ln
            ),
            None,
        )
        if end is None:
            continue
        return "\n".join(lines[start:end + 1])

    raise AssertionError(
        "the check-verdict guard was not found in app-pr-approve.yml; the "
        "workflow's shape changed, and the gate would pass vacuously"
    )


def _run_guard(tmp_path: Path, api_output: str) -> subprocess.CompletedProcess:
    bash = _bash()
    if bash is None:
        pytest.skip("no working bash on this host (the gate runs on CI)")

    fixture = tmp_path / "api-output.txt"
    fixture.write_text(api_output, encoding="utf-8")

    # A stub `gh` that emits the captured API output. The guard's own
    # `--jq` filter is not exercised by this stub; what is exercised is the
    # comparison of the verdict the filter produced -- which is exactly the
    # thing that was broken.
    stub_dir = tmp_path / "bin"
    stub_dir.mkdir()
    stub = stub_dir / "gh"
    stub.write_text(
        "#!/usr/bin/env bash\n"
        "cat \"$GH_FIXTURE\"\n",
        encoding="utf-8",
    )
    stub.chmod(0o755)

    script = tmp_path / "guard.sh"
    script.write_text(
        "set -euo pipefail\n"
        'REPO="POWERFULMOVES/PMOVES.AI"\n'
        'head="0000000000000000000000000000000000000000"\n'
        'refuse() { echo "REFUSED: $*" >&2; exit 1; }\n'
        f"{_guard_block()}\n"
        'echo "GUARD_ACCEPTED"\n',
        encoding="utf-8",
        newline="\n",
    )

    env = dict(os.environ)
    env["PATH"] = f"{stub_dir}{os.pathsep}{env.get('PATH', '')}"
    env["GH_FIXTURE"] = str(fixture)
    return subprocess.run(
        [bash, str(script)],
        capture_output=True, text=True, encoding="utf-8",
        env=env, timeout=120,
    )


def test_the_guard_accepts_the_lowercase_verdicts_the_api_returns(tmp_path: Path) -> None:
    """The defect this gate exists for: the API's verdicts must be ACCEPTED."""
    result = _run_guard(tmp_path, LIVE_API_OUTPUT)

    assert "BAD:" not in result.stdout, (
        f"the guard rejected a GREEN set of checks:\n{result.stdout}\n{result.stderr}"
    )
    assert "GUARD_ACCEPTED" in result.stdout, (
        f"the guard did not accept the captured API output:\n"
        f"{result.stdout}\n{result.stderr}"
    )


def test_the_guard_still_tolerates_a_cancelled_review_bot(tmp_path: Path) -> None:
    """The fix must not have cost the review-bot tolerance."""
    result = _run_guard(
        tmp_path,
        LIVE_API_OUTPUT + CANCELLED_REVIEW_BOT + "\n",
    )

    assert "tolerated CANCELLED review-bot check" in result.stdout, (
        f"the guard stopped tolerating a cancelled review bot:\n"
        f"{result.stdout}\n{result.stderr}"
    )
    assert "GUARD_ACCEPTED" in result.stdout, (
        f"the guard refused a green set plus a cancelled review bot:\n"
        f"{result.stdout}\n{result.stderr}"
    )


def test_the_guard_still_refuses_a_failed_check(tmp_path: Path) -> None:
    """FAIL CLOSED: the fix must not have made the guard permissive."""
    result = _run_guard(
        tmp_path,
        LIVE_API_OUTPUT + FAILED_CHECK + "\n",
    )

    assert result.returncode != 0, (
        f"the guard ACCEPTED a failing check:\n{result.stdout}\n{result.stderr}"
    )
    assert "REFUSED:" in result.stderr, (
        f"the guard did not refuse with a reason:\n{result.stdout}\n{result.stderr}"
    )
    assert "not green" in result.stderr, (
        f"the refusal did not name the failing checks:\n{result.stderr}"
    )


def test_the_guard_still_refuses_a_cancelled_non_review_bot(tmp_path: Path) -> None:
    """Only the named review bots may be tolerated when cancelled."""
    result = _run_guard(
        tmp_path,
        LIVE_API_OUTPUT + CANCELLED_OTHER + "\n",
    )

    assert result.returncode != 0, (
        f"the guard ACCEPTED a cancelled non-review-bot check:\n"
        f"{result.stdout}\n{result.stderr}"
    )
    assert "REFUSED:" in result.stderr


def test_the_guard_refuses_when_there_are_no_check_runs_at_head(tmp_path: Path) -> None:
    """Absence is not consent.

    The API answers an empty check-runs list for a head that has never been
    checked. Every check being "green" is then vacuously true, so the guard
    has to refuse on the EMPTY set rather than accept it.
    """
    result = _run_guard(tmp_path, "")

    assert result.returncode != 0, (
        f"the guard ACCEPTED an empty check set:\n{result.stdout}\n{result.stderr}"
    )
    assert "REFUSED:" in result.stderr, (
        f"the guard did not refuse with a reason:\n{result.stdout}\n{result.stderr}"
    )
    assert "no check runs" in result.stderr, (
        f"the refusal did not name the missing evidence:\n{result.stderr}"
    )


def test_the_app_token_is_minted_inline_in_the_approving_job() -> None:
    """A credential cannot cross a job boundary through a JOB OUTPUT.

    MEASURED 2026-11-02 in PMOVES.AI PR #3445: GitHub Actions SKIPS a job
    output whose value "may contain secret". The mint job SUCCEEDS and the
    consuming job receives an EMPTY value -- the mint job's own log says it
    verbatim (`##[warning]Skip output 'token' since it may contain secret.`).
    The reusable workflow `.github/workflows/_app-token.yml` was consumed that
    way and its only cross-job consumer failed on 100% of runs.

    So the token must be minted and consumed in the SAME job, through a STEP
    output. This workflow already does that; the gate is here so that moving it
    back across the boundary cannot pass unnoticed.
    """
    yaml = pytest.importorskip("yaml")
    workflow = yaml.safe_load(WORKFLOW_FILE.read_text(encoding="utf-8"))
    assert isinstance(workflow, dict)

    token_envs: list[str] = []
    for job_name, job in (workflow.get("jobs") or {}).items():
        job = job or {}
        for step in (job.get("steps") or []):
            step = step or {}
            for value in (step.get("env") or {}, job.get("env") or {}):
                if isinstance(value, dict) and "GH_TOKEN" in value:
                    token_envs.append(f"{job_name}/{step.get('name')}:{value['GH_TOKEN']}")

    assert token_envs, (
        "no step in app-pr-approve.yml sets GH_TOKEN; the guard would run with "
        "no credential, and this gate would pass vacuously"
    )
    for entry in token_envs:
        assert "steps." in entry and ".outputs.token" in entry, (
            f"GH_TOKEN is set from {entry!r}; a credential taken from a JOB "
            f"output arrives EMPTY, because GitHub skips job outputs that may "
            f"contain a secret"
        )
        assert "needs." not in entry, (
            f"GH_TOKEN is set from {entry!r}; a credential must be minted and "
            f"consumed in the SAME job, through a STEP output"
        )
