"""MEASURE the fleet's scheduled workflows, fail-closed, and CHECK that the
image-build slot is clear of self-hosted contention.

WHY THIS TOOL EXISTS
--------------------
`build-images.yml` schedules a fleet-wide image build and runs its `build`
job on `[self-hosted, Linux, X64]`. The comment in that workflow explains why
the cron minute is `23` and not `0`, and it backs that explanation with
MEASURED claims about the fleet's other schedules. A claim that cites a
measurement needs a RE-RUNNABLE instrument: if the instrument lives only in a
developer's temp directory, then the claim survives in the prose and the
measurement does not, and a future reader hunting the tree for the script that
produced the numbers finds nothing.

So the measurement lives HERE, in the tree, and the comment cites this path.

FAIL-CLOSED, ON PURPOSE
-----------------------
The first version of this measurement lived in a temp directory and did
`continue` on a YAML parse exception, so a workflow file it could not read was
dropped from the population SILENTLY and the script still exited 0. The
population it reported could therefore shrink between runs without anyone
noticing -- a green measurement over a smaller set than it claimed.

This version refuses to report a population it did not fully read:

  * every workflow file is COUNTED, and every parse failure is named;
  * a parse failure is an ERROR that forces a non-zero exit, not a silent
    drop;
  * UNDECIDED is not a category here. The tool either measured the whole
    fleet or it failed.

WHAT IS MEASURED
----------------
  * every live `schedule:` cron in `.github/workflows` -- a COMMENTED-OUT
    `schedule:` is genuinely absent, which is why the YAML is parsed rather
    than grepped;
  * each schedule's CLOCK TIMES and its day-of-week restriction, so "fires at
    04:00" is never claimed for a cron that only fires on Sundays;
  * the runner class (HOSTED vs SELF-HOSTED) from each job's `runs-on`;
  * each schedule's WEEKLY FREQUENCY, computed from the cron fields rather
    than asserted by hand.

The weekly frequency exists because a hand-written ratio is a hand-written
claim. `0 */2 * * *` fires 12 times a day (84 a week); `0 4 * * 0` fires once
a week. The ratio is 84. It is computed here from the parsed fields, so it
cannot drift away from the crons it describes.

CLI
---
    python pmoves/tools/measure_schedule_contention.py
    python pmoves/tools/measure_schedule_contention.py --json
    python pmoves/tools/measure_schedule_contention.py --check
    python pmoves/tools/measure_schedule_contention.py --slot 04:23 --margin 60

`--check` exits 1 when a SELF-HOSTED schedule falls within `--margin` minutes
of the build slot, and 2 when the fleet could not be fully read. The comment
in `build-images.yml` asserts that the slot IS clear, so that assertion is
runnable rather than merely stated.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - the fleet ships PyYAML; absence is fatal
    yaml = None  # type: ignore[assignment]

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WORKFLOWS = REPO_ROOT / ".github" / "workflows"

# The build slot asserted in build-images.yml, and the margin inside which a
# self-hosted schedule counts as contention.
DEFAULT_SLOT = "04:23"
DEFAULT_MARGIN_MINUTES = 60

# The workflow that OWNS the build slot. It is not in contention with itself,
# so the check excludes it unless the caller says otherwise.
DEFAULT_EXCLUDED_WORKFLOWS = {"build-images.yml"}

EXIT_OK = 0
EXIT_CONTENTION = 1
EXIT_UNMEASURED = 2

DAY_NAMES = {
    "0": "Sunday", "1": "Monday", "2": "Tuesday", "3": "Wednesday",
    "4": "Thursday", "5": "Friday", "6": "Saturday", "7": "Sunday",
}

# The cron field shapes this reader understands are enforced by
# `_expand_field`, which raises ValueError on a shape it does not understand.
# There is deliberately no separate registry of "supported shapes" to drift
# away from the parser -- a registry the parser never reads is a comment
# pretending to be a contract.


def _expand_field(field_expr: str, low: int, high: int) -> set[int]:
    """Every value a cron field matches. Supports `*`, `*/N`, `a-b`, `a,b`
    and plain integers. Raises ValueError on a shape it does not understand."""
    expr = field_expr.strip()
    if not expr:
        raise ValueError("empty cron field")
    if expr == "*":
        return set(range(low, high + 1))
    values: set[int] = set()
    for part in expr.split(","):
        part = part.strip()
        if not part:
            raise ValueError(f"empty element in cron field {field_expr!r}")
        if part.startswith("*/"):
            step_text = part[2:]
            if not step_text.isdigit():
                raise ValueError(f"bad step in cron field {field_expr!r}")
            step = int(step_text)
            if step <= 0:
                raise ValueError(f"bad step in cron field {field_expr!r}")
            values.update(range(low, high + 1, step))
        elif "-" in part:
            bounds = part.split("-")
            if len(bounds) != 2 or not all(b.strip().isdigit() for b in bounds):
                raise ValueError(f"bad range in cron field {field_expr!r}")
            start, end = int(bounds[0]), int(bounds[1])
            if start < low or end > high or start > end:
                raise ValueError(f"out-of-range range in cron field {field_expr!r}")
            values.update(range(start, end + 1))
        elif part.isdigit():
            value = int(part)
            if value < low or value > high:
                raise ValueError(f"out-of-range value in cron field {field_expr!r}")
            values.add(value)
        else:
            raise ValueError(f"unsupported cron field {field_expr!r}")
    if not values:
        raise ValueError(f"cron field {field_expr!r} matches nothing")
    return values


@dataclass
class Schedule:
    """One live `schedule:` entry, with the runner class of its workflow."""

    workflow: str
    cron: str
    minutes: set[int] = field(default_factory=set)
    hours: set[int] = field(default_factory=set)
    days_of_week: set[int] = field(default_factory=set)
    day_restricted: bool = False
    runner_labels: set[str] = field(default_factory=set)
    self_hosted: bool = False

    @property
    def clock_times(self) -> list[str]:
        return sorted(
            f"{h:02d}:{m:02d}" for h in self.hours for m in self.minutes
        )

    @property
    def day_note(self) -> str:
        if not self.day_restricted:
            return ""
        names = sorted({DAY_NAMES.get(str(d), str(d)) for d in self.days_of_week})
        return " / ".join(names) + " only"

    @property
    def weekly_frequency(self) -> int:
        """How many times a week this cron fires, COMPUTED from the fields.

        A hand-written ratio is a hand-written claim; this is derived, so it
        cannot drift away from the crons it describes.
        """
        if not self.minutes or not self.hours:
            return 0
        days = self._days_per_week()
        return len(self.minutes) * len(self.hours) * days

    def _days_per_week(self) -> int:
        # Day-of-MONTH restricted crons are REFUSED at parse time (see
        # `_parse_cron`), so the only day restriction that can reach here is
        # day-of-week, and the count is the NORMALISED one -- Sunday spelled
        # 0 and Sunday spelled 7 are one day, not two.
        if not self.day_restricted:
            return 7
        return len(self.days_of_week)


@dataclass
class ScanResult:
    """Everything one scan measured, and everything it could not."""

    workflows_dir: Path
    files_scanned: int = 0
    files_parsed: int = 0
    schedules: list[Schedule] = field(default_factory=list)
    parse_failures: list[str] = field(default_factory=list)

    @property
    def fully_read(self) -> bool:
        return not self.parse_failures


def _runner_labels(data: dict) -> set[str]:
    labels: set[str] = set()
    for job in (data.get("jobs") or {}).values():
        if not isinstance(job, dict):
            continue
        runs_on = job.get("runs-on")
        if isinstance(runs_on, str):
            labels.add(runs_on)
        elif isinstance(runs_on, list):
            labels.update(str(item) for item in runs_on)
    return labels


def _schedule_entries(data: dict) -> list:
    """The `on:` block's live `schedule:` list.

    YAML 1.1 parses the bare key `on:` as the boolean True, so both spellings
    are checked.
    """
    on = data.get("on", data.get(True))
    if not isinstance(on, dict):
        return []
    schedule = on.get("schedule")
    if not isinstance(schedule, list):
        return []
    return [entry for entry in schedule if isinstance(entry, dict)]


def _parse_cron(
    cron: str,
) -> tuple[set[int], set[int], set[int], bool]:
    """(minutes, hours, days-of-week, day-of-week-restricted).

    Two shapes are REFUSED rather than approximated, because this tool's whole
    contract is that a number it publishes is derived:

    * a day-of-MONTH restricted cron. `0 4 15 * *` fires once a MONTH, and a
      month is not a week: reading its day set as "31 days" and calling the
      result a weekly frequency is fiction. The shape is refused, the entry
      becomes a NAMED failure, and the scan fails closed.
    * a day-of-week field that names 7 as well as 0 is normalised, because 7
      is Sunday's second spelling: `0,7` is ONE day and `0-7` is every day,
      not two and eight.
    """
    parts = cron.split()
    if len(parts) != 5:
        raise ValueError(f"cron {cron!r} does not have 5 fields")
    minute_expr, hour_expr, dom_expr, mon_expr, dow_expr = parts
    # The month field is read for shape only: the fleet's crons are all-*
    # months, and a restricted month would need calendar arithmetic this tool
    # deliberately does not approximate.
    _expand_field(mon_expr, 1, 12)
    minutes = _expand_field(minute_expr, 0, 59)
    hours = _expand_field(hour_expr, 0, 23)
    dom = _expand_field(dom_expr, 1, 31)
    dow = _expand_field(dow_expr, 0, 7)
    if dom_expr.strip() != "*":
        raise ValueError(
            f"cron {cron!r} restricts day-of-month; a weekly frequency cannot "
            "be derived from it (a month is not a week) and it is not "
            "approximated"
        )
    # 7 is Sunday's second spelling. Normalise BEFORE counting, so the number
    # the ratio leans on is the same one the prose label describes.
    normalised_dow = {day % 7 for day in dow}
    restricted = dow_expr.strip() != "*" and normalised_dow != set(range(7))
    return minutes, hours, normalised_dow, restricted


def scan_workflows(workflows_dir: Path) -> ScanResult:
    """Measure every live schedule under `workflows_dir`.

    FAIL-CLOSED: a file that cannot be parsed is RECORDED as a failure. The
    caller decides what to do with the failures; the scan never silently
    reports a smaller population than it walked.
    """
    result = ScanResult(workflows_dir=Path(workflows_dir))
    if yaml is None:  # pragma: no cover
        result.parse_failures.append(
            "PyYAML is not importable, so no workflow can be read"
        )
        return result
    if not workflows_dir.is_dir():
        result.parse_failures.append(f"{workflows_dir} is not a directory")
        return result

    files = sorted(list(workflows_dir.glob("*.yml")) + list(workflows_dir.glob("*.yaml")))
    result.files_scanned = len(files)
    for path in files:
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001 -- a failure we must name
            result.parse_failures.append(f"{path.name}: YAML PARSE FAILED: {exc}")
            continue
        if not isinstance(data, dict):
            # A workflow file that is not a mapping carries no schedule, and
            # reading it is not a failure.
            result.files_parsed += 1
            continue
        result.files_parsed += 1
        labels = _runner_labels(data)
        self_hosted = any("self-hosted" in label for label in labels)
        for entry in _schedule_entries(data):
            cron = entry.get("cron")
            if not isinstance(cron, str) or not cron.strip():
                # An entry with no cron key, or a cron that YAML read as a
                # NUMBER (an unquoted `23` is an int), is a schedule the tool
                # cannot measure. It is a NAMED FAILURE, not a silent drop:
                # v1 dropped unreadable FILES, and dropping unreadable
                # ENTRIES is the same fail-open in a smaller hat.
                result.parse_failures.append(
                    f"{path.name}: schedule entry with no usable cron: {entry!r}"
                )
                continue
            try:
                minutes, hours, dow, dow_restricted = _parse_cron(cron)
            except ValueError as exc:
                result.parse_failures.append(f"{path.name}: {exc}")
                continue
            result.schedules.append(
                Schedule(
                    workflow=path.name,
                    cron=cron,
                    minutes=minutes,
                    hours=hours,
                    days_of_week=dow,
                    day_restricted=dow_restricted,
                    runner_labels=labels,
                    self_hosted=self_hosted,
                )
            )
    return result


def _to_minutes(clock: str) -> int:
    hours, minutes = clock.split(":")
    return int(hours) * 60 + int(minutes)


def _circular_distance(first: int, second: int) -> int:
    """Minutes between two clock positions, WRAPPING at midnight.

    A plain `abs(a - b)` makes 23:50 look 1420 minutes from 00:10 when it is
    20. The CLI advertises `--slot 00:10`, and a self-hosted schedule 20
    minutes away on the other side of midnight is exactly the contention the
    check exists to find -- so the distance has to close the circle.
    """
    delta = abs(first - second)
    return min(delta, 1440 - delta)


def _slot_minutes(slot: str) -> int:
    try:
        hours, minutes = slot.split(":")
        value = int(hours) * 60 + int(minutes)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"slot {slot!r} is not HH:MM") from exc
    if not 0 <= value < 24 * 60:
        raise ValueError(f"slot {slot!r} is out of range")
    return value


def self_hosted_neighbours(
    result: ScanResult,
    slot: str,
    margin_minutes: int,
    exclude: set[str] | None = None,
) -> list[tuple[int, Schedule, str]]:
    """(minutes_away, schedule, clock_time) for every self-hosted schedule
    within `margin_minutes` of the slot, nearest first.

    `exclude` names the workflows that OWN the slot. A build is not in
    contention with itself: `build-images.yml` at 04:23 is 0 minutes from
    04:23, and counting it would make every slot look contended.
    """
    exclude = exclude or set()
    slot_minutes = _slot_minutes(slot)
    found: list[tuple[int, Schedule, str]] = []
    for schedule in result.schedules:
        if not schedule.self_hosted:
            continue
        if schedule.workflow in exclude:
            continue
        for clock in schedule.clock_times:
            distance = _circular_distance(_to_minutes(clock), slot_minutes)
            if distance <= margin_minutes:
                found.append((distance, schedule, clock))
    return sorted(found, key=lambda row: row[0])


def nearest_self_hosted(
    result: ScanResult, slot: str, exclude: set[str] | None = None
) -> list[tuple[int, Schedule, str]]:
    """Every self-hosted schedule, nearest to the slot, regardless of margin."""
    exclude = exclude or set()
    slot_minutes = _slot_minutes(slot)
    found: list[tuple[int, Schedule, str]] = []
    for schedule in result.schedules:
        if not schedule.self_hosted:
            continue
        if schedule.workflow in exclude:
            continue
        for clock in schedule.clock_times:
            found.append(
                (_circular_distance(_to_minutes(clock), slot_minutes), schedule, clock)
            )
    return sorted(found, key=lambda row: row[0])


def build_payload(
    result: ScanResult,
    slot: str,
    margin_minutes: int,
    exclude: set[str] | None = None,
) -> dict:
    """The machine-readable measurement."""
    exclude = exclude or set()
    return {
        "workflows_dir": str(result.workflows_dir),
        "files_scanned": result.files_scanned,
        "files_parsed": result.files_parsed,
        "live_schedules": len(result.schedules),
        "slot": slot,
        "margin_minutes": margin_minutes,
        "excluded_workflows": sorted(exclude),
        "parse_failures": list(result.parse_failures),
        "schedules": [
            {
                "workflow": schedule.workflow,
                "cron": schedule.cron,
                "clock_times": schedule.clock_times,
                "day_note": schedule.day_note,
                "self_hosted": schedule.self_hosted,
                "runner_labels": sorted(schedule.runner_labels),
                "weekly_frequency": schedule.weekly_frequency,
            }
            for schedule in sorted(
                result.schedules, key=lambda s: (s.workflow, s.cron)
            )
        ],
        "self_hosted_within_margin": [
            {
                "workflow": schedule.workflow,
                "cron": schedule.cron,
                "clock_time": clock,
                "minutes_away": distance,
                "day_note": schedule.day_note,
            }
            for distance, schedule, clock in self_hosted_neighbours(
                result, slot, margin_minutes, exclude
            )
        ],
    }


def _print_report(
    result: ScanResult, slot: str, margin_minutes: int, exclude: set[str] | None = None
) -> None:
    exclude = exclude or set()
    print(f"=== workflows scanned: {result.files_scanned} ===")
    print(f"=== workflows parsed:  {result.files_parsed} ===")
    print(f"=== live schedules:    {len(result.schedules)} ===")
    print()
    for schedule in sorted(result.schedules, key=lambda s: (s.workflow, s.cron)):
        kind = "SELF-HOSTED" if schedule.self_hosted else "HOSTED"
        times = ", ".join(schedule.clock_times[:8])
        owner = " (slot owner)" if schedule.workflow in exclude else ""
        print(
            f"  {schedule.workflow:<40} {schedule.cron:<16} {kind:<12} "
            f"{times:<34} {schedule.weekly_frequency}/week  {schedule.day_note}{owner}"
        )
    print()
    print(f"=== self-hosted schedules within {margin_minutes} min of {slot} ===")
    neighbours = self_hosted_neighbours(result, slot, margin_minutes, exclude)
    if not neighbours:
        print("  (none)")
    for distance, schedule, clock in neighbours:
        print(
            f"  {clock} ({distance} min)  {schedule.workflow:<40} "
            f"{schedule.cron:<16} {schedule.day_note}"
        )
    print()
    print("=== nearest self-hosted schedules, any distance ===")
    for distance, schedule, clock in nearest_self_hosted(result, slot, exclude)[:6]:
        print(
            f"  {clock} ({distance} min)  {schedule.workflow:<40} {schedule.cron}"
        )
    if result.parse_failures:
        print()
        print("=== PARSE FAILURES (the population below is INCOMPLETE) ===")
        for failure in result.parse_failures:
            print(f"  {failure}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Measure the fleet's scheduled workflows and check that the image-build "
            "slot is clear of self-hosted contention."
        )
    )
    parser.add_argument(
        "--workflows",
        default=str(DEFAULT_WORKFLOWS),
        help="directory holding the workflow files (default: the repo's)",
    )
    parser.add_argument("--slot", default=DEFAULT_SLOT, help="HH:MM build slot")
    parser.add_argument(
        "--margin",
        type=int,
        default=DEFAULT_MARGIN_MINUTES,
        help="minutes within which a self-hosted schedule counts as contention",
    )
    parser.add_argument(
        "--exclude-workflow",
        action="append",
        default=None,
        help=(
            "workflow to ADD to the exclusion set (repeatable). The set always "
            "contains the slot owner; this flag adds to it, never replaces it."
        ),
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit 1 when a self-hosted schedule is within the margin",
    )
    parser.add_argument("--json", action="store_true", help="emit JSON")
    args = parser.parse_args(argv)

    # The exclusion is a UNION with the default, not a replacement of it: one
    # `--exclude-workflow notes.yml` must not make the slot owner's own
    # exclusion evaporate, or the build would be reported as contending with
    # itself at distance 0 and `--check` would exit CONTENTION about the very
    # job that owns the slot.
    exclude = DEFAULT_EXCLUDED_WORKFLOWS | set(args.exclude_workflow or ())

    try:
        _slot_minutes(args.slot)
    except ValueError as exc:
        print(f"measure-schedule-contention: {exc}", file=sys.stderr)
        return EXIT_UNMEASURED

    result = scan_workflows(Path(args.workflows))
    payload = build_payload(result, args.slot, args.margin, exclude)

    if args.json:
        json.dump(payload, sys.stdout, indent=2, sort_keys=True)
        print()
    else:
        _print_report(result, args.slot, args.margin, exclude)

    # FAIL CLOSED: a fleet that could not be fully read is NOT a fleet with no
    # contention. Exiting 0 here would be exactly the fail-open the first
    # version of this measurement had.
    if not result.fully_read:
        print(
            "measure-schedule-contention: NOT MEASURED - "
            f"{len(result.parse_failures)} workflow file(s) could not be read; "
            "the population above is INCOMPLETE.",
            file=sys.stderr,
        )
        return EXIT_UNMEASURED

    if args.check:
        neighbours = payload["self_hosted_within_margin"]
        if neighbours:
            print(
                "measure-schedule-contention: CONTENTION - "
                f"{len(neighbours)} self-hosted schedule(s) within "
                f"{args.margin} min of {args.slot}.",
                file=sys.stderr,
            )
            return EXIT_CONTENTION
        print(
            f"measure-schedule-contention: CLEAR - no self-hosted schedule "
            f"within {args.margin} min of {args.slot}."
        )

    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
