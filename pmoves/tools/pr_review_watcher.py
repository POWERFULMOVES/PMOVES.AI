"""
pr_review_watcher.py — Listen for GitHub review events on PMOVES.AI PRs.

A-mode "no polling" reviewer notification tool. Works without a public
webhook URL — the assumption is that GitHub already sends notifications;
we just need to listen for them. Uses HTTP conditional GET (ETag) so
the cost of "listening" is minimal: GitHub returns 304 instantly when
nothing has changed, 200 only when a new notification appears.

Modes (in order of preference):

  1. notifications (default) — uses `gh api /notifications` with ETag.
     Tracks the last-modified state. When a new notification for one of
     our watched PRs arrives, emits an event. This is the "GitHub sends
     notifications, why not listen for those" mode.

  2. pr-watch — uses `gh pr view <N> --json` in a polling loop. Per-PR.
     Use when you want to watch a specific PR and care about review
     state changes (not just notifications).

  3. nats — subscribes to `github.webhook.review.submitted.v1` (and
     related subjects) from the n8n webhook bridge. Only works when
     the webhook infra is up. This is the B-mode "fully event-driven"
     mode; the same tool, same CLI, just a different transport.

Emits events to:
  - stdout (one line per event, JSON or human-readable)
  - --log <path>  (JSONL append)
  - --emit-nats   (publish to chit.pr.review.detected.v1)

Exits:
  0  — event detected (review arrived within --max-runtime)
  1  — timeout (no event within --max-runtime)
  2  — error (gh not authed, repo not detected, etc.)
  130 — SIGINT (Ctrl-C)

Usage examples:
  # Listen for ANY new notification on this repo (the "just listen" mode)
  python -m pmoves.tools.pr_review_watcher --mode notifications

  # Listen for review events on PR #2132 (A2UI v0.1 + Fordham)
  python -m pmoves.tools.pr_review_watcher --pr 2132 --max-runtime 2h --log pmoves/docs/logs/pr_review_arrivals.jsonl

  # Listen on all 3 PRs at once
  python -m pmoves.tools.pr_review_watcher --prs 2132,2133,2134 --max-runtime 8h

  # Daemon mode — run in the background, log to JSONL, emit to NATS
  nohup python -m pmoves.tools.pr_review_watcher \\
      --prs 2132,2133,2134 \\
      --max-runtime 24h \\
      --log pmoves/docs/logs/pr_review_arrivals.jsonl \\
      --emit-nats \\
      > pmoves/docs/logs/pr_review_watcher.out 2>&1 &

  # B-mode: subscribe to the n8n webhook bridge
  python -m pmoves.tools.pr_review_watcher --mode nats --max-runtime 24h

CHIT trail: signed advisory on first emit (no CHIT_PASSPHRASE loaded).
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# --- Constants ----------------------------------------------------------------

GITHUB_API = "https://api.github.com"
DEFAULT_NATS_SUBJECT = "chit.pr.review.detected.v1"
NATS_REVIEW_SUBJECTS = [
    "github.webhook.review.submitted.v1",
    "github.webhook.review.thread_comment.v1",
    "github.webhook.review.issue_comment.v1",
    "chit.pr.review.detected.v1",
]
LOG_DIR = Path("pmoves/docs/logs")


# --- Helpers ------------------------------------------------------------------

def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run(cmd: list[str], timeout: int = 30) -> tuple[int, str, str]:
    """Run a subprocess, return (returncode, stdout, stderr).

    Uses bytes mode + manual decode to avoid Windows subprocess issues
    with text mode + capture_output + UTF-16 console output.
    """
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout)
    except FileNotFoundError as e:
        return 127, "", f"command not found: {cmd[0]} ({e})"
    except subprocess.TimeoutExpired:
        return 124, "", f"command timed out after {timeout}s"
    out = r.stdout.decode("utf-8", errors="replace")
    err = r.stderr.decode("utf-8", errors="replace")
    return r.returncode, out, err


def detect_repo() -> str | None:
    """Detect owner/repo from the current git remote via `gh repo view`."""
    code, out, err = run(["gh", "repo", "view", "--json", "nameWithOwner"])
    if code != 0:
        # Fallback: parse git remote
        code2, out2, _ = run(["git", "remote", "get-url", "origin"])
        if code2 != 0:
            return None
        url = out2.strip()
        # Parse https://github.com/OWNER/REPO.git or git@github.com:OWNER/REPO.git
        for prefix in ("https://github.com/", "git@github.com:"):
            if url.startswith(prefix):
                repo = url[len(prefix):]
                if repo.endswith(".git"):
                    repo = repo[:-4]
                return repo
        return None
    try:
        return json.loads(out)["nameWithOwner"]
    except (json.JSONDecodeError, KeyError):
        return None


def gh_notifications(etag: str | None) -> tuple[int, list[dict] | None, str | None, str | None]:
    """
    Fetch notifications via gh api.
    Returns: (status_code, notifications, new_etag, last_modified)
      - status_code: 200 (new data), 304 (not modified), other (error)
      - notifications: list of dicts (empty on 304 or error)
      - new_etag: ETag header value (or None)
      - last_modified: Last-Modified header value (or None)
    """
    # `gh api` doesn't directly expose headers; use `gh api --include` to
    # get the full HTTP response (headers + body, separated by \r\n\r\n).
    cmd = ["gh", "api", "--include", "/notifications?participating=true&per_page=50"]
    if etag:
        cmd.insert(2, f"If-None-Match: {etag}")
        cmd.insert(2, "-H")
    code, out, err = run(cmd, timeout=20)
    if code != 0:
        return code, None, None, None
    # Parse the --include output: HTTP/1.1 status line, headers, blank line, body
    if "\r\n\r\n" in out:
        head, body = out.split("\r\n\r\n", 1)
    elif "\n\n" in out:
        head, body = out.split("\n\n", 1)
    else:
        return code, None, None, None
    new_etag = None
    last_modified = None
    status_code = 200
    for line in head.splitlines():
        if line.lower().startswith("etag:"):
            new_etag = line.split(":", 1)[1].strip()
        elif line.lower().startswith("last-modified:"):
            last_modified = line.split(":", 1)[1].strip()
        elif line.startswith("HTTP/"):
            try:
                status_code = int(line.split()[1])
            except (IndexError, ValueError):
                pass
    if status_code == 304 or not body.strip():
        return status_code, [], new_etag, last_modified
    try:
        notifs = json.loads(body)
    except json.JSONDecodeError:
        return status_code, None, new_etag, last_modified
    return status_code, notifs, new_etag, last_modified


def gh_pr_state(pr: int, repo: str) -> dict | None:
    """Fetch PR state for review tracking."""
    code, out, err = run([
        "gh", "pr", "view", str(pr), "--repo", repo, "--json",
        "reviewDecision,latestReviews,state,comments,number,title,url"
    ], timeout=20)
    if code != 0:
        return None
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return None


def state_diff(initial: dict | None, current: dict) -> list[dict]:
    """Diff two PR states, return list of changes."""
    if not initial:
        return []
    changes: list[dict] = []
    for key in ("reviewDecision", "state"):
        if initial.get(key) != current.get(key):
            changes.append({
                "field": key,
                "before": initial.get(key),
                "after": current.get(key),
            })
    init_latest = initial.get("latestReviews") or []
    curr_latest = current.get("latestReviews") or []
    if len(curr_latest) > len(init_latest):
        new_reviews = curr_latest[len(init_latest):]
        for r in new_reviews:
            changes.append({
                "field": "newReview",
                "author": (r.get("author") or {}).get("login"),
                "state": r.get("state"),
                "submittedAt": r.get("submittedAt"),
                "body": (r.get("body") or "")[:500],
            })
    init_comments = (initial.get("comments") or [])
    curr_comments = (current.get("comments") or [])
    if len(curr_comments) > len(init_comments):
        for c in curr_comments[len(init_comments):]:
            changes.append({
                "field": "newComment",
                "author": (c.get("author") or {}).get("login"),
                "body": (c.get("body") or "")[:500],
                "createdAt": c.get("createdAt"),
            })
    return changes


def notif_is_pr_review(notif: dict) -> dict | None:
    """
    If this notification is a PR review / review comment / PR comment,
    return a normalized event. Else return None.
    """
    subject = notif.get("subject") or {}
    stype = subject.get("type")
    if stype not in ("PullRequest", "Commit"):
        # IssueComment events have subject.type == Issue; we still want
        # them if the issue is a PR. Check the URL pattern.
        url = subject.get("latest_comment_url") or subject.get("url") or ""
        if "/pulls/" not in url:
            return None
    raw_url = (notif.get("repository") or {}).get("html_url") or ""
    # Extract PR number from the subject's latest_comment_url or url
    pr_url = subject.get("latest_comment_url") or subject.get("url") or ""
    pr_number = None
    if "/pulls/" in pr_url:
        try:
            pr_number = int(pr_url.split("/pulls/")[1].split("/")[0].split("?")[0])
        except (ValueError, IndexError):
            pr_number = None
    if not pr_number:
        return None
    return {
        "event": "notification",
        "kind": subject.get("type", "unknown").lower(),
        "reason": notif.get("reason"),
        "pr_number": pr_number,
        "pr_url": f"{raw_url}/pull/{pr_number}",
        "title": subject.get("title"),
        "updated_at": notif.get("updated_at"),
        "unread": notif.get("unread", True),
        "ts": now_iso(),
    }


def emit(event: dict, log_path: Path | None, nats_subject: str, emit_nats: bool, as_json: bool):
    """Emit an event to stdout, optional JSONL log, optional NATS."""
    line = json.dumps(event) if as_json else pretty_print(event)
    print(line, flush=True)
    if log_path:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")
    if emit_nats:
        publish_nats(nats_subject, event)


def pretty_print(event: dict) -> str:
    """Human-readable one-line event."""
    if event.get("event") == "notification":
        return (f"[{event['ts']}] NOTIFICATION on PR #{event['pr_number']} "
                f"({event.get('kind')}) reason={event.get('reason')} "
                f"title={event.get('title')!r}")
    if event.get("event") == "review_state_change":
        return (f"[{event['ts']}] REVIEW-STATE-CHANGE on PR #{event['pr']} "
                f"in {event['repo']}: {event['changes']}")
    if event.get("event") == "nats_message":
        return (f"[{event['ts']}] NATS on {event['subject']}: {event.get('data', '')[:200]}")
    return json.dumps(event)


def publish_nats(subject: str, payload: dict) -> bool:
    """Best-effort NATS publish. Tries nats CLI, then nats-py, then no-op."""
    data = json.dumps(payload).encode()
    nats_url = os.environ.get("NATS_URL", "nats://nats:pmoves@localhost:4222")
    # Try nats CLI
    code, _, _ = run(["nats", "pub", "--server", nats_url, subject, data.decode()], timeout=5)
    if code == 0:
        return True
    # Try nats-py
    code, _, _ = run([sys.executable, "-c", f"""
import asyncio, nats, os
async def pub():
    nc = await nats.connect(os.environ.get('NATS_URL', '{nats_url}'), connect_timeout=2)
    await nc.publish('{subject}', {data!r})
    await nc.drain()
asyncio.run(pub())
"""], timeout=5)
    return code == 0


def parse_duration(s: str) -> int:
    """Parse '1h', '30m', '90s', '24h' → seconds."""
    s = s.strip().lower()
    if s.endswith("h"):
        return int(s[:-1]) * 3600
    if s.endswith("m"):
        return int(s[:-1]) * 60
    if s.endswith("s"):
        return int(s[:-1])
    return int(s)


# --- Modes --------------------------------------------------------------------

def mode_notifications(args, prs: list[int] | None) -> int:
    """Mode: notifications — listen for new GitHub notifications via ETag."""
    print(f"[{now_iso()}] mode=notifications, watching repo={args.repo}, "
          f"filter_prs={prs or 'ALL'}", file=sys.stderr)
    etag: str | None = None
    last_modified: str | None = None
    end = time.monotonic() + args.max_runtime_s
    interval = args.interval
    log_path = Path(args.log) if args.log else None
    while time.monotonic() < end:
        status, notifs, new_etag, new_last_mod = gh_notifications(etag)
        if status == 200 and notifs is not None:
            # Filter to PR-related notifications
            for n in notifs:
                evt = notif_is_pr_review(n)
                if not evt:
                    continue
                if prs and evt["pr_number"] not in prs:
                    continue
                emit(evt, log_path, args.nats_subject, args.emit_nats, args.json)
            etag = new_etag
            last_modified = new_last_mod
        elif status == 304:
            # Not modified — bump interval (exponential backoff up to cap)
            interval = min(interval * 2, args.max_interval)
        else:
            # Error — try again with smaller interval
            interval = max(args.interval, interval // 2)
        time.sleep(interval)
        interval = max(args.interval, interval // 2)  # reset toward base
    print(f"[{now_iso()}] timeout: no matching notification in {args.max_runtime_s}s",
          file=sys.stderr)
    return 1


def mode_pr_watch(args, prs: list[int]) -> int:
    """Mode: pr-watch — poll per-PR review state for each PR in `prs`."""
    if not prs:
        print("error: --pr or --prs required for mode=pr-watch", file=sys.stderr)
        return 2
    print(f"[{now_iso()}] mode=pr-watch, prs={prs}, repo={args.repo}, "
          f"interval={args.interval}s, max_runtime={args.max_runtime_s}s",
          file=sys.stderr)
    log_path = Path(args.log) if args.log else None
    initial_states = {pr: gh_pr_state(pr, args.repo) for pr in prs}
    for pr, st in initial_states.items():
        if st is None:
            print(f"warning: could not read PR #{pr} initial state", file=sys.stderr)
            continue
        print(f"[{now_iso()}] PR #{pr}: reviewDecision={st.get('reviewDecision')}, "
              f"latestReviews={len(st.get('latestReviews') or [])}, "
              f"comments={len(st.get('comments') or [])}", file=sys.stderr)
    end = time.monotonic() + args.max_runtime_s
    while time.monotonic() < end:
        time.sleep(args.interval)
        for pr in prs:
            current = gh_pr_state(pr, args.repo)
            if not current:
                continue
            changes = state_diff(initial_states.get(pr), current)
            if changes:
                event = {
                    "event": "review_state_change",
                    "pr": pr,
                    "repo": args.repo,
                    "ts": now_iso(),
                    "changes": changes,
                    "current": {
                        "reviewDecision": current.get("reviewDecision"),
                        "state": current.get("state"),
                        "latestReviews_count": len(current.get("latestReviews") or []),
                        "comments_count": len(current.get("comments") or []),
                    },
                }
                emit(event, log_path, args.nats_subject, args.emit_nats, args.json)
                return 0
            # Update initial state baseline (so we only see NEW changes)
            initial_states[pr] = current
    print(f"[{now_iso()}] timeout: no review state change in {args.max_runtime_s}s",
          file=sys.stderr)
    return 1


def mode_nats(args, prs: list[int] | None) -> int:
    """Mode: nats — subscribe to github.webhook.review.* subjects."""
    print(f"[{now_iso()}] mode=nats, subjects={NATS_REVIEW_SUBJECTS}, "
          f"filter_prs={prs or 'ALL'}", file=sys.stderr)
    log_path = Path(args.log) if args.log else None
    nats_url = os.environ.get("NATS_URL", "nats://nats:pmoves@localhost:4222")
    # Use nats-py if available, else nats CLI sub
    try:
        import nats  # type: ignore
    except ImportError:
        return mode_nats_cli(args, prs, log_path)
    import asyncio

    async def run_nats():
        nc = await nats.connect(nats_url, connect_timeout=3)
        events: list[dict] = []

        async def handler(msg):
            try:
                data = json.loads(msg.data.decode())
            except (json.JSONDecodeError, UnicodeDecodeError):
                data = {"raw": msg.data.decode(errors="replace")[:500]}
            evt = {
                "event": "nats_message",
                "subject": msg.subject,
                "data": data,
                "ts": now_iso(),
            }
            # Filter by PR if requested
            pr_n = (data.get("pull_request", {}).get("number")
                    or data.get("issue", {}).get("number")
                    or data.get("number"))
            if prs and pr_n and int(pr_n) not in prs:
                return
            events.append(evt)
            emit(evt, log_path, args.nats_subject, args.emit_nats, args.json)
            await nc.drain()

        for subj in NATS_REVIEW_SUBJECTS:
            await nc.subscribe(subj, cb=handler)
        # Block until max_runtime
        await asyncio.sleep(args.max_runtime_s)
        await nc.drain()
        return 1 if not events else 0

    try:
        return asyncio.run(run_nats())
    except Exception as e:
        print(f"error: nats subscribe failed: {e}", file=sys.stderr)
        return 2


def mode_nats_cli(args, prs: list[int] | None, log_path: Path | None) -> int:
    """Fallback: nats CLI sub (less robust than nats-py)."""
    nats_url = os.environ.get("NATS_URL", "nats://nats:pmoves@localhost:4222")
    subjects_filter = ",".join(NATS_REVIEW_SUBJECTS)
    cmd = ["nats", "sub", "--server", nats_url, subjects_filter]
    print(f"[{now_iso()}] running: {' '.join(cmd)}", file=sys.stderr)
    try:
        r = subprocess.run(cmd, timeout=args.max_runtime_s)
        return r.returncode
    except subprocess.TimeoutExpired:
        return 1
    except FileNotFoundError:
        print("error: nats CLI not found and nats-py not installed", file=sys.stderr)
        return 2


# --- Main ---------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(
        description="Listen for GitHub review events on PMOVES.AI PRs (no polling).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--mode", choices=["notifications", "pr-watch", "nats"],
                    default="notifications",
                    help="Listen mode. Default: notifications (ETag-based).")
    ap.add_argument("--pr", type=int, help="Watch a single PR (pr-watch mode).")
    ap.add_argument("--prs", type=str,
                    help="Comma-separated PR numbers to watch (e.g. 2132,2133,2134).")
    ap.add_argument("--repo", help="owner/repo. Default: detect from git remote.")
    ap.add_argument("--max-runtime", default="1h",
                    help="Max time to listen (e.g. 1h, 30m, 24h). Default: 1h.")
    ap.add_argument("--interval", type=int, default=30,
                    help="Base poll interval in seconds (notifications/pr-watch modes).")
    ap.add_argument("--max-interval", type=int, default=300,
                    help="Max backoff interval in seconds (notifications mode).")
    ap.add_argument("--log", help="Append events to this JSONL file.")
    ap.add_argument("--json", action="store_true", help="Emit JSON to stdout.")
    ap.add_argument("--emit-nats", action="store_true",
                    help="Also publish events to NATS (subject --nats-subject).")
    ap.add_argument("--nats-subject", default=DEFAULT_NATS_SUBJECT,
                    help=f"NATS subject for outbound events. Default: {DEFAULT_NATS_SUBJECT}")
    args = ap.parse_args()

    args.max_runtime_s = parse_duration(args.max_runtime)

    # Detect repo
    if not args.repo:
        args.repo = detect_repo()
        if not args.repo:
            print("error: could not detect repo. Pass --repo owner/name.", file=sys.stderr)
            return 2
    print(f"[{now_iso()}] repo={args.repo}", file=sys.stderr)

    # Resolve PR list
    prs: list[int] | None = None
    if args.pr:
        prs = [args.pr]
    elif args.prs:
        prs = [int(x.strip()) for x in args.prs.split(",") if x.strip()]

    # Graceful Ctrl-C
    def _sigint(_sig, _frm):
        print(f"\n[{now_iso()}] SIGINT — exiting", file=sys.stderr)
        sys.exit(130)
    signal.signal(signal.SIGINT, _sigint)

    if args.mode == "notifications":
        return mode_notifications(args, prs)
    if args.mode == "pr-watch":
        return mode_pr_watch(args, prs or [])
    if args.mode == "nats":
        return mode_nats(args, prs)
    return 2


if __name__ == "__main__":
    sys.exit(main())
