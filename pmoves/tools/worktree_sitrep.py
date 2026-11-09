#!/usr/bin/env python3
"""Worktree sitrep — what is actually dirty across every registered worktree.

WHY THIS EXISTS
---------------
`.claude/CLAUDE.md` and `.claude/PATTERNS.md` have documented
`make -C pmoves worktree-sitrep` / `-strict` as the *authoritative* worktree
check, telling readers to prefer it to per-worktree spot checks. Neither target
existed. Both sat in the command-anchor baseline as GHOST_TARGETs, so following
the documented road produced:

    make: *** No rule to make target 'worktree-sitrep-strict'.  Stop.

and the reader hand-rolled `git status` across ~130 worktrees instead.

WHAT A HAND-ROLLED SWEEP GETS WRONG
-----------------------------------
  1. SUBMODULE NOISE. Plain status reports ` M PMOVES-Archon` for every
     submodule whose checkout differs from the recorded gitlink. With ~50
     submodules that buries real work. Submodule entries are identified by
     PATH (from .gitmodules), reported separately, and never silently dropped.

  2. HUSKS. Several worktrees report thousands of entries where every one is a
     WORKTREE-SIDE deletion: the directory was emptied on disk (the OneDrive
     lock cleanup does this) while git still tracks the files. That is one dead
     registration, not thousands of edits.

  3. STALE BASE. A worktree can be clean and still useless — the repo root sat
     200+ commits behind main, and reading files from it produced three wrong
     conclusions in one session. Distance from base is reported for every
     worktree.

FAILING SAFE, NOT QUIET
-----------------------
An earlier revision of this tool collapsed every git failure into "" and fell
through to `clean`, so an unreadable or timed-out worktree PASSED the strict
gate. That is the same defect this whole lane is about: a check that reports
success while measuring nothing. `_git()` now returns None on failure, distinct
from "" (a real empty result), and a worktree whose status cannot be read is
`unknown` — which FAILS strict mode. A gate that cannot see is not a gate that
passed.

HUSK vs REAL DELETIONS
----------------------
`git rm old.py` stages a deletion: `D ` (index column). An emptied directory
leaves the index alone and shows ` D` (worktree column). Only the second is a
husk. Treating both as husks let staged deletions pass the strict gate.

UNTRACKED FILES
---------------
Counted and reported, never silently skipped — but they do NOT fail strict mode
on their own. Build output and scratch files land untracked constantly, and a
gate that fires on them gets muted. `--untracked-strict` includes them.

Usage:
    python pmoves/tools/worktree_sitrep.py            # snapshot
    python pmoves/tools/worktree_sitrep.py --strict   # gate
    python pmoves/tools/worktree_sitrep.py --json     # machine-readable
    python pmoves/tools/worktree_sitrep.py --submodules        # count gitlink drift as dirty
    python pmoves/tools/worktree_sitrep.py --untracked-strict  # untracked also fails

Exit codes:
    0 = nothing dirty/conflicted/unknown (or snapshot mode)
    1 = at least one dirty, conflicted, or unreadable worktree (--strict only)
    2 = error
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BASE_REF = "origin/main"
GIT_TIMEOUT = 60


def _git(args: List[str], cwd: Optional[Path] = None, timeout: int = GIT_TIMEOUT) -> Optional[str]:
    """Run git. Returns stdout on success, or None on ANY failure.

    None is deliberately distinct from "": an empty string is a real result
    (a clean `git status`), while None means we could not measure. Callers must
    not conflate them — doing so is what let unreadable worktrees report clean.
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
        return None
    return r.stdout if r.returncode == 0 else None


def submodule_paths() -> Set[str]:
    """Registered submodule paths, read once. Used to separate gitlink drift
    from real work by PATH rather than by subtracting two status calls — the
    subtraction miscounted untracked files as submodule drift."""
    out = _git(["config", "-f", ".gitmodules", "--get-regexp", r"submodule\..*\.path"], cwd=REPO_ROOT)
    if not out:
        return set()
    return {line.split(None, 1)[1].strip() for line in out.splitlines() if " " in line}


def worktrees() -> List[Path]:
    out = _git(["worktree", "list", "--porcelain"], cwd=REPO_ROOT)
    if out is None:
        return []
    return [Path(l[len("worktree "):].strip()) for l in out.splitlines() if l.startswith("worktree ")]


def classify(wt: Path, submodules: Set[str]) -> Dict:
    info: Dict = {
        "path": wt.as_posix(), "name": wt.name, "branch": "", "state": "unknown",
        "staged": 0, "modified": 0, "worktree_deleted": 0, "untracked": 0,
        "conflicted": 0, "submodule_drift": 0, "behind": None, "ahead": None,
        "note": "",
    }

    if not wt.is_dir():
        info["state"] = "missing"
        return info

    branch = _git(["branch", "--show-current"], cwd=wt)
    info["branch"] = (branch or "").strip()

    # ONE status call. The previous revision ran a second one without
    # --ignore-submodules purely to derive a drift count, doubling the most
    # expensive operation across 127 worktrees. Submodules are identified by
    # path instead.
    status = _git(["status", "--porcelain=v1", "--untracked-files=normal"], cwd=wt)
    if status is None:
        info["note"] = "git status failed or timed out — NOT verified clean"
        return info  # stays "unknown"

    for line in status.splitlines():
        if len(line) < 3:
            continue
        x, y, path = line[0], line[1], line[3:].strip().strip('"')
        if x == "?" and y == "?":
            info["untracked"] += 1
            continue
        if path in submodules:
            info["submodule_drift"] += 1
            continue
        if "U" in (x, y) or (x, y) in (("A", "A"), ("D", "D")):
            info["conflicted"] += 1
        elif y == "D" and x == " ":
            info["worktree_deleted"] += 1      # gone from disk, index untouched
        elif x != " ":
            info["staged"] += 1                # includes staged deletions (D )
        else:
            info["modified"] += 1

    counts = _git(["rev-list", "--left-right", "--count", f"{BASE_REF}...HEAD"], cwd=wt)
    parts = (counts or "").split()
    if len(parts) == 2:
        info["behind"], info["ahead"] = int(parts[0]), int(parts[1])

    real = info["staged"] + info["modified"]
    if info["conflicted"]:
        info["state"] = "conflicted"
    elif info["worktree_deleted"] and not real:
        # Every tracked entry gone from disk with the index untouched: an
        # emptied directory, not work. A staged `git rm` lands in `staged`.
        info["state"] = "husk"
    elif real or info["worktree_deleted"]:
        info["state"] = "dirty"
    elif info["untracked"]:
        info["state"] = "untracked-only"
    else:
        info["state"] = "clean"
    return info


def main() -> int:
    ap = argparse.ArgumentParser(description="Worktree sitrep across all registered worktrees.")
    ap.add_argument("--strict", action="store_true", help="exit 1 on dirty, conflicted or unreadable worktrees")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--submodules", action="store_true", help="count submodule gitlink drift as dirty")
    ap.add_argument("--untracked-strict", action="store_true", help="untracked-only worktrees also fail --strict")
    args = ap.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    wts = worktrees()
    if not wts:
        print("ERROR: no worktrees found — is this a git repo?", file=sys.stderr)
        return 2

    subs = submodule_paths()
    rows = [classify(w, subs) for w in wts]
    if args.submodules:
        for r in rows:
            if r["state"] == "clean" and r["submodule_drift"]:
                r["state"] = "dirty"

    by_state: Dict[str, List[Dict]] = {}
    for r in rows:
        by_state.setdefault(r["state"], []).append(r)

    failing = (
        by_state.get("dirty", []) + by_state.get("conflicted", [])
        + by_state.get("unknown", []) + by_state.get("missing", [])
        + (by_state.get("untracked-only", []) if args.untracked_strict else [])
    )

    if args.json:
        print(json.dumps({"base": BASE_REF, "total": len(rows), "worktrees": rows}, indent=2))
        return 1 if (args.strict and failing) else 0

    order = ["conflicted", "unknown", "missing", "dirty", "husk", "untracked-only", "clean"]
    print(f"Worktrees: {len(rows)}   base: {BASE_REF}")
    print("  " + ", ".join(f"{s}={len(by_state.get(s, []))}" for s in order if by_state.get(s)))

    for state in order:
        group = by_state.get(state)
        if not group or state == "clean":
            continue
        print(f"\n{state.upper()} ({len(group)}):")
        for r in sorted(group, key=lambda x: x["name"]):
            pos = f"  [behind {r['behind']}, ahead {r['ahead']}]" if r["behind"] is not None else ""
            print(f"  {r['name']:<34} {r['branch'] or '(detached)':<44}{pos}")
            bits = [f"{r[k]} {label}" for k, label in (
                ("staged", "staged"), ("modified", "modified"),
                ("worktree_deleted", "deleted-on-disk"), ("conflicted", "conflicted"),
                ("untracked", "untracked"), ("submodule_drift", "submodule-drift"),
            ) if r[k]]
            if bits:
                print(f"      {', '.join(bits)}")
            if r["note"]:
                print(f"      {r['note']}")

    stale = [r for r in rows if r["behind"] and r["behind"] > 50 and r["state"] == "clean"]
    if stale:
        print(f"\nClean but STALE (>50 behind {BASE_REF}) — reading files here returns old content:")
        for r in sorted(stale, key=lambda x: -x["behind"])[:10]:
            print(f"  {r['name']:<34} behind {r['behind']}")

    if args.strict:
        if failing:
            print(f"\nFAIL — {len(failing)} worktree(s) dirty, conflicted or unreadable.")
            return 1
        print("\nPASS — no dirty, conflicted or unreadable worktrees.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
