#!/usr/bin/env python3
"""Submodule dirty-state auditor — finds signal in noise.

Designed for 4090-claude's cognitive strength: cross-repo pattern mining.
Scans all submodules, categorizes dirty state, suggests actions.

Categories:
  CLEANUP     — >50% deletions: archive/prune work, safe to commit
  NEW_WORK    — untracked files dominate: active development, needs review
  REFINEMENT  — modifications dominate: in-progress edits, check completion
  NESTED_STALE — dirty nested submodules: gitlink sync needed
  CLEAN       — no dirty state
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class SubmoduleState:
    name: str
    added: int = 0
    modified: int = 0
    deleted: int = 0
    untracked: int = 0
    nested_dirty: int = 0

    @property
    def total(self) -> int:
        return self.added + self.modified + self.deleted + self.untracked + self.nested_dirty

    @property
    def category(self) -> str:
        if self.total == 0:
            return "CLEAN"
        if self.nested_dirty > 0 and self.nested_dirty >= self.total // 2:
            return "NESTED_STALE"
        if self.deleted > self.total // 2:
            return "CLEANUP"
        if self.untracked > self.total // 2:
            return "NEW_WORK"
        return "REFINEMENT"


def scan_submodules() -> list[SubmoduleState]:
    """Scan all submodules and categorize their dirty state."""
    result = subprocess.run(
        ["git", "submodule", "foreach", "--quiet", "echo $sm_path"],
        capture_output=True, text=True, cwd=PROJECT_ROOT,
    )
    states: list[SubmoduleState] = []
    for sm_path in result.stdout.strip().splitlines():
        sm_path = sm_path.strip()
        if not sm_path:
            continue
        full_path = PROJECT_ROOT / sm_path
        if not full_path.is_dir():
            continue
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, cwd=full_path,
        )
        state = SubmoduleState(name=sm_path)
        for line in status.stdout.splitlines():
            if len(line) < 2:
                continue
            code = line[:2]
            if code.startswith("?"):
                state.untracked += 1
            elif "D" in code:
                state.deleted += 1
            elif "A" in code:
                state.added += 1
            elif "m" in code:
                state.nested_dirty += 1
            else:
                state.modified += 1
        if state.total > 0:
            states.append(state)
    return states


def main() -> int:
    states = scan_submodules()
    if not states:
        print("All submodules clean.")
        return 0

    print(f"{'Submodule':<45} {'Category':<15} {'D':>3} {'M':>3} {'A':>3} {'?':>3} {'m':>3}")
    print("-" * 80)
    for s in sorted(states, key=lambda x: x.total, reverse=True):
        print(f"{s.name:<45} {s.category:<15} {s.deleted:>3} {s.modified:>3} {s.added:>3} {s.untracked:>3} {s.nested_dirty:>3}")

    print(f"\n{len(states)} dirty submodule(s)")
    categories = {}
    for s in states:
        categories.setdefault(s.category, []).append(s.name)
    for cat, names in sorted(categories.items()):
        print(f"  {cat}: {len(names)} — {', '.join(n.split('/')[-1] for n in names[:5])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
