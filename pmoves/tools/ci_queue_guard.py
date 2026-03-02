#!/usr/bin/env python3
"""Guard GitHub Actions queue health for self-hosted runner deadlocks.

Use this to clear stale queued runs so active PR lanes can proceed.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

PR_EVENTS = {"pull_request", "pull_request_target"}


@dataclass
class RunItem:
    run_id: int
    workflow: str
    event: str
    head_branch: str
    title: str
    url: str
    created_at: str
    action: str
    reason: str


def _run_json(cmd: list[str]) -> Any:
    proc = subprocess.run(cmd, text=True, capture_output=True, check=False, encoding="utf-8")
    if proc.returncode != 0:
        raise RuntimeError(f"command failed ({proc.returncode}): {' '.join(cmd)}\n{proc.stderr.strip()}")
    payload = proc.stdout.strip()
    return json.loads(payload) if payload else None


def _resolve_repo(explicit_repo: str) -> str:
    if explicit_repo.strip():
        return explicit_repo.strip()
    data = _run_json(["gh", "repo", "view", "--json", "nameWithOwner"])
    if isinstance(data, dict):
        value = data.get("nameWithOwner")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "POWERFULMOVES/PMOVES.AI"


def _open_heads(repo: str) -> set[str]:
    data = _run_json(["gh", "pr", "list", "--repo", repo, "--state", "open", "--limit", "200", "--json", "headRefName"])
    heads: set[str] = set()
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                branch = item.get("headRefName")
                if isinstance(branch, str) and branch:
                    heads.add(branch)
    return heads


def _queued(repo: str, limit: int) -> list[dict[str, Any]]:
    data = _run_json(
        [
            "gh",
            "run",
            "list",
            "--repo",
            repo,
            "--status",
            "queued",
            "--limit",
            str(limit),
            "--json",
            "databaseId,event,headBranch,workflowName,displayTitle,url,createdAt",
        ]
    )
    return data if isinstance(data, list) else []


def _classify(runs: list[dict[str, Any]], open_heads: set[str], workflows: set[str]) -> list[RunItem]:
    items: list[RunItem] = []
    for run in runs:
        if not isinstance(run, dict):
            continue
        workflow = str(run.get("workflowName") or "")
        if workflows and workflow not in workflows:
            continue

        event = str(run.get("event") or "")
        branch = str(run.get("headBranch") or "")
        run_id = int(run.get("databaseId") or 0)
        title = str(run.get("displayTitle") or "")
        url = str(run.get("url") or "")
        created_at = str(run.get("createdAt") or "")

        action = "cancel"
        reason = "non_pr_event"
        if event in PR_EVENTS:
            if branch in open_heads:
                action = "keep"
                reason = "open_pr_branch"
            else:
                reason = "pr_branch_not_open"

        items.append(
            RunItem(
                run_id=run_id,
                workflow=workflow,
                event=event,
                head_branch=branch,
                title=title,
                url=url,
                created_at=created_at,
                action=action,
                reason=reason,
            )
        )
    return items


def _cancel(repo: str, run_id: int) -> tuple[bool, str]:
    proc = subprocess.run(
        ["gh", "run", "cancel", str(run_id), "--repo", repo],
        text=True,
        capture_output=True,
        check=False,
        encoding="utf-8",
    )
    if proc.returncode == 0:
        return True, ""
    return False, (proc.stderr or proc.stdout or "").strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default="", help="owner/repo (default: auto-detect)")
    parser.add_argument("--limit", type=int, default=200, help="max queued runs to inspect")
    parser.add_argument("--threshold", type=int, default=9, help="minimum queued count to trigger cancellation")
    parser.add_argument("--workflow", action="append", default=[], help="filter by workflow name (repeatable)")
    parser.add_argument("--apply", action="store_true", help="execute cancellation")
    parser.add_argument("--force", action="store_true", help="ignore threshold guard")
    parser.add_argument("--json-out", type=Path, default=None, help="write JSON summary")
    args = parser.parse_args()

    repo = _resolve_repo(args.repo)
    workflows = {w.strip() for w in args.workflow if w.strip()}
    open_heads = _open_heads(repo)
    runs = _queued(repo, args.limit)
    items = _classify(runs, open_heads, workflows)

    cancel_items = [item for item in items if item.action == "cancel"]
    keep_items = [item for item in items if item.action == "keep"]

    print(f"Repo: {repo}")
    print(f"Queued runs considered: {len(items)} (raw={len(runs)})")
    print(f"Open PR branches: {len(open_heads)}")
    print(f"Keep: {len(keep_items)}  Cancel candidates: {len(cancel_items)}")
    if workflows:
        print(f"Workflow filter: {', '.join(sorted(workflows))}")

    should_apply = args.apply and (args.force or len(items) >= args.threshold)
    if args.apply and not should_apply:
        print(
            f"Threshold guard: queued={len(items)} < threshold={args.threshold}; "
            "no cancellations applied (use --force to override)."
        )

    cancelled = 0
    failures: list[dict[str, Any]] = []
    if should_apply:
        for item in cancel_items:
            ok, err = _cancel(repo, item.run_id)
            if ok:
                cancelled += 1
            else:
                failures.append({"run_id": item.run_id, "error": err})

    for item in cancel_items:
        prefix = "CANCEL" if should_apply else "WOULD_CANCEL"
        print(f"{prefix} {item.run_id} {item.workflow} {item.event} {item.head_branch} ({item.reason})")
    for item in keep_items:
        print(f"KEEP {item.run_id} {item.workflow} {item.event} {item.head_branch}")

    payload = {
        "repo": repo,
        "threshold": args.threshold,
        "apply_requested": args.apply,
        "applied": should_apply,
        "queued_considered": len(items),
        "queued_raw": len(runs),
        "open_pr_branches": sorted(open_heads),
        "workflows_filter": sorted(workflows),
        "cancel_candidates": len(cancel_items),
        "kept": len(keep_items),
        "cancelled": cancelled,
        "failures": failures,
        "items": [asdict(item) for item in items],
    }
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"Wrote: {args.json_out}")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
