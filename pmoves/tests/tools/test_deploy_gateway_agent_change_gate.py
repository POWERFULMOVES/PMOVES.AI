"""Gate: the deploy pipeline only DEPLOYS when the push touched something
deploy-relevant.

WHY THIS GATE EXISTS
--------------------
`deploy-gateway-agent.yml` deploys the gateway agent to ai-lab and to the VPS
(kvm4). Its `paths:` filter lists `.github/workflows/deploy-gateway-agent.yml`
ITSELF, so editing the workflow re-triggers the live deploys -- the coupling
that made PR #3445's merge re-trigger a pipeline that had been failing since
2026-09-28.

The `changes` job decides, from the push's own before/after SHAs, whether the
push is deploy-relevant. This gate drives that job's REAL shell block under
bash, with a stubbed `git`, and asserts the four outcomes that matter:

  1. a gateway-agent / docker-compose change  -> deploy=true,  build=true
  2. a workflow-file-only change               -> deploy=FALSE, build=true
  3. an unrelated change                       -> deploy=false, build=false
  4. a `git fetch` that fails                  -> the block FAILS and writes
     NO outputs, so nothing downstream can deploy (fail closed)

WHAT THIS TEST DOES NOT DO
--------------------------
It does not re-type the detection logic in Python. A test that re-types the
expression it is testing proves only that the author believed the expression --
which is the exact failure mode the whole gate exists to catch. The block under
test is SLICED OUT of the workflow file and executed.

It also asserts the WIRING: every job that consumes `needs.changes.outputs`
must be gated on it, and every gated job must spell out its dependency
success explicitly (a job-level `if:` without `success()` runs even when a
dependency FAILED).
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKFLOW_FILE = REPO_ROOT / ".github" / "workflows" / "deploy-gateway-agent.yml"

FULL_SHA = "361e26e9a0bc6b7f986524ab123b02059d92792d"
OTHER_SHA = "7b590f8b7e7794b16547212fb2c664afacf64615"


def _bash() -> str | None:
    """A bash that actually runs, or None.

    On Windows the `bash` on PATH is usually the WSL launcher, which may have
    no distribution; Git Bash is the reliable one. Each candidate is VERIFIED
    by running a command, so a launcher that cannot start is skipped rather
    than failing the test with a confusing error.
    """
    candidates = []
    git_bash = Path(r"C:\Program Files\Git\bin\bash.exe")
    if git_bash.exists():
        candidates.append(str(git_bash))
    found = shutil.which("bash")
    if found:
        candidates.append(found)
    for candidate in candidates:
        try:
            probe = subprocess.run(
                [candidate, "-c", "echo ok"],
                capture_output=True, text=True, timeout=60,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if probe.returncode == 0 and "ok" in probe.stdout:
            return candidate
    return None


def _workflow():
    yaml = pytest.importorskip("yaml")
    assert WORKFLOW_FILE.exists(), f"the deploy workflow must exist: {WORKFLOW_FILE}"
    workflow = yaml.safe_load(WORKFLOW_FILE.read_text(encoding="utf-8"))
    assert isinstance(workflow, dict), "the workflow must parse into a mapping"
    return workflow


def _detect_block() -> str:
    """The `changes` job's detection shell, sliced out of the workflow.

    FAIL CLOSED: if the block cannot be located, this raises rather than
    returning something vacuous.
    """
    workflow = _workflow()
    jobs = workflow.get("jobs") or {}
    assert "changes" in jobs, (
        "the `changes` job is missing from deploy-gateway-agent.yml; the "
        "workflow would deploy on every trigger again, and this gate would "
        "pass vacuously"
    )
    job = jobs["changes"] or {}
    scripts = [
        str((step or {}).get("run") or "")
        for step in (job.get("steps") or [])
    ]
    for script in scripts:
        if "git diff --name-only" in script:
            return script
    raise AssertionError(
        "the change-detection block was not found in the `changes` job; the "
        "workflow's shape changed, and the gate would pass vacuously"
    )


def _run_detect(
    tmp_path: Path,
    changed_paths: str,
    *,
    before: str = FULL_SHA,
    after: str = OTHER_SHA,
    fetch_rc: int = 0,
):
    """Run the REAL detection block with a stubbed `git`.

    The stub answers exactly the two git calls the block makes: `fetch`
    (exit code controlled by `fetch_rc`) and `diff --name-only` (the fixture's
    paths). Everything else in the block is the workflow's own code.

    The stub is a SHELL FUNCTION, not a PATH entry, and that is not a
    style choice. MEASURED 2026-11-05 on Git Bash: the shell PREPENDS
    `/mingw64/bin:/usr/bin` to PATH, so `command -v git` resolves to
    `/mingw64/bin/git` no matter what a test prepends to PATH -- a PATH-based
    `git` stub is silently ignored and the test would exercise the REAL git
    against the REAL network. A shell function takes precedence over PATH
    lookup, so it cannot be bypassed that way.
    """
    bash = _bash()
    if bash is None:
        pytest.skip("no working bash on this host (the gate runs on CI)")

    fixture = tmp_path / "changed-paths.txt"
    fixture.write_text(changed_paths, encoding="utf-8")

    stub = (
        "git() {\n"
        '  case "$1" in\n'
        '    fetch) return "${GIT_FETCH_RC:-0}" ;;\n'
        '    diff)  cat "$GIT_FIXTURE_CHANGED"; return 0 ;;\n'
        '    *)     return 0 ;;\n'
        "  esac\n"
        "}\n"
    )

    script = tmp_path / "detect.sh"
    script.write_text(
        stub + _detect_block(),
        encoding="utf-8",
        newline="\n",
    )

    output_file = tmp_path / "github-output.txt"
    output_file.write_text("", encoding="utf-8")

    env = dict(os.environ)
    env["GIT_FIXTURE_CHANGED"] = str(fixture)
    env["GIT_FETCH_RC"] = str(fetch_rc)
    env["BEFORE"] = before
    env["AFTER"] = after
    env["GITHUB_OUTPUT"] = str(output_file)

    result = subprocess.run(
        [bash, str(script)],
        capture_output=True, text=True, encoding="utf-8",
        env=env, timeout=120,
    )
    outputs = {}
    for line in output_file.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            outputs[key.strip()] = value.strip()
    return result, outputs


def test_a_deploy_relevant_change_deploys(tmp_path: Path) -> None:
    """A change to the gateway agent or to docker-compose MUST deploy."""
    for path in (
        "pmoves/services/gateway-agent/app.py",
        "pmoves/docker-compose.yml",
    ):
        result, outputs = _run_detect(tmp_path, path + "\n")
        assert result.returncode == 0, (
            f"the detection block failed for {path}:\n"
            f"{result.stdout}\n{result.stderr}"
        )
        assert outputs.get("deploy") == "true", (
            f"a change to {path} did NOT set deploy=true (outputs: {outputs}); "
            f"the gateway agent would not deploy when it should"
        )
        assert outputs.get("build") == "true", (
            f"a change to {path} did NOT set build=true (outputs: {outputs})"
        )


def test_a_workflow_only_change_does_not_deploy(tmp_path: Path) -> None:
    """THE defect this gate exists for.

    Editing the workflow re-triggers it, because the workflow file is in the
    `paths:` filter. That must build (so the fix is proven on a real runner)
    but MUST NOT deploy to ai-lab or to the VPS.
    """
    result, outputs = _run_detect(
        tmp_path, ".github/workflows/deploy-gateway-agent.yml\n"
    )
    assert result.returncode == 0, (
        f"the detection block failed:\n{result.stdout}\n{result.stderr}"
    )
    assert outputs.get("build") == "true", (
        f"a workflow-file change did not set build=true (outputs: {outputs}); "
        f"the workflow's own fix would never be exercised on a runner"
    )
    assert outputs.get("deploy") != "true", (
        f"a workflow-file-only change set deploy=true (outputs: {outputs}); "
        f"editing a YAML file would silently deploy to the fleet"
    )


def test_an_unrelated_change_neither_builds_nor_deploys(tmp_path: Path) -> None:
    """An unrelated push must not consume a runner or deploy anything."""
    result, outputs = _run_detect(tmp_path, "pmoves/launcher/README.md\n")
    assert result.returncode == 0, (
        f"the detection block failed:\n{result.stdout}\n{result.stderr}"
    )
    assert outputs.get("deploy") != "true", (
        f"an unrelated change set deploy=true (outputs: {outputs})"
    )
    assert outputs.get("build") != "true", (
        f"an unrelated change set build=true (outputs: {outputs})"
    )


def test_a_failed_fetch_fails_closed(tmp_path: Path) -> None:
    """A gate that cannot read its input must FAIL CLOSED.

    If the before-SHA cannot be fetched, the block must fail and write NO
    outputs -- so `needs.changes.outputs.deploy` is empty, every `== 'true'`
    comparison downstream is false, and nothing deploys.
    """
    result, outputs = _run_detect(
        tmp_path,
        "pmoves/docker-compose.yml\n",
        fetch_rc=1,
    )

    assert result.returncode != 0, (
        f"the detection block SUCCEEDED even though the fetch failed:\n"
        f"{result.stdout}\n{result.stderr}"
    )
    assert "deploy" not in outputs, (
        f"the block wrote outputs despite the failed fetch: {outputs}; a "
        f"downstream job could read deploy=true and deploy"
    )


def test_an_abbreviated_before_sha_is_not_silently_accepted(tmp_path: Path) -> None:
    """MEASURED 2026-11-05: `git fetch origin <abbrev>` fails with
    "couldn't find remote ref" -- the fetch is a ref advertisement, not a
    prefix lookup. The block passes whatever it is given to `git fetch`, and
    a failed fetch fails closed (see the test above), so an abbreviated SHA
    means NO deploy rather than a wrong deploy. This test pins that
    contract: the stub is told to fail for a non-40-character ref.
    """
    result, outputs = _run_detect(
        tmp_path,
        "pmoves/docker-compose.yml\n",
        before="361e26e9a0b",
        fetch_rc=128,
    )

    assert result.returncode != 0, (
        f"the block succeeded with an abbreviated SHA and a failing fetch:\n"
        f"{result.stdout}\n{result.stderr}"
    )
    assert "deploy" not in outputs


def test_every_job_that_consumes_the_detection_is_gated_on_it() -> None:
    """Wiring: a job may only read `needs.changes.outputs` if it is gated.

    A job-level `if:` that does not mention the detection output would deploy
    unconditionally -- the exact behaviour this gate removes.
    """
    workflow = _workflow()
    jobs = workflow.get("jobs") or {}

    consumers = []
    for job_name, job in jobs.items():
        job = job or {}
        needs = job.get("needs") or []
        if isinstance(needs, str):
            needs = [needs]
        if "changes" in needs:
            consumers.append(job_name)

    assert consumers, (
        "no job depends on the `changes` job; the workflow would deploy on "
        "every trigger and this gate would pass vacuously"
    )

    for job_name in consumers:
        condition = str((jobs[job_name] or {}).get("if") or "")
        assert "needs.changes.outputs" in condition, (
            f"job {job_name!r} depends on `changes` but its `if:` does not read "
            f"needs.changes.outputs (if: {condition!r}); it would run "
            f"unconditionally"
        )


def test_a_gated_job_states_its_dependency_success_explicitly() -> None:
    """A job-level `if:` without `success()` runs even when a dependency FAILED.

    GitHub's default `if: success()` is only applied when the condition does
    not mention a status function. So `if: needs.changes.outputs.deploy ==
    'true'` would run `deploy-ai-lab` even if `validate` had FAILED. Every
    gated job must therefore spell the dependency's result out.
    """
    workflow = _workflow()
    jobs = workflow.get("jobs") or {}

    for job_name, job in jobs.items():
        job = job or {}
        condition = str(job.get("if") or "")
        if "needs.changes.outputs" not in condition:
            continue
        assert ".result ==" in condition, (
            f"job {job_name!r} is gated on the detection output but does not "
            f"state any dependency's result (if: {condition!r}); it would run "
            f"even when a dependency failed"
        )
