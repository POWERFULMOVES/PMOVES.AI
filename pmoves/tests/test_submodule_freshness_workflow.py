"""
Workflow-glue regression test for .github/workflows/submodule-freshness.yml

Lesson 12 from the Mavis harness v0 follow-ups slice:
"Workflow glue needs code review, not just unit tests."

This test asserts the patterns that bind the workflow to the
tool's actual contract:
  - Uses `python` (not `py`, which is Windows-only and exits
    127 on the Ubuntu runner — caught for #2623)
  - Has `set -e -o pipefail` so a `python | tee` pipeline
    surfaces the tool's exit code (caught for #2568)
  - Calls the tool as `python -m pmoves.tools.submodule_freshness_check`
    (the canonical entry point that pmoves/tools/__init__.py
    wires into `python -m`)
  - Schedule is weekly (cron `0 8 * * 0`) — daily would be
    overkill for submodule drift; weekly matches the ruleset-
    sync safety net cadence
  - Permissions are `{}` (the workflow doesn't need any)
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "submodule-freshness.yml"


@pytest.fixture(scope="module")
def workflow_text() -> str:
    if not WORKFLOW.exists():
        pytest.skip(f"workflow not present at {WORKFLOW}")
    return WORKFLOW.read_text(encoding="utf-8")


def test_workflow_uses_python_not_py(workflow_text: str) -> None:
    """Every `python` invocation must be `python`, never `py`.

    `py` is the Windows Python launcher; on Ubuntu it exits 127
    because the launcher is not installed. Every workflow in this
    repo uses `python`; this test pins the new workflow to the
    same convention.
    """
    # Look for `py` as a standalone command (not `python` substring).
    bad = re.findall(r"(?<![\w-])py\b", workflow_text)
    # Filter out `pyproject.toml` and similar substrings.
    bad = [m for m in bad if m != "py"]
    # The only `py` token that should appear is the start of `python`.
    # Assert we never use a bare `py` command.
    assert " py " not in workflow_text, (
        "workflow contains a bare `py` command; use `python` instead "
        "(py is the Windows Python launcher and exits 127 on Ubuntu)"
    )


def test_workflow_has_pipefail(workflow_text: str) -> None:
    """The `python | tee` pipeline must use `set -e -o pipefail`."""
    assert "set -e" in workflow_text, (
        "workflow missing `set -e`; bash without -e continues on errors"
    )
    assert "pipefail" in workflow_text, (
        "workflow missing `pipefail`; without it, a `python | tee` "
        "pipeline reports tee's exit code (always 0), masking tool "
        "failures. See Lesson 12 (workflow glue needs code review)."
    )


def test_workflow_invokes_canonical_entry_point(workflow_text: str) -> None:
    """Calls the tool as `python -m pmoves.tools.submodule_freshness_check`."""
    assert "python -m pmoves.tools.submodule_freshness_check" in workflow_text, (
        "workflow doesn't call the tool as `python -m pmoves.tools."
        "submodule_freshness_check`; that's the canonical entry point "
        "that pmoves/tools/__init__.py wires into `python -m`"
    )


def test_workflow_has_minimal_permissions(workflow_text: str) -> None:
    """The workflow has `permissions: {}` (no token scope)."""
    # The `permissions: {}` block appears near the top of the workflow
    # (right after the `on:` block). Assert it exists at the right level.
    assert re.search(r"^permissions:\s*\{\}\s*$", workflow_text, re.MULTILINE), (
        "workflow missing `permissions: {}`; without it, the runner "
        "inherits the repo's default token which is broader than needed. "
        "The freshness check only does `git ls-remote` which doesn't "
        "require any GitHub API scope at all."
    )


def test_workflow_schedule_is_weekly(workflow_text: str) -> None:
    """Schedule is weekly (Sun 08:00 UTC), not daily."""
    # The cron expression `0 8 * * 0` = weekly Sunday 08:00 UTC.
    m = re.search(r"cron:\s*['\"]([^'\"]+)['\"]", workflow_text)
    assert m, "workflow has no cron schedule"
    cron = m.group(1)
    parts = cron.split()
    assert len(parts) == 5, f"cron expression must have 5 fields, got: {cron!r}"
    # Day-of-week field is `0` (Sunday) — weekly cadence.
    assert parts[4] == "0", (
        f"workflow cron day-of-week is {parts[4]!r}; expected '0' (Sunday) "
        f"for weekly cadence. Daily would be overkill for submodule drift."
    )


def test_workflow_uploads_artifact(workflow_text: str) -> None:
    """The workflow uploads the freshness report as an artifact."""
    assert "actions/upload-artifact" in workflow_text, (
        "workflow doesn't upload an artifact; the JSON report must be "
        "preserved for offline inspection"
    )
    assert ".freshness/" in workflow_text or "freshness" in workflow_text.lower(), (
        "workflow doesn't reference the .freshness/ artifact path"
    )

def test_every_run_block_is_valid_shell():
    """The step that shipped was Python pasted into a bash `run:` block.

    After the `python -c` invocation closed, the script continued with
    `ahead = [...]`, `if ahead:` and `for s in ahead:` -- Python, in the shell.
    `bash -n` rejects it with "syntax error near unexpected token '('", and the
    step is `if: always()`, so every scheduled run would have failed.

    Nothing in this repo syntax-checks workflow shell, which is why it shipped:
    the YAML parses fine, and the string inside `run:` is opaque to it.
    """
    import shutil
    import subprocess
    import tempfile

    yaml = pytest.importorskip("yaml")
    bash = shutil.which("bash")
    if not bash:
        pytest.skip("bash not available on this runner")

    doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps = [s for job in doc["jobs"].values()
             for s in job["steps"] if "run" in s]
    assert steps, "no run: blocks found -- this test would pass vacuously"

    offenders = []
    with tempfile.TemporaryDirectory() as d:
        script = Path(d) / "step.sh"
        for step in steps:
            script.write_text(step["run"], encoding="utf-8", newline="\n")
            proc = subprocess.run(
                [bash, "-n", str(script)], capture_output=True, text=True
            )
            if proc.returncode != 0:
                offenders.append(f"{step.get('name')!r}: {proc.stderr.strip()}")

    assert not offenders, (
        "run: blocks that are not valid shell:\n" + "\n".join(offenders)
    )
