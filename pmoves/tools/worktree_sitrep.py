#!/usr/bin/env python3
"""Generate a two-sided worktree + submodule audit SITREP."""

from __future__ import annotations

import argparse
import configparser
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
GITMODULES = REPO_ROOT / ".gitmodules"


@dataclass
class WorktreeInfo:
    path: str
    head: str
    branch: str
    detached: bool
    dirty_count: int
    status_lines: list[str]


def run_git(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd or REPO_ROOT),
        text=True,
        capture_output=True,
        check=False,
    )


def parse_worktrees() -> list[dict[str, str]]:
    proc = run_git(["worktree", "list", "--porcelain"])
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "git worktree list failed")
    rows: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for raw in proc.stdout.splitlines():
        line = raw.strip()
        if not line:
            if current:
                rows.append(current)
            current = None
            continue
        key, _, value = line.partition(" ")
        if key == "worktree":
            if current:
                rows.append(current)
            current = {"path": value}
            continue
        if current is None:
            continue
        current[key] = value
    if current:
        rows.append(current)
    return rows


def collect_worktree_status(entry: dict[str, str], max_lines: int) -> WorktreeInfo:
    path = entry.get("path", "")
    proc = run_git(["status", "--short"], cwd=Path(path))
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    return WorktreeInfo(
        path=path,
        head=entry.get("HEAD", ""),
        branch=entry.get("branch", ""),
        detached="detached" in entry,
        dirty_count=len(lines),
        status_lines=lines[:max_lines],
    )


def count_gitmodules() -> int:
    cfg = configparser.ConfigParser()
    cfg.read(GITMODULES, encoding="utf-8")
    return len(cfg.sections())


def parse_submodule_prefix_counts(status_stdout: str) -> dict[str, int]:
    counts = {"-": 0, "+": 0, "U": 0, "clean": 0}
    for raw in status_stdout.splitlines():
        line = raw.rstrip()
        if not line:
            continue
        prefix = line[0]
        if prefix in {"-", "+"}:
            counts[prefix] += 1
        elif prefix.upper() == "U":
            counts["U"] += 1
        else:
            counts["clean"] += 1
    return counts


def render_worktree_block(info: WorktreeInfo) -> str:
    branch = info.branch.removeprefix("refs/heads/")
    mode = "detached" if info.detached else branch or "unknown"
    header = f"- `{info.path}` [{mode}] dirty={info.dirty_count}"
    if not info.status_lines:
        return header
    lines = "\n".join(f"  - `{line}`" for line in info.status_lines)
    return f"{header}\n{lines}"


def build_report(
    worktrees: list[WorktreeInfo],
    gitmodules_count: int,
    submodule_counts: dict[str, int],
    recursive_exit: int,
    recursive_error: str,
) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    dirty_total = sum(1 for wt in worktrees if wt.dirty_count > 0)
    blocks = "\n".join(render_worktree_block(wt) for wt in worktrees) or "- _none_"
    recursive_error = recursive_error.strip() or "_none_"
    return f"""# Worktree + Submodule Audit SITREP
_Generated: {now}_

## Summary
- Worktrees discovered: **{len(worktrees)}**
- Dirty worktrees: **{dirty_total}**
- `.gitmodules` entries: **{gitmodules_count}**
- Submodule clean rows: **{submodule_counts['clean']}**
- Submodule uninitialized (`-`): **{submodule_counts['-']}**
- Submodule drifted (`+`): **{submodule_counts['+']}**
- Submodule conflicts (`U`): **{submodule_counts['U']}**
- Recursive submodule status exit: **{recursive_exit}**

## Worktree Status
{blocks}

## Recursive Submodule Error
`{recursive_error}`

## Operator Guidance
1. Run this report before cleanup: `make -C pmoves worktree-sitrep`.
2. If recursive exit is non-zero, fix nested `.gitmodules` mapping before pointer cleanup.
3. Clean only one wave at a time:
   - Wave A: root worktree + active feature worktree.
   - Wave B: main-audit/reference worktrees.
   - Wave C: detached/archive worktrees.
"""


def main() -> int:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        default=str(REPO_ROOT / f"pmoves/docs/AGENTS/WORKTREE_SUBMODULE_AUDIT_SITREP_{today}.md"),
        help="Output markdown report path.",
    )
    parser.add_argument(
        "--max-status-lines",
        type=int,
        default=20,
        help="Max status lines captured per worktree.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return non-zero when any worktree is dirty or recursive submodule check fails.",
    )
    args = parser.parse_args()

    worktree_entries = parse_worktrees()
    worktrees = [collect_worktree_status(entry, args.max_status_lines) for entry in worktree_entries]

    status_proc = run_git(["submodule", "status"])
    if status_proc.returncode != 0:
        raise SystemExit(status_proc.stderr.strip() or "git submodule status failed")
    submodule_counts = parse_submodule_prefix_counts(status_proc.stdout)

    recursive_proc = run_git(["submodule", "status", "--recursive"])
    recursive_error = recursive_proc.stderr.strip() or recursive_proc.stdout.strip()

    report = build_report(
        worktrees=worktrees,
        gitmodules_count=count_gitmodules(),
        submodule_counts=submodule_counts,
        recursive_exit=recursive_proc.returncode,
        recursive_error=recursive_error,
    )

    out = Path(args.output).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report, encoding="utf-8")
    print(out)

    if args.strict:
        dirty = any(wt.dirty_count > 0 for wt in worktrees)
        if dirty or recursive_proc.returncode != 0:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
