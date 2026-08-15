#!/usr/bin/env python3
"""Worktree sitrep — what is actually dirty across every registered worktree.

WHY THIS EXISTS
---------------
`.claude/CLAUDE.md` and `.claude/PATTERNS.md` have documented
`make -C pmoves worktree-sitrep` / `-strict` as the *authoritative* worktree
check, and told readers to prefer it to per-worktree spot checks. Neither target
existed. Both were sitting in the command-anchor baseline as GHOST_TARGETs, so
anyone following the documented road got:

    make: *** No rule to make target 'worktree-sitrep-strict'.  Stop.

and fell back to hand-rolling `git status` across ~130 worktrees — which is
exactly what the doc was written to prevent.

WHAT A HAND-ROLLED SWEEP GETS WRONG
-----------------------------------
Three things, all learned the hard way:

  1. SUBMODULE NOISE. A plain `git status` reports ` M PMOVES-Archon` for every
     submodule whose checkout differs from the recorded gitlink. With ~50
     submodules that buries real work. This is gitlink drift, not uncommitted
     work, so it is separated out rather than mixed in — but NOT silently
     dropped, because "empty git output != absence" is its own trap. See
     --submodules.

  2. HUSKS. Several worktrees report thousands of modifications where every
     single entry is a deletion: the directory was emptied on disk (the
     OneDrive-lock cleanup does this) while git still tracks the files. That is
     not 5,700 pieces of uncommitted work, it is one dead registration. Counted
     and labelled separately so it cannot be mistaken for either.

  3. STALE BASE. A worktree can be clean and still be useless — the repo root
     was sitting 199 commits behind main, which caused three separate wrong
     conclusions in one session because files were read from it. Distance from
     the base branch is reported for every worktree, clean or not.

STRICT MODE
-----------
`--strict` exits non-zero when any worktree is DIRTY or CONFLICTED. Husks and
stale-but-clean worktrees do NOT fail it: they are housekeeping, not
uncommitted work, and a gate that fires on them would be muted within a week.

Usage:
    python pmoves/tools/worktree_sitrep.py            # snapshot
    python pmoves/tools/worktree_sitrep.py --strict   # gate
    python pmoves/tools/worktree_sitrep.py --json     # machine-readable
    python pmoves/tools/worktree_sitrep.py --submodules   # include gitlink drift

Exit codes:
    0 = no dirty or conflicted worktrees (or snapshot mode)
    1 = at least one dirty/conflicted worktree (--strict only)
    2 = error
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BASE_REF = "origin/main"


def _git(args: List[str], cwd: Optional[Path] = None, timeout: int = 60) -> str:
    """Run git and return stdout, or '' on any failure.

    Never raises: one unreadable worktree must not abort the sweep. Callers
    distinguish 'no output' from 'failed' via the caller-side checks below,
    which is why every consumer here treats '' as unknown rather than as clean.
    """
    try:
        r = subprocess.run(
            ["git", *args],
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return r.stdout if r.returncode == 0 else ""


def worktrees() -> List[Path]:
    out = _git(["worktree", "list", "--porcelain"], cwd=REPO_ROOT)
    return [Path(l[len("worktree "):].strip()) for l in out.splitlines() if l.startswith("worktree ")]


def classify(wt: Path, include_submodules: bool) -> Dict:
    """Classify one worktree. Never raises."""
    info: Dict = {
        "path": wt.as_posix(),
        "name": wt.name,
        "branch": "",
        "state": "unknown",
        "changed": 0,
        "deleted": 0,
        "conflicted": 0,
        "submodule_drift": 0,
        "behind": None,
        "ahead": None,
    }

    if not wt.is_dir():
        info["state"] = "missing"
        return info

    info["branch"] = _git(["branch", "--show-current"], cwd=wt).strip()

    # --ignore-submodules=all is deliberate and is reported separately below.
    # Mixing gitlink drift into the dirty count is what makes a hand sweep
    # unreadable; hiding it entirely is what makes one wrong.
    args = ["status", "--porcelain=v1"]
    if not include_submodules:
        args.append("--ignore-submodules=all")
    status = _git(args, cwd=wt)

    changed = deleted = conflicted = 0
    for line in status.splitlines():
        if len(line) < 2:
            continue
        x, y = line[0], line[1]
        if "U" in (x, y) or (x, y) in (("A", "A"), ("D", "D")):
            conflicted += 1
        elif x == "D" or y == "D":
            deleted += 1
        elif not line.startswith("??"):
            changed += 1

    if not include_submodules:
        drift = _git(["status", "--porcelain=v1"], cwd=wt)
        info["submodule_drift"] = max(0, len([l for l in drift.splitlines() if l[:2].strip()]) - (changed + deleted + conflicted))

    info["changed"], info["deleted"], info["conflicted"] = changed, deleted, conflicted

    counts = _git(["rev-list", "--left-right", "--count", f"{BASE_REF}...HEAD"], cwd=wt).split()
    if len(counts) == 2:
        info["behind"], info["ahead"] = int(counts[0]), int(counts[1])

    if conflicted:
        info["state"] = "conflicted"
    elif deleted and not changed:
        # Every tracked entry gone from disk: an emptied directory, not work.
        info["state"] = "husk"
    elif changed or deleted:
        info["state"] = "dirty"
    else:
        info["state"] = "clean"
    return info


def main() -> int:
    ap = argparse.ArgumentParser(description="Worktree sitrep across all registered worktrees.")
    ap.add_argument("--strict", action="store_true", help="exit 1 if any worktree is dirty or conflicted")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--submodules", action="store_true", help="count submodule gitlink drift as changes")
    args = ap.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    wts = worktrees()
    if not wts:
        print("ERROR: no worktrees found — is this a git repo?", file=sys.stderr)
        return 2

    rows = [classify(w, args.submodules) for w in wts]
    by_state: Dict[str, List[Dict]] = {}
    for r in rows:
        by_state.setdefault(r["state"], []).append(r)

    if args.json:
        print(json.dumps({"base": BASE_REF, "total": len(rows), "worktrees": rows}, indent=2))
        return 1 if (args.strict and (by_state.get("dirty") or by_state.get("conflicted"))) else 0

    order = ["conflicted", "dirty", "husk", "missing", "unknown", "clean"]
    print(f"Worktrees: {len(rows)}   base: {BASE_REF}")
    print("  " + ", ".join(f"{s}={len(by_state.get(s, []))}" for s in order if by_state.get(s)))

    for state in order:
        group = by_state.get(state)
        if not group or state == "clean":
            continue
        print(f"\n{state.upper()} ({len(group)}):")
        for r in sorted(group, key=lambda x: x["name"]):
            pos = ""
            if r["behind"] is not None:
                pos = f"  [behind {r['behind']}, ahead {r['ahead']}]"
            detail = []
            if r["changed"]:
                detail.append(f"{r['changed']} changed")
            if r["deleted"]:
                detail.append(f"{r['deleted']} deleted")
            if r["conflicted"]:
                detail.append(f"{r['conflicted']} conflicted")
            print(f"  {r['name']:<34} {r['branch'] or '(detached)':<44}{pos}")
            if detail:
                print(f"      {', '.join(detail)}")

    # Reported, never silently folded into the dirty count.
    drift = [r for r in rows if r["submodule_drift"]]
    if drift and not args.submodules:
        print(f"\nSubmodule gitlink drift (excluded from dirty; --submodules to include): {len(drift)} worktree(s)")

    stale = [r for r in rows if r["behind"] and r["behind"] > 50 and r["state"] == "clean"]
    if stale:
        print(f"\nClean but STALE (>50 behind {BASE_REF}) — reading files here returns old content:")
        for r in sorted(stale, key=lambda x: -x["behind"])[:10]:
            print(f"  {r['name']:<34} behind {r['behind']}")

    bad = len(by_state.get("dirty", [])) + len(by_state.get("conflicted", []))
    if args.strict:
        if bad:
            print(f"\nFAIL — {bad} worktree(s) dirty or conflicted.")
            return 1
        print("\nPASS — no dirty or conflicted worktrees.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
