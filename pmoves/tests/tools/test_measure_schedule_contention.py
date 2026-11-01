"""The schedule-contention measurement is FAIL-CLOSED, COMPUTES its ratios, and
is re-runnable from the tree.

WHY THIS FILE EXISTS
--------------------
`build-images.yml` schedules a fleet-wide image build on a self-hosted runner
and explains its cron minute with MEASURED claims about the fleet's other
schedules. Three defects were found in that explanation, and this file is the
gate that keeps them fixed:

1. THE INSTRUMENT WAS NOT IN THE TREE. The measurement lived in a developer's
   temp directory, so the claim survived in the prose and the measurement did
   not. A future reader hunting the tree for the script that produced the
   numbers found nothing. The instrument now lives at
   `pmoves/tools/measure_schedule_contention.py`, and this file exercises it.

2. THE MEASUREMENT WAS FAIL-OPEN. It did `continue` on a YAML parse
   exception, so a workflow file it could not read was dropped from the
   population SILENTLY and the script still exited 0. The population it
   reported could shrink between runs without anyone noticing. A measurement
   over a smaller set than it claims is not a measurement.

3. THE RATIO WAS ASSERTED, NOT COMPUTED. The claim "review-collect fires 365x
   more often than the weekly ruleset sync" was WRONG: `0 */2 * * *` fires 12
   times a day (84 a week) and `0 4 * * 0` fires once a week, so the ratio is
   84. The ratio is now COMPUTED from the parsed cron fields, so it cannot
   drift away from the crons it describes.

WHAT THIS FILE ASSERTS
----------------------
  * a workflow file that cannot be parsed is a NAMED FAILURE, not a silent
    drop, and the tool exits 2 (NOT MEASURED) rather than 0;
  * a COMMENTED-OUT `schedule:` is genuinely absent -- the YAML is parsed, not
    grepped;
  * the weekly frequency is derived from the cron fields;
  * a runner label of `self-hosted` is what makes a schedule contend for the
    build's runner pool;
  * the workflow that OWNS the build slot is not in contention with itself;
  * LIVE, against this repo: the whole fleet is read (no file dropped), and
    no self-hosted schedule falls within the margin of the build slot. This
    last one is the ROT GATE -- if someone adds a self-hosted schedule at
    04:10, this test goes red instead of the comment quietly becoming false.

Hermetic: no network, no docker, no NATS, no gh. It reads files in this repo
and writes into pytest's tmp_path.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
TOOL = REPO_ROOT / "pmoves" / "tools" / "measure_schedule_contention.py"
WORKFLOWS = REPO_ROOT / ".github" / "workflows"

spec = importlib.util.spec_from_file_location("measure_schedule_contention", TOOL)
assert spec and spec.loader, f"cannot load {TOOL}"
msc = importlib.util.module_from_spec(spec)
sys.modules["measure_schedule_contention"] = msc
spec.loader.exec_module(msc)


# --------------------------------------------------------------- fixtures ---


def _write_workflow(directory: Path, name: str, body: str) -> Path:
    path = directory / name
    path.write_text(body, encoding="utf-8")
    return path


HOSTED_WORKFLOW = """
name: hosted
on:
  schedule:
    - cron: '0 */2 * * *'
jobs:
  probe:
    runs-on: ubuntu-24.04
    steps:
      - run: echo hello
"""

SELF_HOSTED_WORKFLOW = """
name: self-hosted
on:
  schedule:
    - cron: '0 3 * * *'
jobs:
  probe:
    runs-on: [self-hosted, Linux, X64]
    steps:
      - run: echo hello
"""

WEEKLY_WORKFLOW = """
name: weekly
on:
  schedule:
    - cron: '0 4 * * 0'
jobs:
  probe:
    runs-on: ubuntu-24.04
    steps:
      - run: echo hello
"""

COMMENTED_OUT_WORKFLOW = """
name: commented
on:
  # schedule:
  #   - cron: '17 7 * * *'
  workflow_dispatch:
jobs:
  probe:
    runs-on: ubuntu-24.04
    steps:
      - run: echo hello
"""


@pytest.fixture
def workflow_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "workflows"
    directory.mkdir()
    return directory


# ------------------------------------------------- the instrument exists ---


def test_the_measurement_instrument_is_in_the_tree():
    """The lesson and the comment cite this path. If the file moves or is
    deleted, the citation becomes a claim about a thing that does not exist."""
    assert TOOL.is_file(), (
        f"{TOOL} is missing. The schedule-contention measurement is cited by "
        ".github/workflows/build-images.yml and by "
        "pmoves/docs/AGENTS/runbook_drift_fleet_closure_LEARNINGS.md; a "
        "measurement that survives only in prose is a claim, not a measurement."
    )


# ------------------------------------------------- fail-closed on unread ---


def test_a_workflow_that_cannot_be_parsed_is_a_named_failure(
    workflow_dir: Path,
):
    """NOT a silent drop. The first version of this measurement did
    `continue` on a parse exception and exited 0, so the population it
    reported could shrink between runs with nothing to show for it."""
    _write_workflow(workflow_dir, "good.yml", HOSTED_WORKFLOW)
    _write_workflow(workflow_dir, "broken.yml", "on:\n  schedule:\n   - cron: '0 3 * * *'\n  bad: [unclosed\n")

    result = msc.scan_workflows(workflow_dir)

    assert result.parse_failures, "an unparsable workflow was dropped silently"
    assert any("broken.yml" in failure for failure in result.parse_failures), (
        f"the failure does not name the file it could not read: "
        f"{result.parse_failures}"
    )
    assert result.fully_read is False
    # The readable file was still measured -- the failure does not discard it.
    assert [s.workflow for s in result.schedules] == ["good.yml"]


def test_the_cli_exits_not_measured_when_the_fleet_cannot_be_read(
    workflow_dir: Path, capsys
):
    """Exit 2, never 0. A green measurement over a population it could not
    fully read is exactly the fail-open this tool exists to remove."""
    _write_workflow(workflow_dir, "broken.yml", "on: [unclosed\n")
    code = msc.main(["--workflows", str(workflow_dir), "--check"])
    assert code == msc.EXIT_UNMEASURED, (
        f"expected NOT MEASURED (2), got {code}; a tool that cannot read its "
        "input must not exit 0"
    )


def test_a_workflow_that_cannot_be_parsed_still_counts_in_the_population(
    workflow_dir: Path,
):
    """The count of files SCANNED includes the unreadable one, so the reported
    population and the walked population cannot disagree."""
    _write_workflow(workflow_dir, "good.yml", HOSTED_WORKFLOW)
    _write_workflow(workflow_dir, "broken.yml", "on: [unclosed\n")
    result = msc.scan_workflows(workflow_dir)
    assert result.files_scanned == 2
    assert result.files_parsed == 1


# ------------------------------------------------------- what counts as a ---


def test_a_commented_out_schedule_is_not_a_schedule(workflow_dir: Path):
    """A commented-out `schedule:` is genuinely absent. This is the exact
    defect the lane's lesson 21 caught in prose: a dead code block cited as
    fleet-wide load-balancing evidence."""
    _write_workflow(workflow_dir, "commented.yml", COMMENTED_OUT_WORKFLOW)
    result = msc.scan_workflows(workflow_dir)
    assert result.schedules == []
    assert result.parse_failures == []


def test_a_self_hosted_runner_label_is_what_makes_a_schedule_contend(
    workflow_dir: Path,
):
    _write_workflow(workflow_dir, "hosted.yml", HOSTED_WORKFLOW)
    _write_workflow(workflow_dir, "selfhosted.yml", SELF_HOSTED_WORKFLOW)
    result = msc.scan_workflows(workflow_dir)
    by_name = {s.workflow: s for s in result.schedules}
    assert by_name["hosted.yml"].self_hosted is False
    assert by_name["selfhosted.yml"].self_hosted is True


# ---------------------------------------------- the ratio is COMPUTED ------


@pytest.mark.parametrize(
    "cron,expected",
    [
        ("0 */2 * * *", 84),   # every even hour -> 12/day -> 84/week
        ("0 4 * * 0", 1),      # Sundays only -> 1/week
        ("0 6 * * *", 7),      # daily -> 7/week
        ("23 4 * * *", 7),     # daily -> 7/week
        ("41 6 * * *", 7),     # daily -> 7/week
        ("0 9 * * 1", 1),      # Mondays only -> 1/week
        ("16 20 * * 5", 1),    # Fridays only -> 1/week
    ],
)
def test_the_weekly_frequency_is_computed_from_the_cron_fields(
    workflow_dir: Path, cron: str, expected: int
):
    """The ratio in the comment is DERIVED, so it cannot drift from the crons
    it describes. An asserted ratio is exactly what went wrong: 365x was
    wrong, and the true ratio is 84."""
    body = (
        "name: probe\non:\n  schedule:\n    - cron: '%s'\n"
        "jobs:\n  probe:\n    runs-on: ubuntu-24.04\n    steps:\n      - run: echo hi\n"
        % cron
    )
    _write_workflow(workflow_dir, "probe.yml", body)
    result = msc.scan_workflows(workflow_dir)
    assert len(result.schedules) == 1
    assert result.schedules[0].weekly_frequency == expected


def test_the_reported_ratio_is_84_not_365(workflow_dir: Path):
    """review-collect (`0 */2 * * *`) against the weekly ruleset sync
    (`0 4 * * 0`). MEASURED, not asserted -- and it is 84, not 365."""
    _write_workflow(workflow_dir, "review.yml", HOSTED_WORKFLOW)
    _write_workflow(workflow_dir, "weekly.yml", WEEKLY_WORKFLOW)
    result = msc.scan_workflows(workflow_dir)
    by_cron = {s.cron: s for s in result.schedules}
    frequent = by_cron["0 */2 * * *"].weekly_frequency
    rare = by_cron["0 4 * * 0"].weekly_frequency
    assert (frequent, rare) == (84, 1)
    assert frequent // rare == 84


def test_a_day_restricted_cron_is_reported_with_its_restriction(
    workflow_dir: Path,
):
    """'fires at 04:00' is never claimed for a cron that only fires on
    Sundays."""
    _write_workflow(workflow_dir, "weekly.yml", WEEKLY_WORKFLOW)
    result = msc.scan_workflows(workflow_dir)
    schedule = result.schedules[0]
    assert schedule.clock_times == ["04:00"]
    assert schedule.day_note == "Sunday only"


# ------------------------------------------------- the slot is not its own ---


def test_the_slot_owner_is_not_its_own_contention(workflow_dir: Path):
    """A build is not in contention with itself. Counting the owner would
    make every slot look contended and the check meaningless."""
    _write_workflow(workflow_dir, "build-images.yml", SELF_HOSTED_WORKFLOW)
    result = msc.scan_workflows(workflow_dir)
    assert result.schedules[0].self_hosted is True
    assert msc.self_hosted_neighbours(result, "03:00", 60, {"build-images.yml"}) == []
    assert msc.self_hosted_neighbours(result, "03:00", 60, set())


# ----------------------------------------------------- the CLI, end to end ---


def test_the_cli_reports_the_measurement_as_json(workflow_dir: Path):
    _write_workflow(workflow_dir, "hosted.yml", HOSTED_WORKFLOW)
    _write_workflow(workflow_dir, "selfhosted.yml", SELF_HOSTED_WORKFLOW)
    completed = subprocess.run(
        [sys.executable, str(TOOL), "--workflows", str(workflow_dir), "--json"],
        capture_output=True, text=True, timeout=120,
    )
    assert completed.returncode == 0, completed.stderr
    import json

    payload = json.loads(completed.stdout)
    assert payload["files_scanned"] == 2
    assert payload["live_schedules"] == 2
    assert payload["parse_failures"] == []


def test_the_cli_fails_when_a_self_hosted_schedule_is_near_the_slot(
    workflow_dir: Path,
):
    """The NEGATIVE CONTROL: the check must be able to say no."""
    body = (
        "name: probe\non:\n  schedule:\n    - cron: '10 4 * * *'\n"
        "jobs:\n  probe:\n    runs-on: [self-hosted, Linux, X64]\n"
        "    steps:\n      - run: echo hi\n"
    )
    _write_workflow(workflow_dir, "rival.yml", body)
    completed = subprocess.run(
        [sys.executable, str(TOOL), "--workflows", str(workflow_dir), "--check"],
        capture_output=True, text=True, timeout=120,
    )
    assert completed.returncode == msc.EXIT_CONTENTION, completed.stdout + completed.stderr


# --------------------------------------------------------------- the LIVE ---


def test_the_live_fleet_is_read_completely():
    """No workflow file in this repo may be unreadable. If one becomes
    unreadable, the fleet's schedule population is no longer known and every
    claim about it is void."""
    result = msc.scan_workflows(WORKFLOWS)
    assert result.parse_failures == [], (
        "workflow files could not be read, so the fleet's schedule population "
        f"is unknown:\n" + "\n".join(result.parse_failures)
    )
    assert result.files_scanned == result.files_parsed
    assert result.files_scanned > 0


def test_the_live_build_slot_is_clear_of_self_hosted_contention():
    """THE ROT GATE.

    `build-images.yml` asserts that its 04:23 slot is clear of every
    self-hosted schedule in the fleet. This test re-measures that claim from
    the tree on every PR, so the assertion cannot rot into a falsehood: add a
    self-hosted schedule at 04:10 and this goes red.
    """
    result = msc.scan_workflows(WORKFLOWS)
    assert result.fully_read, (
        "the fleet could not be fully read, so the contention question is "
        "undecided rather than answered"
    )
    conflicts = msc.self_hosted_neighbours(
        result,
        msc.DEFAULT_SLOT,
        msc.DEFAULT_MARGIN_MINUTES,
        msc.DEFAULT_EXCLUDED_WORKFLOWS,
    )
    assert conflicts == [], (
        "a self-hosted schedule now falls within "
        f"{msc.DEFAULT_MARGIN_MINUTES} min of the {msc.DEFAULT_SLOT} build slot "
        f"in .github/workflows/build-images.yml:\n"
        + "\n".join(
            f"  {c[2]} ({c[0]} min) {c[1].workflow} {c[1].cron}" for c in conflicts
        )
    )


def test_the_live_measurement_still_sees_the_schedules_it_cites():
    """The comment names specific schedules at specific clock times. If the
    fleet's schedules move, the comment's numbers move with them -- and this
    test says so rather than letting the prose rot."""
    result = msc.scan_workflows(WORKFLOWS)
    by_workflow = {s.workflow: s for s in result.schedules}

    assert "04:00" in by_workflow["review-collect.yml"].clock_times
    assert "04:00" in by_workflow["branch-protection-ruleset-sync.yml"].clock_times
    assert "03:00" in by_workflow["fleet-docker-cleanup.yml"].clock_times
    assert "03:00" in by_workflow["runner-maintenance.yml"].clock_times
    assert "06:00" in by_workflow["submodule-update-check.yml"].clock_times

    # And the 06:00 cluster is SEVEN schedules, not six.
    at_six = [s for s in result.schedules if "06:00" in s.clock_times]
    assert len(at_six) == 7, (
        f"the comment enumerates the 06:00 cluster; it now holds "
        f"{len(at_six)} schedules: {[s.workflow for s in at_six]}"
    )
