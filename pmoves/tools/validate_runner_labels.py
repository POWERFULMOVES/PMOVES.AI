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

import yaml
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

# A matrix resolved at run time (fromJson of a previous job's output) genuinely
# cannot be expanded here. Blocking on it forever would make this gate cry wolf,
# and a gate people learn to skip is how the four prior instances shipped. So:
# undeclared is a failure, declared is a decision -- the same contract as the
# arch opt-out, and it forces the reason to be written down at the site.
OPT_OUT_RUNTIME = "runner-labels: runtime-resolved"


def _opted_out(text: str, job: str, marker: str = OPT_OUT) -> bool:
    """Is the declared opt-out present inside THIS job's block?

    Searching the whole file would let one job's declaration silence every other
    job in it -- a gate that can be switched off from a distance is not a gate.
    """
    lines = text.splitlines()
    start = next((i for i, l in enumerate(lines) if l.startswith(f"  {job}:")), None)
    if start is None:
        return False
    end = next(
        (i for i in range(start + 1, len(lines))
         if re.match(r"^  [A-Za-z0-9_-]+:", lines[i])),
        len(lines),
    )
    return marker in "\n".join(lines[start:end])


def _job_line(text: str, job: str) -> int:
    """Best-effort source line for a job key, for reporting only."""
    for i, line in enumerate(text.splitlines(), 1):
        if line.startswith(f"  {job}:"):
            return i
    return 0


def _is_disabled(job: dict) -> bool:
    """True when the job's `if` is a literal false that no context can flip.

    A job that cannot run cannot fail to schedule, so its runs-on is not a
    finding. Only a LEADING literal `false` counts -- `false && (...)` is a
    deliberate disable, while `github.x == false` is a real predicate.

    This must be one key. A second `if:` in the same mapping does not error;
    YAML lets the later one silently win, so a disable written above an existing
    predicate evaporates. (Caught in review on this very file's PR.)
    """
    cond = job.get("if")
    if not isinstance(cond, (str, bool)):
        return False
    if cond is False:
        return True
    return re.match(r"^\s*false\s*(&&|$)", str(cond)) is not None


def _matrix_combos(job: dict) -> tuple[list[dict], list[str]]:
    """Expand a literal matrix into concrete variable bindings.

    Returns (combinations, unresolved_reasons). An expression-valued matrix
    cannot be expanded here; it is REPORTED rather than skipped, because a
    silently-skipped lane is exactly how an unschedulable matrix passes a gate
    built to catch unschedulable jobs.
    """
    strategy = job.get("strategy")
    if not isinstance(strategy, dict):
        return [{}], []
    matrix = strategy.get("matrix")
    if not isinstance(matrix, dict):
        if matrix is not None:
            return [{}], ["matrix is an expression; lanes not statically known"]
        return [{}], []

    unresolved: list[str] = []
    axes = {k: v for k, v in matrix.items() if k not in ("include", "exclude")}
    combos: list[dict] = [{}]
    for key, values in axes.items():
        if not isinstance(values, list):
            unresolved.append(f"matrix.{key} is not a literal list")
            continue
        expanded = []
        for combo in combos:
            for v in values:
                expanded.append({**combo, key: v})
        combos = expanded or combos

    include = matrix.get("include")
    if isinstance(include, list):
        literal = [i for i in include if isinstance(i, dict)]
        if literal:
            # `include` entries here fully specify their own lane.
            combos = literal if not axes else combos + literal
    elif include is not None:
        unresolved.append("matrix.include is an expression")

    return combos, unresolved


_MATRIX_REF = re.compile(r"\$\{\{\s*matrix\.([A-Za-z0-9_-]+)\s*\}\}")


def _resolve(label: str, binding: dict) -> tuple[str, bool]:
    """Substitute matrix refs. Returns (resolved, fully_resolved)."""
    def sub(m):
        key = m.group(1)
        return str(binding[key]) if key in binding else m.group(0)
    out = _MATRIX_REF.sub(sub, label)
    return out, EXPR.search(out) is None


def _runs_on_labels(runs_on) -> list[str] | None:
    """Normalise runs-on into a label list, or None when it is not an array."""
    if isinstance(runs_on, list):
        return [str(x).strip().strip('"\'') for x in runs_on if str(x).strip()]
    return None


def analyse(runners: list[dict]) -> tuple[list[str], list[str], list[str]]:
    known = {l for r in runners for l in r["labels"]}
    names = {r["name"] for r in runners}
    unsatisfiable: list[str] = []
    ambiguous: list[str] = []
    unverifiable: list[str] = []

    for wf in sorted(WORKFLOWS.glob("*.yml")):
        text = wf.read_text(encoding="utf-8", errors="replace")
        try:
            doc = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            unsatisfiable.append(f"{wf.name}: unparseable ({str(exc)[:80]})")
            continue
        if not isinstance(doc, dict):
            continue
        jobs = doc.get("jobs")
        if not isinstance(jobs, dict):
            continue

        for job_name, job in jobs.items():
            if not isinstance(job, dict) or _is_disabled(job):
                continue
            labels = _runs_on_labels(job.get("runs-on"))
            if labels is None or "self-hosted" not in labels:
                continue

            where = f"{wf.name}:{_job_line(text, str(job_name))} ({job_name})"
            opted_out = _opted_out(text, str(job_name))
            combos, unresolved = _matrix_combos(job)
            # An unexpandable matrix only matters if runs-on DEPENDS on it. Most
            # matrices name build targets, not runners; flagging those is the
            # cry-wolf failure this tool's own docstring warns about.
            depends_on_matrix = any(_MATRIX_REF.search(l) for l in labels)
            if unresolved and depends_on_matrix:
                if _opted_out(text, str(job_name), OPT_OUT_RUNTIME):
                    continue
                unverifiable.append(
                    f"{where}: {unresolved[0]} — runs-on depends on it "
                    f"(runs-on: {labels}), so no lane can be checked"
                )
                continue

            for binding in combos:
                resolved = []
                blocked = False
                for l in labels:
                    r, ok = _resolve(l, binding)
                    if not ok:
                        if _opted_out(text, str(job_name), OPT_OUT_RUNTIME):
                            blocked = True
                            break
                        unverifiable.append(
                            f"{where}: {l} does not resolve from this matrix lane "
                            f"(runs-on: {labels})"
                        )
                        blocked = True
                        break
                    resolved.append(r)
                if blocked:
                    continue

                missing = [l for l in resolved if l not in known]
                if missing:
                    hint = ""
                    name_like = [m for m in missing if m in names]
                    if name_like:
                        hint = (
                            f" — {name_like} is a runner NAME, not a label; "
                            f"`runs-on` matches labels only"
                        )
                    unsatisfiable.append(
                        f"{where}: no runner has {missing} — job can never schedule"
                        f"{hint} (runs-on: {resolved})"
                    )
                    continue
                matches = [r for r in runners if set(resolved) <= set(r["labels"])]
                if not matches:
                    unsatisfiable.append(
                        f"{where}: every label exists but no single runner has them all "
                        f"— job can never schedule (runs-on: {resolved})"
                    )
                    continue
                arches = {a for r in matches for a in set(r["labels"]) & ARCHES}
                if len(arches) > 1 and not (set(resolved) & ARCHES) and not opted_out:
                    who = ", ".join(sorted(r["name"] for r in matches))
                    ambiguous.append(
                        f"{where}: matches {len(matches)} runners across {sorted(arches)} "
                        f"with no arch pin — {who} (runs-on: {resolved})"
                    )
    return unsatisfiable, ambiguous, unverifiable


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--strict", action="store_true", help="exit 1 on any finding")
    ap.add_argument("--refresh", action="store_true", help="re-read the inventory from the API")
    args = ap.parse_args(argv)

    if args.refresh:
        return refresh()

    runners = load_inventory()
    unsat, ambig, unver = analyse(runners)

    for f in unsat:
        print(f"UNSATISFIABLE: {f}")
    for f in ambig:
        print(f"AMBIGUOUS:     {f}")
    # Kept a separate category on purpose. "I checked and it cannot schedule" and
    # "I could not check" are different claims, and collapsing them into one
    # number is how a gate ends up reporting coverage it does not have.
    for f in unver:
        print(f"UNVERIFIABLE:  {f}")

    total = len(unsat) + len(ambig) + len(unver)
    if total == 0:
        print(f"OK: every self-hosted runs-on resolves to a runner class "
              f"({len(runners)} runners registered).")
        return 0

    print(f"\n{len(unsat)} unsatisfiable, {len(ambig)} ambiguous, {len(unver)} unverifiable.")
    print("Registered labels: " + ", ".join(sorted({l for r in runners for l in r['labels']})))
    return 1 if args.strict else 0


if __name__ == "__main__":
    raise SystemExit(main())
