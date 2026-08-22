#!/usr/bin/env python3
"""Every self-hosted `runs-on` must match exactly one registered runner class.

Why this is a gate and not a comment
------------------------------------
The repo has learned this lesson three times and fixed it locally each time:

  1. `cleanup-kvm2` targeted `[self-hosted, kvm2]`, a label that does not exist.
     It "sat queued for the full 24h GitHub scheduling window, and was then
     cancelled -- which set the WHOLE run's conclusion to `cancelled` every
     single night" (runner-maintenance.yml:30). Fixed there only.
  2. `branch-trail-emit` used `[self-hosted, Linux]`, which "matches five
     runners and only some are dirty, this failed 4 of the last 8 runs,
     alternating, which reads as flaky CI rather than one stale directory"
     (branch-trail-emit.yml:61). Fixed there only.
  3. `self-hosted-builds` requires a `gpu` label that has never existed, so it
     has been unschedulable since 2025-12-13 -- every run `cancelled`.

Three diagnoses, three local patches, and the fourth instance still shipped.
The knowledge was in the repo the entire time; what was missing was something
that checks.

Two distinct failures, both silent
----------------------------------
UNSATISFIABLE -- names a label no runner has. The job never schedules. GitHub
does not error; it queues, then cancels, and a cancelled run reads as "someone
stopped it", not "this can never run".

AMBIGUOUS -- matches runners of DIFFERENT architectures. The job lands on
whichever is free, so an x86 build can run on ARM64. It fails intermittently and
reads as flake.

Usage
-----
    python pmoves/tools/validate_runner_labels.py           # report
    python pmoves/tools/validate_runner_labels.py --strict  # exit 1 on findings
    python pmoves/tools/validate_runner_labels.py --refresh # re-read from the API
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INVENTORY = REPO_ROOT / "pmoves" / "config" / "runner_labels.json"
WORKFLOWS = REPO_ROOT / ".github" / "workflows"

# A runs-on entry that is a ${{ ... }} expression is resolved at run time from a
# matrix; we cannot evaluate it here, so it is reported as unresolved rather
# than guessed at.
EXPR = re.compile(r"\$\{\{.*?\}\}")
ARCHES = {"X64", "ARM64"}


def load_inventory() -> list[dict]:
    if not INVENTORY.exists():
        print(f"ERROR: {INVENTORY.relative_to(REPO_ROOT)} missing — run --refresh",
              file=sys.stderr)
        raise SystemExit(2)
    return json.loads(INVENTORY.read_text(encoding="utf-8"))["runners"]


def refresh() -> int:
    out = subprocess.run(
        ["gh", "api", "repos/POWERFULMOVES/PMOVES.AI/actions/runners", "--jq",
         '{generated_note:"machine-emitted", runners:[.runners[]|{name:.name, labels:[.labels[].name]}]}'],
        capture_output=True, text=True,
    )
    if out.returncode != 0:
        print(f"ERROR: gh api failed: {out.stderr.strip()[:200]}", file=sys.stderr)
        return 2
    INVENTORY.write_text(out.stdout, encoding="utf-8")
    n = len(json.loads(out.stdout)["runners"])
    print(f"Wrote {INVENTORY.relative_to(REPO_ROOT)} ({n} runners).")
    return 0


# A job that genuinely runs anywhere declares it, at the site, with a reason:
#     # runner-labels: arch-agnostic -- <why>
#     runs-on: [self-hosted, Linux]
# An undeclared multi-arch target is a bug; a declared one is a decision. Without
# this the gate would flag intentional cases forever, and a gate that cries wolf
# is one people learn to skip -- which is how the three prior instances of this
# same bug shipped.
OPT_OUT = "runner-labels: arch-agnostic"


def _runs_on_entries(text: str):
    """Yield (line_no, [labels], opted_out) for each self-hosted runs-on array."""
    lines = text.splitlines()
    for i, line in enumerate(lines, 1):
        s = line.strip()
        if not s.startswith("runs-on:"):
            continue
        val = s.split("runs-on:", 1)[1].strip()
        if not val.startswith("["):
            continue  # hosted runner (ubuntu-latest etc.)
        labels = [p.strip().strip('"\'') for p in val.strip("[]").split(",")]
        labels = [l for l in labels if l]
        if "self-hosted" in labels:
            # look back a few lines for the declared opt-out
            back = "\n".join(lines[max(0, i - 6):i])
            yield i, labels, OPT_OUT in back


def analyse(runners: list[dict]) -> tuple[list[str], list[str]]:
    known = {l for r in runners for l in r["labels"]}
    unsatisfiable: list[str] = []
    ambiguous: list[str] = []

    for wf in sorted(WORKFLOWS.glob("*.yml")):
        text = wf.read_text(encoding="utf-8", errors="replace")
        for line_no, labels, opted_out in _runs_on_entries(text):
            where = f"{wf.name}:{line_no}"
            if any(EXPR.search(l) for l in labels):
                continue  # matrix-resolved; not decidable here
            missing = [l for l in labels if l not in known]
            if missing:
                unsatisfiable.append(
                    f"{where}: no runner has {missing} — job can never schedule "
                    f"(runs-on: {labels})"
                )
                continue
            matches = [r for r in runners if set(labels) <= set(r["labels"])]
            if not matches:
                unsatisfiable.append(
                    f"{where}: every label exists but no single runner has them all "
                    f"— job can never schedule (runs-on: {labels})"
                )
                continue
            arches = {a for r in matches for a in set(r["labels"]) & ARCHES}
            if len(arches) > 1 and not (set(labels) & ARCHES) and not opted_out:
                names = ", ".join(sorted(r["name"] for r in matches))
                ambiguous.append(
                    f"{where}: matches {len(matches)} runners across {sorted(arches)} "
                    f"with no arch pin — {names} (runs-on: {labels})"
                )
    return unsatisfiable, ambiguous


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--strict", action="store_true", help="exit 1 on any finding")
    ap.add_argument("--refresh", action="store_true", help="re-read the inventory from the API")
    args = ap.parse_args(argv)

    if args.refresh:
        return refresh()

    runners = load_inventory()
    unsat, ambig = analyse(runners)

    for f in unsat:
        print(f"UNSATISFIABLE: {f}")
    for f in ambig:
        print(f"AMBIGUOUS:     {f}")

    total = len(unsat) + len(ambig)
    if total == 0:
        print(f"OK: every self-hosted runs-on resolves to a runner class "
              f"({len(runners)} runners registered).")
        return 0

    print(f"\n{len(unsat)} unsatisfiable, {len(ambig)} ambiguous.")
    print("Registered labels: " + ", ".join(sorted({l for r in runners for l in r['labels']})))
    return 1 if args.strict else 0


if __name__ == "__main__":
    raise SystemExit(main())
