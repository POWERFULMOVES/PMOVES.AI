#!/usr/bin/env python3
"""Review Dump — collect PR review threads into LLM-readable JSON + Markdown.

Extends collect_review_comments.py (which writes to Supabase) with:
  - GraphQL review threads (resolved state + reply chains — REST misses these)
  - Committable-suggestion extraction (CodeRabbit ```suggestion blocks)
  - Diff context (the diff_hunk around each comment)
  - Structured JSON export for tooling
  - Human/LLM-readable Markdown export for local analysis
  - Optional fan-out to Hi-RAG (POST /hirag/upsert-batch) and Cipher (POST /api/memory)

Usage:
    # Dump a single PR to local files:
    python -m pmoves.tools.review_dump --repo PMOVES.AI --pr 2434

    # Dump all open PRs:
    python -m pmoves.tools.review_dump --repo PMOVES.AI --state open

    # Dump + ingest into Hi-RAG and Cipher:
    python -m pmoves.tools.review_dump --repo PMOVES.AI --pr 2434 --ingest-hirag --ingest-cipher

    # Dry-run (collect + export, no ingestion):
    python -m pmoves.tools.review_dump --repo PMOVES.AI --pr 2434 --dry-run

Output files land in pmoves/docs/logs/review-dumps/<repo>-<pr>.{json,md} by default.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

GITHUB_ORG = os.environ.get("PMOVES_GITHUB_ORG", "POWERFULMOVES")
GITHUB_TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
HIRAG_URL = os.environ.get("HIRAG_UPSERT_URL") or os.environ.get("HIRAG_URL", "http://localhost:8086")
CIPHER_URL = os.environ.get("CIPHER_API_URL", "http://localhost:8105")
CIPHER_TOKEN = os.environ.get("CIPHER_API_TOKEN", "")
OUTPUT_DIR = Path(os.environ.get("REVIEW_DUMP_DIR", _REPO_ROOT / "pmoves" / "docs" / "logs" / "review-dumps"))

SEVERITY_RE = re.compile(r"(?:P(\d)\s+Badge|severity[:\s]*P(\d))", re.IGNORECASE)
SUGGESTION_RE = re.compile(r"```suggestion\n(.*?)```", re.DOTALL)
NITPICK_RE = re.compile(r"\b(nitpick|nit\b)", re.IGNORECASE)


def _gh_headers() -> dict[str, str]:
    if not GITHUB_TOKEN:
        raise SystemExit("ERROR: GH_TOKEN or GITHUB_TOKEN not set")
    return {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}


def gh_rest(path: str) -> Any:
    req = urllib.request.Request(f"https://api.github.com{path}", headers=_gh_headers())
    try:
        return json.loads(urllib.request.urlopen(req, timeout=30).read())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return []
        raise


def gh_graphql(query: str, variables: dict[str, Any]) -> dict[str, Any]:
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={**_gh_headers(), "Content-Type": "application/json"},
    )
    return json.loads(urllib.request.urlopen(req, timeout=30).read())


THREADS_QUERY = """
query($owner: String!, $name: String!, $number: Int!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      title state mergedAt headRefName baseRefName additions deletions changedFiles
      author { login }
      reviewThreads(first: 100, after: $cursor) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id isResolved isOutdated path line
          comments(first: 20) {
            nodes {
              databaseId author { login } body path line originalLine diffHunk createdAt url
            }
          }
        }
      }
      reviews(first: 50) {
        nodes { author { login } state body submittedAt }
      }
    }
  }
}
"""


def fetch_threads(repo: str, pr_number: int) -> dict[str, Any]:
    owner, *rest = repo.split("/", 1)
    name = rest[0] if rest else repo
    result: dict[str, Any] = {}
    cursor = None
    while True:
        data = gh_graphql(THREADS_QUERY, {"owner": owner, "name": name, "number": pr_number, "cursor": cursor})
        pr = data["data"]["repository"]["pullRequest"]
        if not pr:
            raise SystemExit(f"ERROR: PR {repo}#{pr_number} not found")
        if not result:
            result = {
                "repo": repo, "pr_number": pr_number, "title": pr["title"], "state": pr["state"],
                "merged_at": pr.get("mergedAt"), "branch": pr["headRefName"], "base": pr["baseRefName"],
                "additions": pr["additions"], "deletions": pr["deletions"], "changed_files": pr["changedFiles"],
                "author": (pr.get("author") or {}).get("login", "unknown"),
                "collected_at": datetime.now(timezone.utc).isoformat(),
                "threads": [],
                "reviews": [
                    {"author": (r.get("author") or {}).get("login", "unknown"), "state": r["state"],
                     "body": r.get("body") or "", "submitted_at": r.get("submittedAt")}
                    for r in pr.get("reviews", {}).get("nodes", [])
                ],
            }
        result["threads"].extend(pr["reviewThreads"]["nodes"])
        if pr["reviewThreads"]["pageInfo"]["hasNextPage"]:
            cursor = pr["reviewThreads"]["pageInfo"]["endCursor"]
        else:
            break
    return result


def extract_severity(body: str) -> str:
    m = SEVERITY_RE.search(body)
    if m:
        for g in m.groups():
            if g and g.isdigit():
                return f"P{g}"
    if NITPICK_RE.search(body):
        return "nitpick"
    low = body.lower()
    if "praise" in low:
        return "praise"
    if "question" in low:
        return "question"
    return "unclassified"


def extract_suggestions(body: str) -> list[str]:
    return [m.group(1).rstrip() for m in SUGGESTION_RE.finditer(body)]


def classify_author(author: str) -> str:
    if "[bot]" in author or author in {"coderabbitai", "chatgpt-codex-connector", "github-actions", "dependabot"}:
        return "bot"
    return "human"


def thread_to_record(thread: dict[str, Any]) -> dict[str, Any]:
    comments = thread.get("comments", {}).get("nodes", [])
    if not comments:
        return {}
    first = comments[0]
    body = first.get("body", "")
    path = thread.get("path") or first.get("path")
    line = thread.get("line") or first.get("line") or first.get("originalLine")
    replies = [
        {"author": (r.get("author") or {}).get("login", "unknown"), "body": r.get("body", ""), "created_at": r.get("createdAt")}
        for r in comments[1:]
    ]
    return {
        "thread_id": thread["id"], "is_resolved": thread.get("isResolved", False),
        "is_outdated": thread.get("isOutdated", False), "path": path, "line": line,
        "severity": extract_severity(body),
        "author": (first.get("author") or {}).get("login", "unknown"),
        "author_type": classify_author((first.get("author") or {}).get("login", "unknown")),
        "body": body, "suggestions": extract_suggestions(body),
        "diff_hunk": first.get("diffHunk", ""), "replies": replies,
        "url": first.get("url", ""), "created_at": first.get("createdAt"),
        "comments_truncated": len(comments) >= 20,
    }


def export_json(data: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def export_markdown(data: dict[str, Any], path: Path) -> None:
    lines: list[str] = []
    repo, pr = data["repo"], data["pr_number"]
    lines.append(f"# Review Dump — {repo}#{pr}\n\n**{data['title']}**\n\n")
    lines.append(f"- State: `{data['state']}` | Branch: `{data['branch']}` → `{data['base']}` | "
                 f"+{data['additions']}/-{data['deletions']} ({data['changed_files']} files)\n")
    lines.append(f"- Author: {data['author']} | Collected: {data['collected_at']}\n")
    records = data.get("thread_records", [])
    resolved = sum(1 for r in records if r["is_resolved"])
    actionable = [r for r in records if r["severity"] in ("P1", "P2") and not r["is_resolved"]]
    suggestions = [s for r in records for s in r["suggestions"]]
    lines.append(f"\n## Summary\n\n| Metric | Count |\n|---|---|\n")
    lines.append(f"| Total threads | {len(records)} |\n| Resolved | {resolved} |\n")
    lines.append(f"| Open P1/P2 (actionable) | {len(actionable)} |\n| Committable suggestions | {len(suggestions)} |\n")
    sev_counts: dict[str, int] = {}
    for r in records:
        sev_counts[r["severity"]] = sev_counts.get(r["severity"], 0) + 1
    if sev_counts:
        lines.append(f"\n**Severity breakdown:** {', '.join(f'{k}={v}' for k, v in sorted(sev_counts.items()))}\n")
    if data.get("reviews"):
        lines.append(f"\n## Reviews ({len(data['reviews'])})\n\n")
        for rev in data["reviews"]:
            lines.append(f"- **{rev['author']}** ({rev['state']}) — {(rev.get('body') or '')[:200].replace(chr(10), ' ')}\n")
    if not records:
        lines.append(f"\n*No review threads found.*\n")
    else:
        lines.append(f"\n## Threads\n\n")
        for i, r in enumerate(records, 1):
            status = "✅" if r["is_resolved"] else ("⚠️" if r["is_outdated"] else "🔴")
            lines.append(f"### {i}. {status} [{r['severity']}] {r['author']} — `{r['path']}:{r['line']}`\n\n")
            lines.append(f"{r['body'][:2000]}\n\n")
            if r["suggestions"]:
                lines.append(f"**Committable suggestion(s):**\n\n")
                for s in r["suggestions"]:
                    lines.append(f"```suggestion\n{s}\n```\n\n")
            if r["diff_hunk"]:
                lines.append(f"<details><summary>Diff context</summary>\n\n```diff\n{r['diff_hunk']}\n```\n\n</details>\n\n")
            if r["replies"]:
                lines.append(f"<details><summary>{len(r['replies'])} repl{'y' if len(r['replies'])==1 else 'ies'}</summary>\n\n")
                for rep in r["replies"]:
                    lines.append(f"- **{rep['author']}**: {rep['body'][:300]}\n")
                lines.append(f"\n</details>\n\n")
            if r["url"]:
                lines.append(f"[→ thread]({r['url']})\n\n")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(lines), encoding="utf-8")


def _record_to_text(r: dict[str, Any], pr_data: dict[str, Any]) -> str:
    parts = [
        f"PR {pr_data['repo']}#{pr_data['pr_number']}: {pr_data['title']}",
        f"Severity: {r['severity']} | Author: {r['author']} | Resolved: {r['is_resolved']}",
    ]
    if r.get("path"):
        parts.append(f"Location: {r['path']}:{r['line']}")
    parts.append(f"\n{r['body']}")
    if r["suggestions"]:
        parts.append("\nSuggested fix:")
        for s in r["suggestions"]:
            parts.append(f"  {s[:200]}")
    return "\n".join(parts)


def ingest_hirag_records(records: list[dict[str, Any]], pr_data: dict[str, Any]) -> int:
    items = [{
        "id": f"review-{pr_data['repo']}-{pr_data['pr_number']}-{r['thread_id'][-12:]}",
        "content": _record_to_text(r, pr_data),
        "metadata": {"type": "review_comment", "repo": pr_data["repo"], "pr_number": pr_data["pr_number"],
                     "severity": r["severity"], "path": r.get("path"), "author": r["author"], "is_resolved": r["is_resolved"]},
    } for r in records]
    body = json.dumps({"items": items}).encode()
    req = urllib.request.Request(f"{HIRAG_URL}/hirag/upsert-batch", data=body,
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        urllib.request.urlopen(req, timeout=30)
        return len(items)
    except Exception as e:
        print(f"  [hirag] error: {e}", file=sys.stderr)
        return 0


def ingest_cipher_records(records: list[dict[str, Any]], pr_data: dict[str, Any]) -> int:
    if not CIPHER_TOKEN:
        print("  [cipher] skip: CIPHER_API_TOKEN not set", file=sys.stderr)
        return 0
    count = 0
    for r in records:
        if r["severity"] not in ("P1", "P2"):
            continue
        body = json.dumps({
            "agentId": "review-collector", "category": "review_learning",
            "content": _record_to_text(r, pr_data),
            "metadata": {"repo": pr_data["repo"], "pr_number": pr_data["pr_number"],
                         "severity": r["severity"], "path": r.get("path"), "thread_id": r["thread_id"]},
            "tags": ["review", r["severity"], pr_data["repo"], "pr-learning"],
        }).encode()
        req = urllib.request.Request(f"{CIPHER_URL}/api/memory", data=body,
                                     headers={"Content-Type": "application/json", "Authorization": f"Bearer {CIPHER_TOKEN}"},
                                     method="POST")
        try:
            urllib.request.urlopen(req, timeout=10)
            count += 1
        except Exception as e:
            print(f"  [cipher] error on thread {r['thread_id'][-8:]}: {e}", file=sys.stderr)
    return count


def dump_pr(repo: str, pr_number: int, dry_run: bool, ingest_hirag: bool = False, ingest_cipher: bool = False) -> dict[str, Any]:
    full_repo = f"{GITHUB_ORG}/{repo}" if "/" not in repo else repo
    print(f"[review-dump] {full_repo}#{pr_number}")
    data = fetch_threads(full_repo, pr_number)
    records = [t for t in (thread_to_record(t) for t in data["threads"]) if t]
    data["thread_records"] = records
    slug = repo.replace("/", "-")
    json_path = OUTPUT_DIR / f"{slug}-{pr_number}.json"
    md_path = OUTPUT_DIR / f"{slug}-{pr_number}.md"
    export_json(data, json_path)
    export_markdown(data, md_path)
    print(f"  exported: {os.path.relpath(json_path, _REPO_ROOT)}")
    print(f"  exported: {os.path.relpath(md_path, _REPO_ROOT)}")
    print(f"  threads: {len(records)} ({sum(1 for r in records if r['is_resolved'])} resolved, "
          f"{sum(1 for r in records if r['severity'] in ('P1','P2') and not r['is_resolved'])} open P1/P2, "
          f"{sum(len(r['suggestions']) for r in records)} suggestions)")
    if ingest_hirag and not dry_run:
        n = ingest_hirag_records(records, data)
        print(f"  [hirag] ingested {n} records")
    if ingest_cipher and not dry_run:
        n = ingest_cipher_records(records, data)
        print(f"  [cipher] ingested {n} P1/P2 learnings")
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect PR review threads into LLM-readable JSON + Markdown")
    parser.add_argument("--repo", required=True, help="Repo name (e.g. PMOVES.AI, Pmoves-cipher)")
    parser.add_argument("--pr", type=int, help="Single PR number")
    parser.add_argument("--state", default="open", choices=["open", "merged", "closed", "all"])
    parser.add_argument("--limit", type=int, default=10, help="Max PRs to scan (when not --pr)")
    parser.add_argument("--dry-run", action="store_true", help="Collect + export only, no ingestion")
    parser.add_argument("--ingest-hirag", action="store_true", help="Fan out to Hi-RAG")
    parser.add_argument("--ingest-cipher", action="store_true", help="Fan out to Cipher memory")
    args = parser.parse_args()
    if args.pr:
        dump_pr(args.repo, args.pr, args.dry_run, ingest_hirag=args.ingest_hirag, ingest_cipher=args.ingest_cipher)
        return
    gh_state = "open" if args.state == "open" else ("all" if args.state == "all" else "closed")
    full_repo = f"{GITHUB_ORG}/{args.repo}" if "/" not in args.repo else args.repo
    prs = gh_rest(f"/repos/{full_repo}/pulls?state={gh_state}&per_page={min(args.limit, 100)}&sort=updated&direction=desc")
    if args.state == "merged":
        prs = [p for p in prs if p.get("merged_at")]
    print(f"[review-dump] {full_repo}: {len(prs)} PRs ({args.state})")
    for pr in prs:
        dump_pr(args.repo, pr["number"], args.dry_run, ingest_hirag=args.ingest_hirag, ingest_cipher=args.ingest_cipher)


if __name__ == "__main__":
    main()
