#!/usr/bin/env python3
"""github_pool_sync -- normalize GitHub's THREE review surfaces into one pool.

WHY THIS TOOL EXISTS (the founding defect, measured on PR #3025, 2026-09-12):
GitHub splits PR conversation across THREE REST endpoints --

  /pulls/{n}/reviews          review objects (state: APPROVED/CHANGES_REQUESTED/...)
  /pulls/{n}/comments         inline review comments (attached to diffs)
  /issues/{n}/comments        issue-style comments

-- and the fleet's own automated reviewers (the kilocode fleet-review lane)
post their findings as ISSUE COMMENTS through github-actions[bot]. An agent
that greps the review endpoints gets a confident zero while a REQUEST_CHANGES
sits in plain sight; the operator's email sees it, the agents do not. That
exact miss happened twice in one day.

This tool reads all three surfaces per open PR, normalizes them into ONE
record shape, and publishes the summary to NATS `github.pool.review.v1`
(JetStream stream GITHUB_POOL, `limits` retention) where any agent on the bus
can subscribe -- no GraphQL, no per-agent API quota, one sweep per cron tick.

Exit codes follow the repo doctrine:
  0  swept and published (findings or not)
  1  findings that need human eyes NOW (e.g. a PR whose ONLY review signal
     is a CHANGES_REQUESTED nobody replied to)
  3  could not measure (no gh, no nats CLI, no broker, API failure)

Usage:
  python3 pmoves/tools/github_pool_sync.py [--repo OWNER/REPO] [--pr N ...]
       [--dry-run] [--json]
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from typing import Any

DEFAULT_REPO = "POWERFULMOVES/PMOVES.AI"
SUBJECT = "github.pool.review.v1"
NATS_URL = os.environ.get("GITHUB_POOL_NATS_URL",
                          "nats://nats:pmoves@127.0.0.1:4222")
FLEET_REVIEW_MARKERS = ("## Fleet review", "fleet review:")

EXIT_OK, EXIT_FINDINGS, EXIT_UNMEASURED = 0, 1, 3


def _gh(path: str) -> list[dict[str, Any]]:
    """One REST call via gh (gh handles auth + REST quota, not GraphQL)."""
    r = subprocess.run(["gh", "api", "--paginate", path],
                       capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise RuntimeError(f"gh api {path} failed: {r.stderr.strip()[:200]}")
    data = json.loads(r.stdout or "[]")
    return data if isinstance(data, list) else []


def normalize_surfaces(pr: dict[str, Any], reviews: list, inline: list,
                       issue_comments: list) -> dict[str, Any]:
    """Three GitHub surfaces -> one pool record. Pure, so tests pin it.

    The load-bearing rule: a bot login is NOT evidence a comment is noise.
    The fleet's own reviewers post through github-actions[bot]; we tag those
    rows `fleet_review` (body marker) so triage reads them FIRST -- they
    carry APPROVE/REQUEST_CHANGES verdicts the review endpoints never see.
    """
    number = pr["number"]
    out_reviews = []
    for rv in reviews:
        out_reviews.append({
            "kind": "review", "actor": rv["user"]["login"],
            "state": rv.get("state", ""), "at": rv.get("submitted_at", ""),
            "url": rv.get("html_url", ""),
        })
    out_inline = []
    for c in inline:
        out_inline.append({
            "kind": "inline", "actor": c["user"]["login"],
            "path": c.get("path", ""), "line": c.get("line"),
            "at": c.get("created_at", ""), "url": c.get("html_url", ""),
        })
    out_comments = []
    for c in issue_comments:
        body = c.get("body", "") or ""
        fleet = any(m.lower() in body.lower()[:200]
                    for m in FLEET_REVIEW_MARKERS)
        verdict = ""
        low = body.lower()
        if fleet:
            if "request_changes" in low or "changes requested" in low:
                verdict = "REQUEST_CHANGES"
            elif "approve" in low:
                verdict = "APPROVE"
        out_comments.append({
            "kind": "issue-comment", "actor": c["user"]["login"],
            "at": c.get("created_at", ""), "url": c.get("html_url", ""),
            "fleet_review": fleet, "fleet_verdict": verdict,
        })
    changes_requested = (
        any(rv["state"] == "CHANGES_REQUESTED" for rv in out_reviews)
        or any(c["fleet_verdict"] == "REQUEST_CHANGES" for c in out_comments)
    )
    approved = (
        any(rv["state"] == "APPROVED" for rv in out_reviews)
        or any(c["fleet_verdict"] == "APPROVE" for c in out_comments)
    )
    return {
        "pr": number, "title": (pr.get("title") or "")[:100],
        "author": (pr.get("user") or {}).get("login", ""),
        "mergeable": pr.get("mergeable"),
        "surfaces": {"reviews": len(reviews), "inline": len(inline),
                     "issue_comments": len(issue_comments)},
        "signals": {"changes_requested": changes_requested, "approved": approved,
                    "fleet_reviews": sum(1 for c in out_comments
                                         if c["fleet_review"])},
        "detail": {"reviews": out_reviews, "inline": out_inline,
                   "issue_comments": out_comments},
        "swept_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def triage(record: dict[str, Any]) -> str:
    """One-line triage verdict per PR, cheapest signal first."""
    s, sig = record["surfaces"], record["signals"]
    if sig["changes_requested"]:
        return f"PR#{record['pr']}: CHANGES_REQUESTED stands " \
               f"({s['reviews']}r/{s['inline']}i/{s['issue_comments']}c, " \
               f"{sig['fleet_reviews']} fleet)"
    if s["reviews"] == 0 and s["inline"] == 0 and s["issue_comments"] == 0:
        return f"PR#{record['pr']}: NO SIGNAL AT ALL (never reviewed)"
    return f"PR#{record['pr']}: ok-ish ({s['reviews']}r/{s['inline']}i/" \
           f"{s['issue_comments']}c, changes={sig['changes_requested']})"


def publish(record: dict[str, Any]) -> None:
    nats = shutil.which("nats")
    if not nats:
        raise RuntimeError("nats CLI not found on PATH (install per "
                           "fix/nats-cli-and-leaf-settle lane)")
    payload = json.dumps(record, separators=(",", ":"))
    r = subprocess.run(
        [nats, "-s", NATS_URL, "pub", SUBJECT, payload],
        capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        raise RuntimeError(f"nats pub failed: {r.stderr.strip()[:200]}")


def ensure_stream() -> None:
    """GITHUB_POOL over github.pool.> with LIMITS retention -- idempotent.

    `limits`, never `interest`: interest-based streams silently drop
    messages with no consumers, which for a triage pool is the
    empty-is-not-evidence trap built into infrastructure.
    """
    nats = shutil.which("nats")
    if not nats:
        return  # reported by caller's could-not-measure path
    r = subprocess.run([nats, "-s", NATS_URL, "stream", "info", "GITHUB_POOL"],
                       capture_output=True, text=True, timeout=15)
    if r.returncode == 0:
        return
    r = subprocess.run(
        [nats, "-s", NATS_URL, "stream", "add", "GITHUB_POOL",
         "--subjects", "github.pool.>", "--storage", "file",
         "--retention", "limits", "--max-age", "72h",
         "--max-msgs", "20000", "--discard", "old", "--defaults"],
        capture_output=True, text=True, timeout=30)
    # CHECKED, not assumed: without --defaults the CLI wants a terminal
    # confirmation and fails in cron/service contexts; without this check
    # the tool published into the void and reported success.
    if r.returncode != 0:
        raise RuntimeError(f"stream add GITHUB_POOL failed: "
                           f"{r.stderr.strip()[:200]}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--repo", default=DEFAULT_REPO)
    p.add_argument("--pr", action="append", type=int, default=[],
                   help="sweep only these PR numbers (default: all open)")
    p.add_argument("--dry-run", action="store_true",
                   help="sweep + print, publish nothing")
    p.add_argument("--json", action="store_true", help="print records")
    args = p.parse_args(argv)

    if shutil.which("gh") is None:
        print("github-pool: NOT MEASURED - gh CLI not on PATH", file=sys.stderr)
        return EXIT_UNMEASURED
    try:
        if args.pr:
            prs = []
            for n in args.pr:
                pr = json.loads(subprocess.run(
                    ["gh", "api", f"repos/{args.repo}/pulls/{n}"],
                    capture_output=True, text=True, timeout=60).stdout)
                prs.append(pr)
        else:
            prs = _gh(f"repos/{args.repo}/pulls?state=open&per_page=100")
    except Exception as exc:  # noqa: BLE001 -- report, never guess
        print(f"github-pool: NOT MEASURED - {exc}", file=sys.stderr)
        return EXIT_UNMEASURED

    records, urgent = [], 0
    for pr in prs:
        n = pr["number"]
        try:
            rec = normalize_surfaces(
                pr,
                _gh(f"repos/{args.repo}/pulls/{n}/reviews"),
                _gh(f"repos/{args.repo}/pulls/{n}/comments"),
                _gh(f"repos/{args.repo}/issues/{n}/comments"),
            )
        except Exception as exc:  # noqa: BLE001
            print(f"github-pool: NOT MEASURED on PR#{n} - {exc}",
                  file=sys.stderr)
            return EXIT_UNMEASURED
        records.append(rec)
        line = triage(rec)
        print(line)
        if "CHANGES_REQUESTED stands" in line or "NO SIGNAL AT ALL" in line:
            urgent += 1

    if args.json:
        print(json.dumps(records, indent=2))

    if not args.dry_run:
        try:
            ensure_stream()
            for rec in records:
                publish(rec)
            print(f"github-pool: published {len(records)} record(s) to "
                  f"{SUBJECT}", file=sys.stderr)
        except Exception as exc:  # noqa: BLE001
            print(f"github-pool: NOT MEASURED - publish failed: {exc}",
                  file=sys.stderr)
            return EXIT_UNMEASURED

    if urgent:
        print(f"github-pool: {urgent} PR(s) need eyes now", file=sys.stderr)
        return EXIT_FINDINGS
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
