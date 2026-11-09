#!/usr/bin/env python3
"""Submodule freshness check: detect submodules whose tracked branch is
ahead of the parent gitlink.

The `pmoves/tools/submodule_integrity.py` check catches the LOCAL case
— a checked-out submodule that's drifted from its parent gitlink.
This tool catches the REMOTE case — a submodule's tracked branch on
the remote (e.g. `PMOVES.AI-Edition-Hardened`) that has commits the
parent repo hasn't picked up. When the remote is ahead, the operator
can run `git submodule update --remote` to consume the new commits
or open a PR to bump the gitlink.

Output: a JSON report on stdout (or a human-readable summary with
--no-json). The JSON shape is:

    {
      "checked_at": "<ISO-8601 UTC>",
      "summary": {
        "total": <int>,
        "in_sync": <int>,
        "remote_ahead": <int>,
        "remote_behind": <int>,
        "remote_missing": <int>,
        "local_uninitialized": <int>,
        "errors": <int>
      },
      "submodules": [
        {
          "path": "<submodule path>",
          "url": "<submodule url>",
          "branch": "<tracked branch>",
          "parent_gitlink": "<sha or null>",
          "remote_head": "<sha or null>",
          "status": "in_sync" | "remote_ahead" | "remote_behind" |
                    "remote_missing" | "local_uninitialized" | "error",
          "detail": "<human-readable note>"
        },
        ...
      ]
    }

This tool makes ONE `git ls-remote` call per submodule, in parallel by
default (configurable). It's safe to run in CI on a cron — no API
calls beyond what the local git daemon does, no auth tokens.

Refs: followups-v1 slice commit 8
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


REPO_ROOT = Path(__file__).resolve().parents[2]
GITMODULES = REPO_ROOT / ".gitmodules"


# ============================================================================
# Data shapes
# ============================================================================


@dataclass
class SubmoduleFreshness:
    path: str
    url: str
    branch: str
    parent_gitlink: Optional[str] = None
    remote_head: Optional[str] = None
    status: str = "pending"  # one of STATUSES
    detail: str = ""


# The authoritative status set. The summary buckets and the test that guards
# them BOTH derive from this tuple, so a new status cannot be added without a
# bucket. The previous arrangement -- a hand-written list in the summary and a
# hand-written list in the test -- could only ever confirm what the author
# already remembered, and it did not remember "unknown".
STATUSES: tuple[str, ...] = (
    "pending",
    "in_sync",
    "remote_ahead",
    "remote_behind",
    "remote_missing",
    "local_uninitialized",
    "unknown",
    "error",
)

# status -> summary key. Only `error` differs: consumers already read
# summary["errors"], so the key stays plural.
_SUMMARY_KEY = {"error": "errors"}


@dataclass
class FreshnessReport:
    checked_at: str
    summary: dict = field(default_factory=dict)
    submodules: list = field(default_factory=list)


# ============================================================================
# .gitmodules parsing
# ============================================================================


def parse_gitmodules() -> list[dict[str, str]]:
    """Return one record per submodule: {path, url, branch}.

    Branch is the .gitmodules `branch =` field; defaults to "main"
    when the field is absent (which is a common case for submodules
    that don't pin a branch).
    """
    if not GITMODULES.exists():
        return []
    records: list[dict[str, str]] = []
    current: dict[str, str] = {}
    section_re = re.compile(r"^\[submodule \"(.+)\"\]\s*$")
    kv_re = re.compile(r"^\s*(\w+)\s*=\s*(.+?)\s*$")
    for raw in GITMODULES.read_text(encoding="utf-8").splitlines():
        section = section_re.match(raw)
        if section:
            if current.get("path"):
                records.append(current)
            current = {"name": section.group(1), "branch": "main"}
            continue
        kv = kv_re.match(raw)
        if not kv or not current:
            continue
        key, value = kv.group(1), kv.group(2)
        if key in ("path", "url", "branch"):
            current[key] = value
    if current.get("path"):
        records.append(current)
    return records


# ============================================================================
# git helpers
# ============================================================================


def run_git(*args: str, cwd: Optional[Path] = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd or REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )


def parent_gitlink(submodule_path: str) -> Optional[str]:
    """Return the SHA the parent repo pins for this submodule, or None."""
    proc = run_git("ls-files", "--stage", submodule_path)
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    # Format: `<mode> <sha> <stage>\t<path>`
    line = proc.stdout.splitlines()[0]
    parts = line.split()
    if len(parts) < 3 or not parts[0].startswith("160000"):
        return None
    return parts[1]


def remote_head(url: str, branch: str) -> Optional[str]:
    """Return the SHA at `<url> refs/heads/<branch>` or None if missing."""
    proc = run_git("ls-remote", "--heads", url, f"refs/heads/{branch}")
    if proc.returncode != 0:
        return None
    for line in proc.stdout.splitlines():
        # Format: `<sha>\t<ref>`
        parts = line.split()
        if len(parts) < 2:
            continue
        if parts[1] == f"refs/heads/{branch}":
            return parts[0]
    return None


# ============================================================================
# Per-submodule check
# ============================================================================


def worktree_populated(path: str) -> bool:
    """True when the submodule's working tree is actually checked out.

    `git` marks a submodule initialized by placing a `.git` file (a gitdir
    pointer) or directory inside it. Testing that is exactly what `git
    submodule status` uses for its leading '-' marker.

    This is NOT the same question as "is the gitlink present". The gitlink lives
    in the parent's index and is there whether or not anyone ran `git submodule
    update --init`. 13 of 71 submodules on B850 had a perfectly good gitlink and
    an EMPTY directory, so the parent-gitlink test below classified them as
    healthy and the run exited 0.
    """
    return (REPO_ROOT / path / ".git").exists()


def check_one(record: dict[str, str]) -> SubmoduleFreshness:
    """Run the freshness check for a single submodule."""
    path = record["path"]
    url = record["url"]
    branch = record["branch"]

    parent = parent_gitlink(path)
    if not parent:
        return SubmoduleFreshness(
            path=path,
            url=url,
            branch=branch,
            status="local_uninitialized",
            detail="parent gitlink is missing from the index",
        )

    # A present gitlink says nothing about whether the tree was ever checked
    # out. Both conditions are reported as local_uninitialized -- the status
    # name is about the LOCAL tree -- but with distinct details, because the
    # fixes differ: a missing gitlink needs a commit, an empty tree needs
    # `git submodule update --init`.
    if not worktree_populated(path):
        return SubmoduleFreshness(
            path=path,
            url=url,
            branch=branch,
            parent_gitlink=parent,
            status="local_uninitialized",
            detail=(
                f"gitlink {parent[:9]} is recorded but the working tree at "
                f"{path} is not checked out; run "
                f"`git submodule update --init --depth 1 {path}`"
            ),
        )

    remote = remote_head(url, branch)
    if not remote:
        return SubmoduleFreshness(
            path=path,
            url=url,
            branch=branch,
            parent_gitlink=parent,
            status="remote_missing",
            detail=f"could not resolve {url} refs/heads/{branch} (branch deleted? private repo? offline?)",
        )

    if remote == parent:
        status = "in_sync"
        detail = "parent gitlink matches remote HEAD"
    else:
        # Ancestry must be computed INSIDE the submodule -- its commits live in
        # its own object store, not the parent's -- and the remote head has to be
        # present locally first, because `ls-remote` returns a SHA without
        # fetching the object it names.
        sub = REPO_ROOT / path
        if not _has_object(remote, sub):
            _try_fetch(url, branch, sub)

        if not (_has_object(remote, sub) and _has_object(parent, sub)):
            # Say so, rather than letting an unresolvable object masquerade as
            # divergence. "Could not measure" and "measured, and they diverged"
            # are different findings and must not share a status.
            status = "unknown"
            detail = (
                f"could not compare {parent[:9]} against {remote[:9]} in {path}: "
                f"objects unavailable locally (submodule uninitialized, or fetch "
                f"of {branch} failed)"
            )
        elif _is_ancestor(remote, parent, sub):
            status = "remote_behind"
            detail = "parent gitlink is ahead of remote HEAD (local-only commit on tracked branch)"
        elif _is_ancestor(parent, remote, sub):
            status = "remote_ahead"
            detail = (
                f"remote HEAD is ahead of parent gitlink by "
                f"{_count_commits_between(parent, remote, sub)} commit(s); "
                f"consider `git submodule update --remote {path}`"
            )
        else:
            status = "error"
            detail = (
                f"parent gitlink ({parent[:9]}) and remote HEAD ({remote[:9]}) "
                f"have diverged; manual reconciliation required"
            )

    return SubmoduleFreshness(
        path=path,
        url=url,
        branch=branch,
        parent_gitlink=parent,
        remote_head=remote,
        status=status,
        detail=detail,
    )


def _is_ancestor(maybe_ancestor: str, descendant: str, cwd: Path) -> bool:
    """True if `maybe_ancestor` is reachable from `descendant`, inside `cwd`.

    `cwd` is REQUIRED and is the submodule, never the parent. A submodule's
    commits live in its own object store; running this in the parent resolves
    neither SHA, both checks return non-zero, and every genuine update is then
    misreported as divergence -- silently turning the tool into one that only
    ever says "reconcile manually".
    """
    proc = run_git("merge-base", "--is-ancestor", maybe_ancestor, descendant, cwd=cwd)
    return proc.returncode == 0


def _has_object(sha: str, cwd: Path) -> bool:
    """Is `sha` present in `cwd`'s object store?

    `git ls-remote` returns a SHA WITHOUT fetching the object it names, so the
    remote head is normally absent locally. Ancestry against an absent object
    fails identically to genuine divergence -- so it must be checked, not assumed.
    """
    proc = run_git("cat-file", "-e", f"{sha}^{{commit}}", cwd=cwd)
    return proc.returncode == 0


def _try_fetch(url: str, branch: str, cwd: Path) -> None:
    """Best-effort: bring the remote branch's objects into `cwd`.

    Failure is not fatal -- the caller checks _has_object afterwards and reports
    an explicit "cannot determine" rather than guessing a relationship.
    """
    run_git("fetch", "--quiet", "--no-tags", url, branch, cwd=cwd)


def _count_commits_between(a: str, b: str, cwd: Path) -> int:
    """Roughly: how many commits in `b` not in `a`? Used for the ahead-count hint."""
    proc = run_git("rev-list", "--count", f"{a}..{b}", cwd=cwd)
    if proc.returncode != 0 or not proc.stdout.strip():
        return 0
    try:
        return int(proc.stdout.strip())
    except ValueError:
        return 0


# ============================================================================
# Orchestration
# ============================================================================


def run_check(records: list[dict[str, str]], parallel: bool = True) -> FreshnessReport:
    """Run the freshness check for every submodule in `records`."""
    if parallel:
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(check_one, records))
    else:
        results = [check_one(r) for r in records]

    # Every status in STATUSES gets a bucket, by construction rather than by
    # remembering. Two were missing when these were hand-listed:
    #   local_uninitialized -- 13 of 71 submodules were uninitialized on B850
    #     and appeared in NO bucket, so the counters silently summed to 58
    #     against total=71 and the run exited 0. PMOVES-MiniMax-MCP was one of
    #     them, which is why .claude/mcp.json registers MiniMax from PyPI
    #     instead of the submodule.
    #   unknown -- reachable whenever ls-remote succeeds but neither commit
    #     object can be fetched. .github/workflows/submodule-freshness.yml
    #     renders these under "Could not be measured", so dropping the bucket
    #     turned a transient fetch failure into an AssertionError that killed
    #     the report the workflow exists to publish.
    summary = {"total": len(results)}
    for _status in STATUSES:
        summary[_SUMMARY_KEY.get(_status, _status)] = sum(
            1 for r in results if r.status == _status
        )
    # The instrument checks itself: every result must land in exactly one
    # bucket. Without this, adding a new status silently shrinks the counters
    # against `total` -- which is precisely how local_uninitialized went
    # unnoticed. A mismatch is a defect in this tool, not in the repo.
    _bucketed = sum(
        v for k, v in summary.items() if k != "total"
    )
    if _bucketed != summary["total"]:
        unaccounted = sorted({r.status for r in results} - set(STATUSES))
        cause = (
            f"status(es) missing from STATUSES: {unaccounted}"
            if unaccounted
            else "every status is in STATUSES, so a result is double-counted"
        )
        raise AssertionError(
            f"freshness summary does not account for every submodule: "
            f"buckets={_bucketed} total={summary['total']}. {cause}."
        )

    return FreshnessReport(
        checked_at=datetime.now(timezone.utc).isoformat(),
        summary=summary,
        submodules=[asdict(r) for r in results],
    )


# ============================================================================
# Output
# ============================================================================


def render_human(report: FreshnessReport) -> str:
    """A human-friendly summary; the JSON is the canonical form."""
    lines: list[str] = []
    s = report.summary
    lines.append(f"Submodule freshness check at {report.checked_at}")
    lines.append(
        f"  total={s['total']}  in_sync={s['in_sync']}  "
        f"remote_ahead={s['remote_ahead']}  remote_behind={s['remote_behind']}  "
        f"remote_missing={s['remote_missing']}  "
        f"uninitialized={s['local_uninitialized']}  errors={s['errors']}"
    )
    # Highlight the ones that need action.
    for sub in report.submodules:
        if sub["status"] in ("in_sync", "remote_behind"):
            continue
        lines.append(f"  [{sub['status']:>20}] {sub['path']:50} {sub['detail']}")
    return "\n".join(lines)


# ============================================================================
# CLI
# ============================================================================


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--no-json",
        action="store_true",
        help="Print a human summary instead of the canonical JSON report.",
    )
    parser.add_argument(
        "--allow-uninitialized",
        action="store_true",
        help="Do not fail on uninitialized submodules (deliberate partial checkout).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero if any submodule is remote_ahead (consume before next release).",
    )
    parser.add_argument(
        "--path",
        action="append",
        default=[],
        help="Restrict the check to this submodule path (can be repeated).",
    )
    parser.add_argument(
        "--no-parallel",
        action="store_true",
        help="Run submodule checks serially (default: 8 workers).",
    )
    args = parser.parse_args(argv)

    records = parse_gitmodules()
    if not records:
        print("ERROR: no submodules found in .gitmodules", file=sys.stderr)
        return 2
    if args.path:
        wanted = set(args.path)
        records = [r for r in records if r["path"] in wanted]
        if not records:
            print(f"ERROR: no submodules match --path {sorted(wanted)}", file=sys.stderr)
            return 2

    report = run_check(records, parallel=not args.no_parallel)

    if args.no_json:
        print(render_human(report))
    else:
        print(json.dumps(asdict(report), indent=2, sort_keys=True))

    # An uninitialized submodule fails REGARDLESS of --strict. It is not a
    # freshness signal like remote_ahead (informational: the remote moved); it
    # means the working tree does not contain the code the gitlink points at.
    # CI checks out with `submodules: recursive`, so seeing it there means the
    # checkout genuinely failed. Locally it means work will route around a
    # missing tree -- which is how the botz-gateway shim and the PyPI MiniMax
    # registration came to exist.
    if report.summary["local_uninitialized"] > 0 and not args.allow_uninitialized:
        # report.submodules holds asdict() output, not SubmoduleFreshness
        # objects -- attribute access here raises AttributeError and takes out
        # the branch whose whole job is to print the fix.
        paths = [
            r["path"] for r in report.submodules
            if r["status"] == "local_uninitialized"
        ]
        print(
            f"FAIL: {len(paths)} submodule(s) are uninitialized: "
            + ", ".join(sorted(paths)[:10])
            + ("" if len(paths) <= 10 else f" (+{len(paths) - 10} more)")
            + "\n      Fix: git submodule update --init --depth 1 <path>"
            + "\n      Override with --allow-uninitialized only when a partial "
              "checkout is deliberate.",
            file=sys.stderr,
        )
        return 1
    if args.strict and report.summary["remote_ahead"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
