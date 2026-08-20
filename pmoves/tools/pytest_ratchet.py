#!/usr/bin/env python3
"""Run the Python test suite and ratchet it: fail on NEW failures, not old ones.

Why this exists
---------------
The `python-tests` job in `.github/workflows/merge-gate.yml` was a required
status check on `main` that could not fail:

    find . -name 'test_*.py' ... | head -20 | xargs pytest --tb=short -q || true

`head -20` handed pytest at most 20 of the repo's 264 test files, chosen by
filesystem order (which puts `.claude/hooks/`, `.minimax/` and
`CATACLYSM_STUDIOS_INC/` first, so the service tests mostly never ran), and
`|| true` discarded the exit code. A representative run reported *pass* on
`collected 455 items / 4 errors / 2 skipped` — zero tests executed.

Removing `|| true` alone would turn `main` red across 264 files at once, and the
honest response to a wall of red is to revert the gate. So this follows the same
ratchet the repo already uses for command anchors, Dockerfile paths and
composes: record today's failures as a baseline, then fail the build on anything
NEW, and on anything baselined that has since been FIXED (a stale entry), so the
count can only go down.

Baselined is not approved. Every entry is a real failing test or a module that
cannot even be imported.

Usage
-----
    python pmoves/tools/pytest_ratchet.py                  # gate (CI)
    python pmoves/tools/pytest_ratchet.py --write-baseline # re-record
    python pmoves/tools/pytest_ratchet.py --json           # machine-readable
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Set

REPO_ROOT = Path(__file__).resolve().parents[2]
PMOVES = REPO_ROOT / "pmoves"
BASELINE = PMOVES / "configs" / "pytest_ratchet" / "_known_failures.yaml"

# Per-group wall clock. A gate has to be bounded: some suites reach for a live
# service and block until their own timeout, and one of those must not be able to
# eat the job budget. A group that exceeds this is recorded as a finding, so a
# hang is visible and ratchetable instead of being an infrastructure mystery.
GROUP_TIMEOUT_SECONDS = int(os.environ.get("PYTEST_RATCHET_GROUP_TIMEOUT", "120"))

# Groups are further chunked so that one hang hides as little as possible. The
# pmoves/tests group alone holds 88 files; when it timed out, every result in it
# collapsed into a single "no report" entry and real findings inside it -- such
# as the hyphen-in-import-path syntax error in test_issue_triage.py -- were
# invisible. Chunking does not change semantics: the same conftest still
# applies to each file.
CHUNK_SIZE = int(os.environ.get("PYTEST_RATCHET_CHUNK_SIZE", "20"))

# When a chunk times out, pytest is killed before it writes its JUnit report, so
# EVERY result in that chunk is lost -- passes and failures alike, not just the
# hang. Measured 2026-08-19: `pmoves/tests [1]` timed out on every run on record,
# and the 20 files inside it included 66 failures in test_docker_hardening.py and
# 25 in test_gateway_agent_integration.py that had never once been reported. The
# baseline recorded the silence; it could not record what the silence contained.
#
# So a timed-out chunk is now re-run one file at a time. Only the file that
# actually hangs stays unmeasured; the other 19 report normally. The cost is paid
# only when a chunk times out, and is bounded by FALLBACK_BUDGET_SECONDS so a
# chunk full of hangs cannot eat the job.
FALLBACK_FILE_TIMEOUT = int(os.environ.get("PYTEST_RATCHET_FILE_TIMEOUT", "60"))
FALLBACK_BUDGET_SECONDS = int(os.environ.get("PYTEST_RATCHET_FALLBACK_BUDGET", "600"))

# Mirrors the workflow's original discovery exactly, minus the `head -20` cap.
# Kept identical on purpose: this change removes a cap and adds a ratchet, it
# does not silently redefine which tests are in scope.
#
# `.claude` is excluded for a reason that only bites OFF CI: git worktrees live
# under `.claude/worktrees/`, each a full copy of the repo. In CI's fresh
# checkout there are none, so this changes nothing there. On a developer machine
# with worktrees checked out, discovery went from 29 groups to 427 — every test
# file counted once per worktree. That matters because the gate's own failure
# message instructs you to run `make -C pmoves python-tests-baseline`, and doing
# so from a machine with worktrees would have written a baseline full of
# duplicated, worktree-scoped keys that CI can never reproduce. The documented
# recovery command has to be safe to actually run.
EXCLUDE_PARTS = (
    "venv",
    "node_modules",
    ".git",
    "__pycache__",
    "site-packages",
    ".claude",
)


def discover_test_files() -> List[Path]:
    """Every `test_*.py` in the parent repo, excluding vendored trees.

    In CI `actions/checkout` runs with `submodules: false`, so submodule
    directories are empty and contribute nothing here.
    """
    found: List[Path] = []
    for p in REPO_ROOT.rglob("test_*.py"):
        rel = p.relative_to(REPO_ROOT)
        if any(part in EXCLUDE_PARTS for part in rel.parts):
            continue
        found.append(rel)
    return sorted(found)


def _as_text(value) -> str:
    """Decode a subprocess stream that may be str, bytes, or None."""
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return value


def group_files(files: List[Path]) -> Dict[str, List[Path]]:
    """Group tests by their nearest ancestor `conftest.py` directory.

    Runs are per-group rather than one session over all 264 files because a
    conftest that cannot be imported aborts the entire session --
    `--continue-on-collection-errors` does not cover conftest import failures.
    One service with a missing dependency would otherwise hide every other
    test in the repo, which is the exact failure mode this gate exists to end.
    Grouping also keeps two conftests from colliding in one plugin registry.
    """
    groups: Dict[str, List[Path]] = {}
    for f in files:
        anchor = f.parent
        probe = f.parent
        while True:
            if (REPO_ROOT / probe / "conftest.py").is_file():
                anchor = probe
                break
            if probe == Path(".") or probe.parent == probe:
                break
            probe = probe.parent
        groups.setdefault(anchor.as_posix(), []).append(f)

    chunked: Dict[str, List[Path]] = {}
    for name, gfiles in groups.items():
        if len(gfiles) <= CHUNK_SIZE:
            chunked[name] = gfiles
            continue
        for i in range(0, len(gfiles), CHUNK_SIZE):
            part = i // CHUNK_SIZE + 1
            chunked[f"{name} [{part}]"] = gfiles[i:i + CHUNK_SIZE]
    return chunked


def run_pytest(files: List[Path], junit: Path,
                timeout: Optional[int] = None) -> tuple[int, str]:
    """Run pytest over `files`, collecting results into a JUnit XML report.

    `--continue-on-collection-errors` matters: without it a single unimportable
    module aborts the whole run, which is how 4 collection errors were able to
    hide 455 collected tests.
    """
    cmd = [
        sys.executable, "-m", "pytest",
        # Every option is set explicitly rather than inherited from whichever
        # config file pytest happens to discover. Passing files from the repo
        # root moves rootdir off pmoves/, so pmoves/pyproject.toml's
        # [tool.pytest.ini_options] may not apply at all -- and silently losing
        # import-mode/asyncio-mode is the kind of environment-dependence this
        # gate exists to stop.
        "-o", "addopts=",              # drop inherited -v/--tb/--strict-markers
        "-o", "asyncio_mode=auto",     # pmoves tests rely on this
        # Two different tests/conftest.py both resolved to the module name
        # "tests.conftest" and pytest aborted the whole session with
        # "Plugin already registered under a different name". Considering
        # namespace packages derives the module name from the full path.
        "-o", "consider_namespace_packages=true",
        "--import-mode=importlib",     # 264 files across the repo share basenames;
                                       # prepend-mode makes those a hard error
        "--continue-on-collection-errors",
        "-p", "no:cacheprovider",
        f"--junit-xml={junit}",
        "--tb=no", "-q",
        *[str(f) for f in files],
    ]
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
    try:
        proc = subprocess.run(cmd, cwd=REPO_ROOT, env=env, text=True,
                              capture_output=True,
                              timeout=timeout or GROUP_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired as exc:
        # subprocess returns TimeoutExpired.stdout/.stderr as raw bytes on some
        # platforms even with text=True, so each is decoded on its own rather
        # than concatenated first (that raised "can't concat str to bytes" on
        # Linux CI while being fine locally on Windows).
        partial = _as_text(exc.stdout) + _as_text(exc.stderr)
        return -1, f"TIMEOUT after {timeout or GROUP_TIMEOUT_SECONDS}s{chr(10)}{partial}"
    # Pytest output is returned, never written to stdout: stdout carries only
    # this tool's report (and --json must stay parseable). Callers surface it
    # on stderr for groups that actually failed to produce a report.
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def parse_junit(junit: Path) -> List[dict]:
    """Extract failures and collection errors from the JUnit report.

    JUnit XML is used rather than scraping the terminal summary because the
    attribute set is stable across pytest versions; the summary format is not.
    """
    if not junit.is_file():
        return []
    findings: List[dict] = []
    root = ET.parse(junit).getroot()
    for case in root.iter("testcase"):
        kind = None
        detail = ""
        for child in case:
            if child.tag == "failure":
                kind = "FAIL"
            elif child.tag == "error":
                kind = "ERROR"
            else:
                continue
            detail = (child.get("message") or "").strip().splitlines()[0][:160] \
                if child.get("message") else ""
            break
        if kind is None:
            continue
        # classname first: it is a dotted module path, so it carries no OS path
        # separator and a baseline recorded on Linux CI matches a local Windows
        # run. `file` is the fallback for collection errors with no classname.
        where = case.get("classname") or case.get("file") or ""
        name = case.get("name") or "<unknown>"
        if not where:
            # A collection error has no classname; pytest puts the module's
            # dotted path in `name`. Move it to `where` so the baseline reads as
            # "this module cannot be imported" rather than "<unknown>".
            where, name = name, "<collection-error>"
        findings.append({
            "kind": kind,
            "where": where.replace(chr(92), "/"),
            "name": name,
            "detail": detail,
        })
    return findings


def _key(f: dict) -> str:
    """`KIND|path|test-name` — same shape as the other ratchets in this repo.

    The failure *message* is deliberately excluded: it changes with library
    versions and would churn the baseline without the set of broken things
    having changed.
    """
    return f"{f['kind']}|{f['where']}|{f['name']}"


def load_baseline() -> Set[str]:
    if not BASELINE.is_file():
        return set()
    keys: Set[str] = set()
    for line in BASELINE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("- "):
            keys.add(line[2:].strip().strip('"'))
    return keys


def write_baseline(findings: List[dict]) -> None:
    BASELINE.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Baselined Python test failures — pytest_ratchet.py",
        "#",
        "# Each entry is a test that FAILS or a module that cannot be imported,",
        "# as of the day the gate was made capable of failing. They are recorded",
        "# so `python-tests` can be enforced today without turning main red in a",
        "# single step. They are NOT approved, and none of them is 'expected'.",
        "#",
        "# The list may shrink and must never silently grow. Removing an entry is",
        "# the goal; adding one should require saying why in the PR.",
        "#",
        "# Regenerate: make -C pmoves python-tests-baseline",
        "known_failures:",
    ]
    for k in sorted({_key(f) for f in findings}):
        lines.append(f'  - "{k}"')
    BASELINE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_chunk_with_fallback(group: str, gfiles: List[Path], tmp: Path,
                            index: int) -> tuple[List[dict], List[str]]:
    """Run a group; if it times out, re-run it one file at a time.

    Returns (findings, dead_labels). `dead_labels` names whatever stayed
    unmeasured -- the whole group if the fallback could not run, or the specific
    files that hang.

    A timed-out chunk is killed before pytest writes its JUnit report, so
    treating the timeout as one opaque "no report" discards every result in the
    chunk. Isolating per file narrows the loss to the file that actually hangs.
    """
    junit = tmp / f"report-{index}.xml"
    rc, output = run_pytest(gfiles, junit)
    if junit.is_file():
        return parse_junit(junit), []

    if rc != -1 or len(gfiles) <= 1:
        # Not a timeout (unimportable conftest, usage error, crash), or nothing
        # left to split. Per-file isolation cannot help either case.
        sys.stderr.write("--- no report for %s (exit %d) ---%s%s%s" % (
            group, rc, chr(10), output[-1500:], chr(10)))
        return [], [group]

    sys.stderr.write(
        "--- %s timed out; isolating %d files (budget %ds) ---%s" % (
            group, len(gfiles), FALLBACK_BUDGET_SECONDS, chr(10)))

    findings: List[dict] = []
    dead: List[str] = []
    spent = 0.0
    for j, f in enumerate(gfiles):
        if spent >= FALLBACK_BUDGET_SECONDS:
            # Honest about what was NOT measured. Silently stopping here would
            # reintroduce the defect this function exists to fix.
            remaining = [str(x).replace(chr(92), "/") for x in gfiles[j:]]
            sys.stderr.write(
                "--- fallback budget exhausted; %d files unmeasured ---%s" % (
                    len(remaining), chr(10)))
            dead.extend(remaining)
            break
        sub = tmp / f"report-{index}-{j}.xml"
        start = time.monotonic()
        frc, foutput = run_pytest([f], sub, timeout=FALLBACK_FILE_TIMEOUT)
        spent += time.monotonic() - start
        if sub.is_file():
            findings.extend(parse_junit(sub))
            continue
        label = str(f).replace(chr(92), "/")
        sys.stderr.write("---   no report for %s (exit %d) ---%s%s%s" % (
            label, frc, chr(10), foutput[-600:], chr(10)))
        dead.append(label)
    return findings, dead


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--write-baseline", action="store_true")
    args = ap.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    files = discover_test_files()
    if not files:
        print("ERROR: no test_*.py discovered — wrong repo root?", file=sys.stderr)
        return 2

    groups = group_files(files)
    findings: List[dict] = []
    dead_groups = 0
    with tempfile.TemporaryDirectory() as tmp:
        for i, (group, gfiles) in enumerate(sorted(groups.items()), 1):
            sys.stderr.write("[%d/%d] %s (%d files)%s" % (i, len(groups), group, len(gfiles), chr(10)))
            gfindings, dead = run_chunk_with_fallback(group, gfiles, Path(tmp), i)
            findings.extend(gfindings)
            for label in dead:
                # pytest never wrote a report for this unit: a conftest that
                # cannot be imported, a usage error, a crash, or a hang that
                # survived per-file isolation. Recorded as a finding so it is
                # visible and ratchetable, rather than being mistaken for
                # "no failures here".
                dead_groups += 1
                findings.append({
                    "kind": "ERROR",
                    # Chunk suffix stripped: "[2]" is a positional label, so
                    # keying on it would churn the baseline every time a test
                    # file is added anywhere earlier in the group. A per-file
                    # label carries no such suffix and needs no stripping --
                    # and, unlike the chunk label, it names the actual hang.
                    "where": label.split(" [")[0],
                    "name": "<pytest-harness>",
                    "detail": "pytest produced no report for this unit",
                })
    # stderr: stdout must stay pure so --json is parseable.
    sys.stderr.write("Groups run: %d%s%s" % (
        len(groups),
        (" (%d produced no report)" % dead_groups) if dead_groups else "",
        chr(10)))

    if args.write_baseline:
        write_baseline(findings)
        n = len({_key(f) for f in findings})
        print(f"Baseline written: {n} entries -> {BASELINE.relative_to(REPO_ROOT)}")
        return 0

    baseline = load_baseline()
    live = {_key(f) for f in findings}
    new = [f for f in findings if _key(f) not in baseline]
    # A baselined entry that no longer occurs was FIXED. Leaving it would let
    # the same breakage return silently, which contradicts the count-only-down
    # claim this ratchet makes.
    stale = sorted(baseline - live)

    if args.json:
        print(json.dumps({
            "test_files": len(files),
            "total": len(findings),
            "baselined": len(findings) - len(new),
            "new": new,
            "stale_baseline": stale,
        }, indent=2))
        return 1 if (new or stale) else 0

    by_kind: Dict[str, int] = {}
    for f in findings:
        by_kind[f["kind"]] = by_kind.get(f["kind"], 0) + 1
    print(f"Test files run: {len(files)}")
    print("Findings by kind: " + (", ".join(f"{k}={v}" for k, v in sorted(by_kind.items())) or "none"))
    print(f"Test findings: {len(findings)} total, {len(findings) - len(new)} baselined, {len(new)} new")

    if new:
        print(f"\nNEW failures — {len(new)} not in the baseline:")
        # Printed in exact baseline-key form so a deliberate re-baseline can be
        # lifted straight out of a CI log without retyping.
        for f in new[:500]:
            print(f"  {_key(f)}")
            if f["detail"]:
                print(f"        {f['detail']}")
        if len(new) > 500:
            print(f"  ... and {len(new) - 500} more (raise the cap to re-baseline)")
        print("\nFix them, or — if they are pre-existing and you are only moving them —")
        print("record them deliberately:")
        print("  make -C pmoves python-tests-baseline")

    if stale:
        print(f"\nSTALE BASELINE — {len(stale)} entr{'y' if len(stale) == 1 else 'ies'} no longer fail:")
        # Printed in FULL, deliberately unlike `new` above. The stale list is the
        # only actionable output this branch produces: `--write-baseline` cannot be
        # run anywhere but CI (discovery walks git worktrees under .claude/ and
        # populated submodules, neither of which exists in CI's checkout — a
        # developer machine reported 398 groups against CI's 29). So the operator
        # has to prune these by hand from the CI log, and truncating at 40 removed
        # exactly the information needed to do it. A list you are told to act on
        # should not be abbreviated.
        for k in stale:
            print(f"  {k}")
        print("\nThese were fixed. Drop them so the same breakage cannot return silently:")
        print("  make -C pmoves python-tests-baseline   (CI only — see note above)")

    if not new and not stale:
        print("PASS — no failures outside the baseline, no stale entries.")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
