"""The `paths:` trigger of python-tests.yml must describe what the job runs.

Why this file exists
--------------------
`.github/workflows/python-tests.yml` listed `pmoves/tests/**` in both of its
`paths:` filters, but its pytest invocation passed only `pmoves/services/*/tests`
directories. A pull request that touched nothing but `pmoves/tests` therefore
woke the workflow, collected none of the 155 test files it had just changed, and
published a green `tests (3.11)` check. The filter read as coverage in the checks
list while providing none.

It also listed `pytest.ini`, a file that has never existed in this repository --
a trigger on something that can never change.

Neither mistake is visible by reading either half alone. It only shows up when
you read the trigger and the run step together, which is what these tests do.

Scope note, so nobody "fixes" this the wrong way: `pmoves/tests` is NOT
untested. merge-gate.yml's `python-tests` job (which IS a required check on
main, unlike `tests (3.11)`) runs pmoves/tools/pytest_ratchet.py over the whole
repo with no paths filter. These tests do not ask python-tests.yml to duplicate
that. They ask it to stop claiming a tree it does not run.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "python-tests.yml"
PYPROJECT = REPO_ROOT / "pmoves" / "pyproject.toml"

# `on:` is parsed by PyYAML 1.1 rules as the boolean True, not the string "on".
ON_KEY = True

GLOB_CHARS = set("*?[]")


def _workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def _triggers(wf: dict) -> dict:
    on = wf.get(ON_KEY, wf.get("on"))
    assert isinstance(on, dict), "python-tests.yml lost its `on:` block"
    return on


def _path_filters(wf: dict) -> dict:
    """{event_name: [path glob, ...]} for every event that declares `paths:`."""
    return {
        event: cfg["paths"]
        for event, cfg in _triggers(wf).items()
        if isinstance(cfg, dict) and "paths" in cfg
    }


# A pytest command line: optional leading VAR=value assignments, then `pytest`,
# then any number of backslash-continued lines. Anchored this precisely because
# the naive version -- "any step whose body mentions pytest" -- also matched the
# dependency-install step, whose heredoc'd Python names `pytest` in its
# base_packages list and names two real repo paths in its comments. Those comment
# paths were then read as pytest targets. Scanning prose for arguments is exactly
# the kind of almost-right check this file exists to prevent.
_PYTEST_CMD = re.compile(
    r"^[ \t]*(?:[A-Z_][A-Z0-9_]*=\S+[ \t]+)*pytest\b(?P<body>(?:[^\n\\]|\\\n)*)",
    re.M,
)


def _run_script(wf: dict) -> str:
    """Every pytest command line in the job, and nothing else."""
    steps = wf["jobs"]["tests"]["steps"]
    cmds = []
    for step in steps:
        for match in _PYTEST_CMD.finditer(step.get("run", "")):
            cmds.append(match.group(0))
    assert cmds, "no step in python-tests.yml invokes pytest"
    return "\n".join(cmds)


def _pytest_targets(script: str) -> set[str]:
    """Positional paths handed to pytest, excluding flag values such as --ignore=."""
    ignored = set(re.findall(r"--ignore=([\w./*-]+)", script))
    targets: set[str] = set()
    for token in re.findall(r"(?<![=\w/.-])(pmoves/[\w./*-]+)", script):
        targets.add(token.rstrip("\\").rstrip())
    return targets - ignored


def test_every_literal_path_in_the_trigger_exists():
    """A trigger on a nonexistent file is dead weight that reads as coverage.

    This is the check that would have caught `pytest.ini`.
    """
    wf = _workflow()
    missing: list[str] = []
    for event, paths in _path_filters(wf).items():
        for entry in paths:
            if GLOB_CHARS & set(entry):
                continue
            if not (REPO_ROOT / entry).exists():
                missing.append(f"{event}: {entry}")
    assert not missing, (
        "python-tests.yml triggers on paths that do not exist:\n  "
        + "\n  ".join(missing)
    )


def test_push_and_pull_request_filters_agree():
    """Two copies of one list drift. If they ever differ it should be on purpose."""
    filters = _path_filters(_workflow())
    assert set(filters) >= {"push", "pull_request"}
    assert filters["push"] == filters["pull_request"], (
        "the push and pull_request paths filters have diverged:\n"
        f"  push:         {filters['push']}\n"
        f"  pull_request: {filters['pull_request']}"
    )


def test_pmoves_tests_is_a_trigger_if_and_only_if_it_is_a_target():
    """The exact defect: `pmoves/tests` triggered the job but was never run by it.

    Both directions are asserted. Adding the tree back to `paths:` without adding
    it to the pytest invocation re-creates the green-check-that-ran-nothing.
    Adding it to the invocation without the trigger creates the opposite problem:
    edits to it would no longer wake the job that now runs it.
    """
    wf = _workflow()
    script = _run_script(wf)

    triggered = any(
        entry.startswith("pmoves/tests")
        for paths in _path_filters(wf).values()
        for entry in paths
    )
    targeted = any(t.startswith("pmoves/tests") for t in _pytest_targets(script))

    assert triggered == targeted, (
        "python-tests.yml's trigger and its pytest targets disagree about "
        f"pmoves/tests (triggered={triggered}, targeted={targeted}).\n"
        "If you are adding it as a target: also add 'pmoves/tests/**' to both "
        "paths: filters, and expect the ~175 failures currently baselined in "
        "pmoves/configs/pytest_ratchet/_known_failures.yaml to surface here as "
        "hard red. Fix them; do not --ignore or skip them."
    )


def test_the_config_file_pytest_actually_uses_is_a_trigger():
    """pmoves/pyproject.toml supplies addopts/import-mode/asyncio_mode for this
    job. Editing it changes what the job does, so it has to wake the job."""
    paths = _path_filters(_workflow())["pull_request"]
    assert "pmoves/pyproject.toml" in paths, (
        "pmoves/pyproject.toml is the `configfile` pytest resolves for this "
        "workflow but is not in its paths filter"
    )


def _markers_declared() -> set[str]:
    body = PYPROJECT.read_text(encoding="utf-8")
    block = re.search(r"^markers = \[(.*?)^\]", body, re.S | re.M)
    assert block, "pmoves/pyproject.toml has no markers list"
    return {
        m.group(1)
        for m in re.finditer(r'"\s*([a-zA-Z_][\w]*)\s*(?:\([^)]*\))?\s*:', block.group(1))
    }


# Markers pytest itself provides; never declared in config.
_BUILTIN_MARKERS = {
    "parametrize", "skip", "skipif", "xfail", "usefixtures", "filterwarnings",
    "asyncio",  # supplied by pytest-asyncio, never declared in config
}


def test_every_marker_used_under_pmoves_tests_is_declared():
    """--strict-markers is on, and an undeclared marker aborts COLLECTION of the
    whole file -- not one test, the file. `requires`, `dependency` and `unit`
    were undeclared, and between them silenced 46 tests across three files under
    any strict invocation."""
    used: dict[str, list[str]] = {}
    for path in sorted((REPO_ROOT / "pmoves" / "tests").rglob("test_*.py")):
        text = path.read_text(encoding="utf-8", errors="replace")
        for name in re.findall(r"@pytest\.mark\.([a-zA-Z_]\w*)", text):
            if name in _BUILTIN_MARKERS:
                continue
            used.setdefault(name, []).append(str(path.relative_to(REPO_ROOT)))

    declared = _markers_declared()
    undeclared = {k: v for k, v in used.items() if k not in declared}
    assert not undeclared, (
        "markers used under pmoves/tests but not declared in "
        "pmoves/pyproject.toml (--strict-markers will abort collection of every "
        "file listed):\n  "
        + "\n  ".join(f"{k}: {sorted(set(v))[:4]}" for k, v in sorted(undeclared.items()))
    )


@pytest.mark.parametrize("service_dir", sorted(
    d for d in (_pytest_targets(_run_script(_workflow())))
    if d.startswith("pmoves/services/")
))
def test_every_service_test_target_exists(service_dir: str):
    """A target directory that has been renamed away makes pytest exit 4 (usage
    error) -- or, worse, silently collects nothing if a sibling still matches."""
    assert (REPO_ROOT / service_dir).is_dir(), (
        f"python-tests.yml passes {service_dir} to pytest, but it is not a directory"
    )
