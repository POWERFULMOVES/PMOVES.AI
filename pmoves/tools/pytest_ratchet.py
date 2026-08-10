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
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Set

REPO_ROOT = Path(__file__).resolve().parents[2]
PMOVES = REPO_ROOT / "pmoves"
BASELINE = PMOVES / "configs" / "pytest_ratchet" / "_known_failures.yaml"

# Mirrors the workflow's original discovery exactly, minus the `head -20` cap.
# Kept identical on purpose: this change removes a cap and adds a ratchet, it
# does not silently redefine which tests are in scope.
EXCLUDE_PARTS = ("venv", "node_modules", ".git", "__pycache__", "site-packages")


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


def run_pytest(files: List[Path], junit: Path) -> int:
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
        "--import-mode=importlib",     # 264 files across the repo share basenames;
                                       # prepend-mode makes those a hard error
        "--continue-on-collection-errors",
        "-p", "no:cacheprovider",
        f"--junit-xml={junit}",
        "--tb=no", "-q",
        *[str(f) for f in files],
    ]
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
    proc = subprocess.run(cmd, cwd=REPO_ROOT, env=env, text=True,
                          capture_output=True)
    # Head as well as tail: a pytest usage error or a conftest import crash
    # prints at the top, and a tail-only view of a long run hides it.
    out = proc.stdout
    if len(out) > 8000:
        out = out[:3000] + "\n" + "...[trimmed]..." + "\n" + out[-5000:]
    sys.stdout.write(out)
    if proc.stderr.strip():
        err = proc.stderr
        if len(err) >= 4000:
            err = err[:2000] + "\n" + "...[trimmed]..." + "\n" + err[-2000:]
        sys.stderr.write(err)
    return proc.returncode


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
        where = case.get("classname") or case.get("file") or "<unknown>"
        findings.append({
            "kind": kind,
            "where": where.replace("\\", "/"),
            "name": case.get("name") or "<unknown>",
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

    with tempfile.TemporaryDirectory() as tmp:
        junit = Path(tmp) / "report.xml"
        rc = run_pytest(files, junit)
        findings = parse_junit(junit)
        if not junit.is_file():
            # pytest never got far enough to write a report: a usage error, an
            # import-time crash in conftest, or a missing dependency. That is a
            # real failure and must not be mistaken for "no findings".
            print(f"ERROR: pytest produced no JUnit report (exit {rc}). "
                  "This is a harness failure, not a clean run.", file=sys.stderr)
            return 2

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
        for k in stale[:40]:
            print(f"  {k}")
        if len(stale) > 40:
            print(f"  ... and {len(stale) - 40} more")
        print("\nThese were fixed. Drop them so the same breakage cannot return silently:")
        print("  make -C pmoves python-tests-baseline")

    if not new and not stale:
        print("PASS — no failures outside the baseline, no stale entries.")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
