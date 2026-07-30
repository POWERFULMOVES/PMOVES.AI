#!/usr/bin/env python3
"""PR Hedge Trim — classify, fix, and resolve CodeRabbit review threads."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List


# Reuse classification tokens from pr_monitor
ACTIONABLE_TOKENS = (
    "[p0",
    "[p1",
    "[p2",
    "error",
    "failing",
    "failed",
    "hard-fail",
    "missing",
    "must",
    "required",
    "security",
    "vulnerability",
    "unsafe",
    "leak",
    "injection",
    "conflict",
    "blocker",
    "invalid",
    "incompatible",
)
# CodeRabbit tags Nitpick findings with 🧹; that TYPE marker is authoritative over
# incidental keyword matches (a "🧹 Nitpick: foo is missing a prefix" is a nitpick,
# not an actionable "missing" hit).
NITPICK_TOKENS = ("🧹", "nitpick", "nit:", "nits", "style-only")
# Explicit high-severity markers from the review bots — an authoritative "this is a real
# issue" signal that must NOT fall through to the nitpick default:
#   CodeRabbit: ⚠️ Potential issue, 🔴 Critical, 🟠 Major
#   Codex:      P0/P1/P2 Badge (rendered as image alt-text in the comment body)
ACTIONABLE_MARKERS = (
    "potential issue",
    "🔴",
    "🟠",
    "p0 badge",
    "p1 badge",
    "p2 badge",
)
DESIGN_TOKENS = (
    "intentional",
    "by design",
    "design decision",
    "trade-off",
    "tradeoff",
    "rationale",
    "deliberate",
)
FALSE_POSITIVE_TOKENS = (
    "false positive",
    "false-positive",
    "not applicable",
    "n/a",
    "already handled",
    "already exists",
    "already fixed",
    "stale",
)

BOT_LOGINS = {"coderabbitai[bot]", "chatgpt-codex-connector[bot]"}

DEFAULT_REPO = "POWERFULMOVES/PMOVES.AI"
DEFAULT_BASE = "PMOVES.AI-Edition-Hardened"
LOGS_DIR = Path(__file__).resolve().parent.parent / "docs" / "logs"

# ---------------------------------------------------------------------------
# Node Agent Review Routing (mirrors mesh.gpu.status.v1 pattern)
# ---------------------------------------------------------------------------
# Maps content keywords to the best-fit node agent for review.
# 4090-claude is the default — the "noise reducer" catches everything else.

_NODE_REVIEW_KEYWORDS: dict[str, str] = {
    "docker": "z890-claude",
    "compose": "z890-claude",
    "dockerfile": "z890-claude",
    "secrets": "z890-claude",
    "nats": "z890-claude",
    "makefile": "z890-claude",
    "env.shared": "z890-claude",
    "env.tier": "z890-claude",
    "tts": "5090-claude",
    "voice": "5090-claude",
    "pipecat": "5090-claude",
    "gpu": "5090-claude",
    "model": "5090-claude",
    "whisper": "5090-claude",
    "ollama": "5090-claude",
    "vram": "5090-claude",
    "nitpick": "4090-claude",
    "pattern": "4090-claude",
    "submodule": "4090-claude",
    "docs": "4090-claude",
    "audit": "4090-claude",
    "readme": "4090-claude",
}

_DEFAULT_REVIEWER = "4090-claude"


def suggest_reviewer(thread_body: str) -> str:
    """Route a PR thread to the best-fit node agent based on content keywords.

    Scoring: each keyword match adds +1 to the matching agent's score.
    Ties and zero-score threads default to 4090-claude (noise reducer).
    """
    body_lower = thread_body.lower()
    scores: dict[str, int] = {"z890-claude": 0, "5090-claude": 0, "4090-claude": 0}
    for keyword, agent in _NODE_REVIEW_KEYWORDS.items():
        if keyword in body_lower:
            scores[agent] += 1
    best = max(scores, key=scores.get)  # type: ignore[arg-type]
    return best if scores[best] > 0 else _DEFAULT_REVIEWER


# ---------------------------------------------------------------------------
# Helpers (reused from pr_monitor.py patterns)
# ---------------------------------------------------------------------------


def _run_json(cmd: list[str]) -> Any:
    """Run a CLI command and parse JSON output."""
    proc = subprocess.run(cmd, text=True, capture_output=True, check=False, encoding="utf-8")
    if proc.returncode != 0:
        raise RuntimeError(f"command failed ({proc.returncode}): {' '.join(cmd)}\n{proc.stderr.strip()}")
    payload = proc.stdout.strip()
    if not payload:
        return None
    return json.loads(payload)


def _repo_name(default_repo: str) -> str:
    """Detect repo from current checkout."""
    try:
        data = _run_json(["gh", "repo", "view", "--json", "nameWithOwner"])
    except RuntimeError:
        return default_repo
    if isinstance(data, dict):
        candidate = data.get("nameWithOwner")
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return default_repo


def _resolve_repo(explicit_repo: str, default_repo: str) -> str:
    """Honor explicit --repo; only inspect current checkout when omitted."""
    repo = explicit_repo.strip()
    if repo:
        return repo
    return _repo_name(default_repo)


def _repo_owner_name(repo: str) -> tuple[str, str]:
    """Split repo into (owner, name)."""
    if "/" not in repo:
        raise ValueError(f"invalid repo format: {repo!r} (expected owner/name)")
    owner, name = repo.split("/", 1)
    return owner.strip(), name.strip()


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class ThreadComment:
    """A single comment within a review thread."""

    body: str
    author: str
    is_bot: bool
    url: str
    path: str
    line: int | None


@dataclass
class ReviewThread:
    """A review thread with classification metadata."""

    thread_id: str
    is_resolved: bool
    is_outdated: bool
    comments: List[ThreadComment]
    classification: str  # actionable | design-decision | false-positive | nitpick
    first_path: str
    first_line: int | None


@dataclass
class TrimReport:
    """Summary of a PR trim operation."""

    pr_number: int
    repo: str
    total_threads: int = 0
    unresolved_threads: int = 0
    actionable: int = 0
    design_decision: int = 0
    false_positive: int = 0
    nitpick: int = 0
    resolved_count: int = 0
    threads: List[ReviewThread] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Four-way classification
# ---------------------------------------------------------------------------


def classify_comment(body: str, *, is_bot: bool = True) -> str:
    """Classify a review comment into one of four categories.

    Categories:
        actionable — Fix-worthy (security, bug, correctness, missing code)
        design-decision — Author's intentional choice, needs documented rationale
        false-positive — Bot misunderstood context
        nitpick — Style/cosmetic, defer

    Args:
        body: The comment text to classify.
        is_bot: Whether the comment author is a bot. Unclassified bot
            comments default to nitpick; unclassified human comments
            default to actionable.
    """
    text = body.lower()
    # 1. An author reply explicitly calling it a false positive wins.
    if any(token in text for token in FALSE_POSITIVE_TOKENS):
        return "false-positive"
    # 2. High-severity explicit markers win FIRST — a Codex P1/P2 badge or CodeRabbit
    #    🔴 Critical / 🟠 Major / ⚠️ Potential issue is actionable even if its PROSE
    #    mentions the word "nitpick" (Codex #1985 P2: badges before broad nitpick words).
    if any(token in text for token in ACTIONABLE_MARKERS):
        return "actionable"
    # 3. Then CodeRabbit's 🧹 Nitpick TYPE marker — authoritative over the keyword
    #    heuristics below, so a "🧹 Nitpick: x is missing a prefix" stays a nitpick and
    #    is not swept up by the "missing"/"must" actionable keywords.
    if any(token in text for token in NITPICK_TOKENS):
        return "nitpick"
    # 4. Fall back to keyword heuristics.
    if any(token in text for token in DESIGN_TOKENS):
        return "design-decision"
    if any(token in text for token in ACTIONABLE_TOKENS):
        return "actionable"
    # Default: unclassified comments from bots are nitpick, from humans are actionable.
    return "nitpick" if is_bot else "actionable"


def classify_thread(thread: ReviewThread) -> str:
    """Classify a thread based on all its comments.

    Priority: actionable > design-decision > false-positive > nitpick.
    """
    classifications = [
        classify_comment(c.body, is_bot=c.is_bot)
        for c in thread.comments
        if c.body.strip()
    ]
    if "actionable" in classifications:
        return "actionable"
    if "design-decision" in classifications:
        return "design-decision"
    if "false-positive" in classifications:
        return "false-positive"
    return "nitpick"


# ---------------------------------------------------------------------------
# GraphQL: fetch threads with full metadata
# ---------------------------------------------------------------------------


def fetch_threads(repo: str, number: int) -> list[ReviewThread]:
    """Fetch all review threads for a PR via GraphQL, including thread IDs."""
    owner, name = _repo_owner_name(repo)
    threads: list[ReviewThread] = []
    cursor: str | None = None

    query = (
        "query($owner:String!,$name:String!,$number:Int!,$after:String){"
        "repository(owner:$owner,name:$name){"
        "pullRequest(number:$number){"
        "reviewThreads(first:100,after:$after){"
        "nodes{"
        "id isResolved isOutdated "
        "comments(first:100){"
        "nodes{body url path line author{login}}"
        "}"
        "}"
        "pageInfo{hasNextPage endCursor}"
        "}}}}"
    )

    while True:
        cmd = [
            "gh", "api", "graphql",
            "-f", f"query={query}",
            "-F", f"owner={owner}",
            "-F", f"name={name}",
            "-F", f"number={number}",
        ]
        if cursor:
            cmd.extend(["-F", f"after={cursor}"])

        payload = _run_json(cmd)
        if not isinstance(payload, dict):
            raise RuntimeError("unexpected GraphQL response: root payload is not an object")
        if payload.get("errors"):
            raise RuntimeError(f"GraphQL errors: {json.dumps(payload['errors'], ensure_ascii=False)}")
        data = payload.get("data")
        if not isinstance(data, dict):
            raise RuntimeError("unexpected GraphQL response: missing 'data' key")
        repository = data.get("repository")
        if not isinstance(repository, dict):
            raise RuntimeError(f"repository not found for {owner}/{name}")
        pr = repository.get("pullRequest")
        if not isinstance(pr, dict):
            raise RuntimeError(f"PR #{number} not found in {owner}/{name}")
        review_threads = pr.get("reviewThreads")
        if not isinstance(review_threads, dict):
            raise RuntimeError(f"reviewThreads missing from PR #{number}")

        nodes = review_threads.get("nodes")
        if isinstance(nodes, list):
            for node in nodes:
                if not isinstance(node, dict):
                    continue
                thread_id = str(node.get("id") or "")
                is_resolved = bool(node.get("isResolved"))
                is_outdated = bool(node.get("isOutdated"))

                comments_data = node.get("comments")
                if not isinstance(comments_data, dict):
                    continue
                comment_nodes = comments_data.get("nodes")
                if not isinstance(comment_nodes, list):
                    continue

                thread_comments: list[ThreadComment] = []
                for comment in comment_nodes:
                    if not isinstance(comment, dict):
                        continue
                    author_obj = comment.get("author")
                    author = str(author_obj.get("login") or "") if isinstance(author_obj, dict) else ""
                    thread_comments.append(ThreadComment(
                        body=str(comment.get("body") or ""),
                        author=author,
                        is_bot=author in BOT_LOGINS,
                        url=str(comment.get("url") or ""),
                        path=str(comment.get("path") or ""),
                        line=comment.get("line"),
                    ))

                first_path = thread_comments[0].path if thread_comments else ""
                first_line = thread_comments[0].line if thread_comments else None

                rt = ReviewThread(
                    thread_id=thread_id,
                    is_resolved=is_resolved,
                    is_outdated=is_outdated,
                    comments=thread_comments,
                    classification="",
                    first_path=first_path,
                    first_line=first_line,
                )
                rt.classification = classify_thread(rt)
                threads.append(rt)

        page_info = review_threads.get("pageInfo")
        if not isinstance(page_info, dict):
            break
        has_next = bool(page_info.get("hasNextPage"))
        next_cursor = str(page_info.get("endCursor") or "").strip()
        if not has_next or not next_cursor:
            break
        cursor = next_cursor

    return threads


# ---------------------------------------------------------------------------
# GraphQL: resolve threads
# ---------------------------------------------------------------------------


def resolve_thread(thread_id: str, *, dry_run: bool = False) -> bool:
    """Resolve a review thread via GraphQL mutation.

    Returns True on success, False on failure.
    """
    if dry_run:
        print(f"  [dry-run] Would resolve thread {thread_id}")
        return True

    mutation = (
        "mutation($threadId:ID!){"
        "resolveReviewThread(input:{threadId:$threadId}){"
        "thread{id isResolved}"
        "}}"
    )
    cmd = [
        "gh", "api", "graphql",
        "-f", f"query={mutation}",
        "-F", f"threadId={thread_id}",
    ]
    try:
        result = _run_json(cmd)
        if isinstance(result, dict):
            data = result.get("data")
            if isinstance(data, dict):
                resolve_data = data.get("resolveReviewThread")
                if resolve_data is None:
                    print(f"  [warn] resolveReviewThread returned null for {thread_id}", file=sys.stderr)
                    return False
                thread = resolve_data.get("thread") or {}
                return bool(thread.get("isResolved"))
        return False
    except RuntimeError as exc:
        print(f"  [error] Failed to resolve thread {thread_id}: {exc}", file=sys.stderr)
        return False


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------


def cmd_analyze(repo: str, pr_number: int, *, json_out: Path | None = None) -> TrimReport:
    """Fetch and classify unresolved review threads for a PR."""
    all_threads = fetch_threads(repo, pr_number)
    unresolved = [t for t in all_threads if not t.is_resolved]

    report = TrimReport(
        pr_number=pr_number,
        repo=repo,
        total_threads=len(all_threads),
        unresolved_threads=len(unresolved),
        threads=unresolved,
    )

    for thread in unresolved:
        if thread.classification == "actionable":
            report.actionable += 1
        elif thread.classification == "design-decision":
            report.design_decision += 1
        elif thread.classification == "false-positive":
            report.false_positive += 1
        elif thread.classification == "nitpick":
            report.nitpick += 1

    # Print classification table
    print(f"\n## PR #{pr_number} — Hedge Trim Analysis")
    print(f"Total threads: {report.total_threads} | Unresolved: {report.unresolved_threads}")
    print("| # | Classification | Path | Line | Excerpt |")
    print("|--:|---|---|---:|---|")
    for i, thread in enumerate(unresolved, 1):
        excerpt = " ".join((thread.comments[0].body if thread.comments else "").split())[:120]
        if len(excerpt) == 120:
            excerpt += "..."
        path = thread.first_path or "(general)"
        line = str(thread.first_line) if thread.first_line else "-"
        print(f"| {i} | **{thread.classification}** | `{path}` | {line} | {excerpt} |")
    print()

    # Summary
    print(f"Actionable: {report.actionable} | Design: {report.design_decision} | "
          f"False-positive: {report.false_positive} | Nitpick: {report.nitpick}")

    # Write JSON artifact
    out_path = json_out or LOGS_DIR / f"pr_trim_{pr_number}_threads.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = _serialize_report(report)
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\nWrote: {out_path}")

    return report


def cmd_resolve(
    repo: str,
    pr_number: int,
    *,
    dry_run: bool = False,
    classifications: tuple[str, ...] = ("false-positive", "design-decision"),
) -> int:
    """Resolve addressed review threads via GraphQL mutation.

    By default resolves false-positive and design-decision threads.
    Actionable threads are resolved only when explicitly included
    (after fixes have been pushed). Nitpick threads are never auto-resolved.
    """
    all_threads = fetch_threads(repo, pr_number)
    unresolved = [t for t in all_threads if not t.is_resolved]
    resolved_count = 0
    failed_count = 0

    print(f"\n## PR #{pr_number} — Resolving threads ({', '.join(classifications)})")
    for thread in unresolved:
        if thread.classification not in classifications:
            continue
        path = thread.first_path or "(general)"
        print(f"  [{thread.classification}] {path}:{thread.first_line or '-'}")
        if resolve_thread(thread.thread_id, dry_run=dry_run):
            resolved_count += 1
        else:
            failed_count += 1
            print(f"  [FAILED] could not resolve thread at {path}:{thread.first_line or '-'}", file=sys.stderr)

    mode = "dry-run" if dry_run else "resolved"
    print(f"\n{mode}: {resolved_count}/{len(unresolved)} threads")
    if failed_count:
        print(f"FAILED: {failed_count} thread(s) could not be resolved", file=sys.stderr)
    return resolved_count


def cmd_report(repo: str, pr_number: int, *, md_out: Path | None = None) -> None:
    """Generate a human-readable trim summary report."""
    report = cmd_analyze(repo, pr_number)
    out_path = md_out or LOGS_DIR / f"pr_trim_{pr_number}_summary.md"

    lines: list[str] = []
    lines.append(f"# PR Hedge Trim Report — #{pr_number}")
    lines.append("")
    lines.append(f"_Generated: {datetime.now(timezone.utc).isoformat()}_")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Count |")
    lines.append("|---|---:|")
    lines.append(f"| Total threads | {report.total_threads} |")
    lines.append(f"| Unresolved | {report.unresolved_threads} |")
    lines.append(f"| Actionable | {report.actionable} |")
    lines.append(f"| Design decision | {report.design_decision} |")
    lines.append(f"| False positive | {report.false_positive} |")
    lines.append(f"| Nitpick | {report.nitpick} |")
    lines.append("")

    if report.threads:
        lines.append("## Thread Details")
        lines.append("")
        for i, thread in enumerate(report.threads, 1):
            lines.append(f"### Thread {i} — {thread.classification}")
            lines.append(f"- **Path:** `{thread.first_path or '(general)'}`")
            if thread.first_line:
                lines.append(f"- **Line:** {thread.first_line}")
            lines.append(f"- **Outdated:** {'yes' if thread.is_outdated else 'no'}")
            lines.append("")
            for j, comment in enumerate(thread.comments):
                bot_tag = " (bot)" if comment.is_bot else ""
                lines.append(f"**Comment {j+1}** by `{comment.author}`{bot_tag}:")
                # Truncate long comments
                body = comment.body.strip()
                if len(body) > 500:
                    body = body[:497] + "..."
                lines.append(f"> {body}")
                lines.append("")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote report: {out_path}")


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def _serialize_report(report: TrimReport) -> dict[str, Any]:
    """Serialize a TrimReport to a JSON-compatible dict."""
    return {
        "pr_number": report.pr_number,
        "repo": report.repo,
        "agent_id": os.environ.get("AGENT_ID", "claude-code-cli"),
        "total_threads": report.total_threads,
        "unresolved_threads": report.unresolved_threads,
        "actionable": report.actionable,
        "design_decision": report.design_decision,
        "false_positive": report.false_positive,
        "nitpick": report.nitpick,
        "resolved_count": report.resolved_count,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "threads": [
            {
                "thread_id": t.thread_id,
                "classification": t.classification,
                "is_resolved": t.is_resolved,
                "is_outdated": t.is_outdated,
                "first_path": t.first_path,
                "first_line": t.first_line,
                "comments": [
                    {
                        "author": c.author,
                        "is_bot": c.is_bot,
                        "path": c.path,
                        "line": c.line,
                        "url": c.url,
                        "excerpt": " ".join(c.body.split())[:180],
                    }
                    for c in t.comments
                ],
            }
            for t in report.threads
        ],
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for PR Hedge Trim."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo",
        default="",
        help="owner/repo override (default: auto-detect)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # analyze
    p_analyze = sub.add_parser("analyze", help="Fetch and classify unresolved review threads")
    p_analyze.add_argument("--pr", type=int, required=True, help="PR number")
    p_analyze.add_argument("--json-out", type=Path, default=None, help="JSON output path")

    # resolve
    p_resolve = sub.add_parser("resolve", help="Resolve addressed review threads")
    p_resolve.add_argument("--pr", type=int, required=True, help="PR number")
    p_resolve.add_argument("--dry-run", action="store_true", help="Print what would be resolved")
    p_resolve.add_argument(
        "--include-actionable",
        action="store_true",
        help="Also resolve actionable threads (after fixes pushed)",
    )

    # report
    p_report = sub.add_parser("report", help="Generate trim summary report")
    p_report.add_argument("--pr", type=int, required=True, help="PR number")
    p_report.add_argument("--md-out", type=Path, default=None, help="Markdown output path")

    args = parser.parse_args(argv)
    repo = _resolve_repo(args.repo, DEFAULT_REPO)

    if args.command == "analyze":
        cmd_analyze(repo, args.pr, json_out=args.json_out)
        return 0

    if args.command == "resolve":
        classifications = ["false-positive", "design-decision"]
        if args.include_actionable:
            classifications.append("actionable")
        cmd_resolve(repo, args.pr, dry_run=args.dry_run, classifications=tuple(classifications))
        # Fetch remaining unresolved to detect failures
        remaining = [t for t in fetch_threads(repo, args.pr) if not t.is_resolved]
        target_threads = [t for t in remaining if t.classification in classifications]
        return 1 if target_threads else 0

    if args.command == "report":
        cmd_report(repo, args.pr, md_out=args.md_out)
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
