"""Fork-sync automation for PMOVES.AI monorepo.

Audit, sync, and track GitHub fork drift from upstream repositories.
Uses only `gh` CLI via subprocess — no Python GitHub libraries.

Usage:
    python3 -m pmoves.tools.fork_sync audit [--json]
    python3 -m pmoves.tools.fork_sync sync [--dry-run] [--fork NAME] [--threshold N] [--max N]
    python3 -m pmoves.tools.fork_sync status
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import date
from typing import Any


# ── ANSI colors ──────────────────────────────────────────────────────────────

RED = "\033[91m"
YELLOW = "\033[93m"
GREEN = "\033[92m"
GRAY = "\033[90m"
BOLD = "\033[1m"
RESET = "\033[0m"


def _color_for(behind: int) -> str:
    if behind >= 1000:
        return RED
    if behind >= 100:
        return YELLOW
    if behind >= 1:
        return GREEN
    return GRAY


# ── Hardcoded fork configuration ─────────────────────────────────────────────

FORK_CONFIG: dict[str, dict[str, str]] = {
    "PMOVES-ClawZ": {"upstream": "openclaw/openclaw"},
    "PMOVES-Creator": {"upstream": "Comfy-Org/ComfyUI"},
    "PMOVES-supabase": {
        "upstream": "supabase/supabase",
        "branch": "PMOVES.AI-Edition-Hardened",
    },
    "PMOVES-tensorzero": {"upstream": "tensorzero/tensorzero"},
    "PMOVES-Wealth": {"upstream": "firefly-iii/firefly-iii"},
    "PMOVES-a0-plugins": {"upstream": "agent0ai/a0-plugins"},
    "PMOVES-Archon": {"upstream": "coleam00/Archon"},
    "PMOVES-Open-Notebook": {"upstream": "lfnovo/open-notebook"},
    "PMOVES-hermes-agent": {"upstream": "NousResearch/hermes-agent"},
    "PMOVES-headscale": {"upstream": "juanfont/headscale"},
    "PMOVES-E2B-Danger-Room": {"upstream": "e2b-dev/E2B"},
    "PMOVES-A2UI": {"upstream": "google/A2UI"},
    "Pmoves-Health-wger": {"upstream": "wger-project/wger"},
    "PMOVES-E2b-Spells": {"upstream": "e2b-dev/e2b-cookbook"},
    "PMOVES-E2B-Danger-Room-Desktop": {"upstream": "e2b-dev/desktop"},
    "PMOVES-FinceptTerminal": {"upstream": "Fincept-Corporation/FinceptTerminal"},
    "PMOVES-Agent-Zero": {"upstream": "agent0ai/agent-zero"},
    "PMOVES-BotZ-gateway": {"upstream": "microsoft/mcp-gateway"},
    "Pmoves-hyperdimensions": {"upstream": "MaxRobinsonTheGreat/hyperdimensions"},
    "PMOVES-llama-throughput-lab": {"upstream": "alexziskind1/llama-throughput-lab"},
    "PMOVES-Pinokio-Ultimate-TTS-Studio": {"upstream": "pinokiofactory/Ultimate-TTS-Studio"},
    "pmoves-e2b-mcp-server": {"upstream": "e2b-dev/mcp-server"},
    "PMOVES-ClawRouter": {"upstream": "BlockRunAI/ClawRouter"},
    "PMOVES-AgentGym": {"upstream": "WooooDyy/AgentGym"},
    "PMOVES-autoresearch": {"upstream": "karpathy/autoresearch", "skip": "synced"},
    "LMRL-Gym": {"upstream": "eric-mitchell/lmrl-gym", "skip": "synced"},
    "PMOVES-MiniMax-MCP": {"upstream": "MiniMax-AI/minimax-mcp", "skip": "synced"},
    "PMOVES-mike": {"upstream": "mike-engel/mike", "skip": "synced"},
}

ORG = "POWERFULMOVES"


# ── gh CLI wrappers ──────────────────────────────────────────────────────────


def _gh(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    cmd = ["gh", *args]
    try:
        return subprocess.run(
            cmd, capture_output=True, text=True, check=check, timeout=60,
        )
    except FileNotFoundError:
        print(f"{RED}Error: `gh` CLI not found. Install it first.{RESET}", file=sys.stderr)
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print(f"{RED}Error: gh command timed out: {' '.join(cmd)}{RESET}", file=sys.stderr)
        sys.exit(1)


def _gh_json(*args: str) -> Any:
    result = _gh(*args, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"gh failed (rc={result.returncode}): {result.stderr.strip()}")
    out = result.stdout.strip()
    if not out:
        raise RuntimeError(f"gh returned empty stdout for: {' '.join(args)}")
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return out


def _gh_api_get(endpoint: str, **jq: str) -> Any:
    args = ["api", endpoint]
    if jq:
        for flag, expr in jq.items():
            args.extend(["--jq", expr])
    return _gh_json(*args)


def _gh_api_post(endpoint: str, fields: dict[str, str] | None = None) -> dict[str, Any]:
    args = ["api", "-X", "POST", endpoint]
    if fields:
        for k, v in fields.items():
            args.extend(["-f", f"{k}={v}"])
    result = _gh(*args, check=False)
    if result.returncode != 0:
        return {"_error": True, "message": result.stderr.strip()}
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"_error": True, "message": result.stdout.strip()}


def _gh_api_delete(endpoint: str) -> bool:
    result = _gh("api", "-X", "DELETE", endpoint, check=False)
    return result.returncode == 0


# ── Helpers ──────────────────────────────────────────────────────────────────


def _get_default_branch(repo_full: str) -> str:
    return _gh_api_get(f"repos/{repo_full}", jq=".default_branch")


def _get_compare(upstream_full: str, upstream_branch: str, fork_branch_full: str) -> dict[str, int]:
    endpoint = f"repos/{upstream_full}/compare/{upstream_branch}...{fork_branch_full}"
    try:
        data = _gh_api_get(endpoint)
        return {"behind": data.get("behind_by", 0), "ahead": data.get("ahead_by", 0)}
    except RuntimeError:
        return {"behind": -1, "ahead": -1}


def _get_ref_sha(repo: str, ref: str) -> str | None:
    try:
        return _gh_api_get(f"repos/{ORG}/{repo}/git/ref/refs/heads/{ref}", jq=".object.sha")
    except RuntimeError:
        return None


def _create_branch(repo: str, branch: str, sha: str) -> bool:
    result = _gh_api_post(f"repos/{ORG}/{repo}/git/refs", fields={"ref": f"refs/heads/{branch}", "sha": sha})
    return "_error" not in result


def _delete_branch(repo: str, branch: str) -> bool:
    return _gh_api_delete(f"repos/{ORG}/{repo}/git/refs/heads/{branch}")


def _find_existing_sync_pr(repo: str) -> dict[str, Any] | None:
    try:
        prs = _gh_api_get(
            f"repos/{ORG}/{repo}/pulls",
            jq='[.[] | select(.head.ref | startswith("sync/")) | {number, title, state, html_url}]',
        )
        if isinstance(prs, list) and prs:
            return prs[0]
        return None
    except RuntimeError:
        return None


def _create_merge_commit(repo: str, base_branch: str, upstream_owner: str, upstream_branch: str) -> dict[str, Any]:
    head = f"{upstream_owner}:{upstream_branch}"
    return _gh_api_post(f"repos/{ORG}/{repo}/merges", fields={"base": base_branch, "head": head})


def _create_pr(repo: str, title: str, head: str, base: str, body: str) -> dict[str, Any]:
    return _gh_api_post(f"repos/{ORG}/{repo}/pulls", fields={"title": title, "head": head, "base": base, "body": body})


def _rate_limit_sleep() -> None:
    time.sleep(2)


def _handle_rate_limit(result: subprocess.CompletedProcess[str]) -> bool:
    if result.returncode == 403 or "rate limit" in result.stderr.lower():
        reset_match = None
        try:
            data = json.loads(result.stderr)
            reset_match = data.get("message", "")
        except (json.JSONDecodeError, TypeError):
            pass
        wait = 60
        if reset_match and "reset in" in reset_match:
            import re
            m = re.search(r"reset in (\d+)", reset_match)
            if m:
                wait = int(m.group(1)) + 5
        print(f"  {YELLOW}Rate limited. Waiting {wait}s...{RESET}", file=sys.stderr)
        time.sleep(wait)
        return True
    return False


# ── Commands ─────────────────────────────────────────────────────────────────


def cmd_audit(args: argparse.Namespace) -> None:
    results: list[dict[str, Any]] = []
    print(f"{BOLD}Auditing {len(FORK_CONFIG)} POWERFULMOVES forks...{RESET}")
    print()

    for fork_name, cfg in FORK_CONFIG.items():
        upstream = cfg["upstream"]
        upstream_owner, upstream_repo = upstream.split("/")
        skip_reason = cfg.get("skip")

        if "branch" in cfg:
            fork_branch = cfg["branch"]
        else:
            try:
                fork_branch = _get_default_branch(f"{ORG}/{fork_name}")
            except RuntimeError as e:
                results.append({"fork": fork_name, "upstream": upstream, "branch": "?", "behind": -1, "ahead": -1, "error": str(e), "skip": skip_reason})
                _rate_limit_sleep()
                continue

        try:
            upstream_branch = _get_default_branch(upstream)
        except RuntimeError as e:
            results.append({"fork": fork_name, "upstream": upstream, "branch": fork_branch, "behind": -1, "ahead": -1, "error": f"upstream: {e}", "skip": skip_reason})
            _rate_limit_sleep()
            continue

        fork_branch_full = f"{ORG}:{fork_name}:{fork_branch}"
        cmp = _get_compare(upstream, upstream_branch, fork_branch_full)

        results.append({"fork": fork_name, "upstream": upstream, "branch": fork_branch, "upstream_branch": upstream_branch, "behind": cmp["behind"], "ahead": cmp["ahead"], "skip": skip_reason})
        _rate_limit_sleep()

    results.sort(key=lambda r: r.get("behind", 0) if r.get("behind", 0) >= 0 else 9999, reverse=True)

    if args.json:
        print(json.dumps(results, indent=2))
        return

    col_fork, col_upstream, col_branch, col_behind, col_ahead, col_status = 38, 32, 32, 8, 8, 12
    hdr = f"{'FORK':<{col_fork}} {'UPSTREAM':<{col_upstream}} {'BRANCH':<{col_branch}} {'BEHIND':>{col_behind}} {'AHEAD':>{col_ahead}} {'STATUS':<{col_status}}"
    print(hdr)
    print("-" * len(hdr))

    for r in results:
        behind, ahead = r["behind"], r["ahead"]
        skip, error = r.get("skip"), r.get("error")
        color = _color_for(behind) if behind >= 0 else RED

        if error:
            status = f"{RED}ERROR{RESET}"
            behind_s, ahead_s = "-", "-"
        elif skip:
            status = f"{GRAY}{skip}{RESET}"
            behind_s, ahead_s = str(behind), str(ahead)
        elif behind == 0:
            status = f"{GRAY}synced{RESET}"
            behind_s = f"{GRAY}0{RESET}"
            ahead_s = str(ahead)
        else:
            behind_s = f"{color}{behind}{RESET}"
            ahead_s = str(ahead) if ahead > 0 else f"{GRAY}0{RESET}"
            if behind >= 1000:
                status = f"{RED}CRITICAL{RESET}"
            elif behind >= 100:
                status = f"{YELLOW}stale{RESET}"
            else:
                status = f"{GREEN}drift{RESET}"

        print(f"{r['fork'][:col_fork]:<{col_fork}} {r['upstream'][:col_upstream]:<{col_upstream}} {r['branch'][:col_branch]:<{col_branch}} {behind_s:>{col_behind}} {ahead_s:>{col_ahead}} {status:<{col_status}}")

    total = len(results)
    critical = sum(1 for r in results if r.get("behind", 0) >= 1000)
    stale = sum(1 for r in results if 100 <= r.get("behind", 0) < 1000)
    drift = sum(1 for r in results if 1 <= r.get("behind", 0) < 100)
    synced = sum(1 for r in results if r.get("behind", 0) == 0)
    errors = sum(1 for r in results if r.get("error"))
    print()
    print(f"{BOLD}Summary:{RESET} {total} forks | {RED}{critical} critical{RESET} | {YELLOW}{stale} stale{RESET} | {GREEN}{drift} drift{RESET} | {GRAY}{synced} synced{RESET} | {RED}{errors} errors{RESET}")


def cmd_sync(args: argparse.Namespace) -> None:
    dry_run = args.dry_run
    fork_filter = args.fork
    threshold = args.threshold
    max_forks = args.max
    candidates: list[tuple[str, dict[str, str]]] = []

    for fork_name, cfg in FORK_CONFIG.items():
        if cfg.get("skip"): continue
        if fork_filter and fork_name != fork_filter: continue
        candidates.append((fork_name, cfg))

    if not candidates:
        print(f"{YELLOW}No forks to sync.{RESET}")
        return

    if fork_filter:
        print(f"{BOLD}Syncing {fork_filter}...{RESET}")
    else:
        print(f"{BOLD}Syncing up to {max_forks} forks (threshold: {threshold})...{RESET}")
    if dry_run:
        print(f"{YELLOW}DRY RUN — no changes will be made{RESET}")
    print()

    synced_count = skipped_count = conflict_count = error_count = 0
    results: list[dict[str, Any]] = []

    for fork_name, cfg in candidates:
        if max_forks > 0 and synced_count >= max_forks:
            print(f"{YELLOW}Reached --max {max_forks} limit.{RESET}")
            break

        upstream = cfg["upstream"]
        upstream_owner, _ = upstream.split("/")

        if "branch" in cfg:
            fork_branch = cfg["branch"]
        else:
            try:
                fork_branch = _get_default_branch(f"{ORG}/{fork_name}")
            except RuntimeError as e:
                print(f"  {RED}✗ {fork_name}: cannot get default branch — {e}{RESET}")
                error_count += 1
                results.append({"fork": fork_name, "result": "error", "detail": str(e)})
                continue

        try:
            upstream_branch = _get_default_branch(upstream)
        except RuntimeError as e:
            print(f"  {RED}✗ {fork_name}: cannot get upstream branch — {e}{RESET}")
            error_count += 1
            results.append({"fork": fork_name, "result": "error", "detail": str(e)})
            continue

        fork_branch_full = f"{ORG}:{fork_name}:{fork_branch}"
        cmp = _get_compare(upstream, upstream_branch, fork_branch_full)
        behind, ahead = cmp["behind"], cmp["ahead"]

        if behind < 0:
            print(f"  {RED}✗ {fork_name}: compare API failed{RESET}")
            error_count += 1
            results.append({"fork": fork_name, "result": "error", "detail": "compare failed"})
            continue

        if behind < threshold:
            print(f"  {GRAY}⊙ {fork_name}: {behind} behind (below threshold {threshold}), skipping{RESET}")
            skipped_count += 1
            results.append({"fork": fork_name, "result": "skipped", "behind": behind})
            continue

        color = _color_for(behind)
        print(f"  {color}⟳ {fork_name}: {behind} behind, {ahead} ahead (branch: {fork_branch}){RESET}")

        existing_pr = _find_existing_sync_pr(fork_name)
        if existing_pr:
            print(f"    {YELLOW}⊙ Open sync PR exists: #{existing_pr['number']} — {existing_pr['html_url']}{RESET}")
            skipped_count += 1
            results.append({"fork": fork_name, "result": "skipped", "detail": f"existing PR #{existing_pr['number']}"})
            _rate_limit_sleep()
            continue

        if dry_run:
            print(f"    {GRAY}[dry-run] Would create sync/upstream-{date.today()} branch, merge upstream, open PR{RESET}")
            synced_count += 1
            results.append({"fork": fork_name, "result": "dry-run", "behind": behind, "ahead": ahead})
            _rate_limit_sleep()
            continue

        sha = _get_ref_sha(fork_name, fork_branch)
        if not sha:
            print(f"    {RED}✗ Cannot resolve SHA for {fork_branch}{RESET}")
            error_count += 1
            results.append({"fork": fork_name, "result": "error", "detail": "cannot resolve SHA"})
            continue

        sync_branch = f"sync/upstream-{date.today()}"
        if not _create_branch(fork_name, sync_branch, sha):
            print(f"    {RED}✗ Failed to create branch {sync_branch}{RESET}")
            error_count += 1
            results.append({"fork": fork_name, "result": "error", "detail": "branch creation failed"})
            continue
        print(f"    {GREEN}✓ Branch {sync_branch} created{RESET}")

        merge_result = _create_merge_commit(fork_name, sync_branch, upstream_owner, upstream_branch)
        if "_error" in merge_result:
            msg = merge_result.get("message", "unknown error")
            if "Conflict" in msg or "merge conflict" in msg.lower():
                print(f"    {YELLOW}⚠ Merge conflict — cleaning up branch{RESET}")
                _delete_branch(fork_name, sync_branch)
                conflict_count += 1
                results.append({"fork": fork_name, "result": "conflict", "behind": behind})
            else:
                print(f"    {RED}✗ Merge failed: {msg}{RESET}")
                _delete_branch(fork_name, sync_branch)
                error_count += 1
                results.append({"fork": fork_name, "result": "error", "detail": msg})
            continue

        print(f"    {GREEN}✓ Merge commit created{RESET}")

        pr_title = f"chore: sync upstream ({behind} commits behind)"
        pr_body = (
            f"## Upstream Sync\n\n"
            f"- **Upstream**: `{upstream}` (`{upstream_branch}`)\n"
            f"- **Behind**: {behind} commits\n"
            f"- **Ahead**: {ahead} commits (PMOVES customizations)\n"
            f"- **Branch**: `{fork_branch}` → `{sync_branch}`\n\n"
            f"This PR merges upstream changes into the PMOVES fork. "
            f"Review the diff to confirm PMOVES customizations are preserved.\n\n"
            f"---\n*Automated by `pmoves.tools.fork_sync`*"
        )
        pr_result = _create_pr(fork_name, pr_title, sync_branch, fork_branch, pr_body)

        if "_error" in pr_result:
            print(f"    {RED}✗ PR creation failed: {pr_result.get('message', 'unknown')}{RESET}")
            _delete_branch(fork_name, sync_branch)
            error_count += 1
            results.append({"fork": fork_name, "result": "error", "detail": "PR creation failed"})
            continue

        pr_url = pr_result.get("html_url", "?")
        pr_num = pr_result.get("number", "?")
        print(f"    {GREEN}✓ PR #{pr_num}: {pr_url}{RESET}")
        synced_count += 1
        results.append({"fork": fork_name, "result": "synced", "pr": pr_num, "url": pr_url, "behind": behind, "ahead": ahead})
        _rate_limit_sleep()

    print()
    print(f"{BOLD}Sync complete:{RESET} {GREEN}{synced_count} synced{RESET} | {YELLOW}{skipped_count} skipped{RESET} | {YELLOW}{conflict_count} conflicts{RESET} | {RED}{error_count} errors{RESET}")
    if not args.json:
        return
    print(json.dumps(results, indent=2))


def cmd_status(args: argparse.Namespace) -> None:
    print(f"{BOLD}Checking sync PR status across all forks...{RESET}")
    print()
    any_found = False
    for fork_name, cfg in FORK_CONFIG.items():
        if cfg.get("skip"): continue
        prs = _find_existing_sync_pr(fork_name)
        if prs is None:
            try:
                closed = _gh_api_get(
                    f"repos/{ORG}/{fork_name}/pulls?state=closed&per_page=5",
                    jq='[.[] | select(.head.ref | startswith("sync/")) | {number, title, state, merged_at, html_url}]',
                )
                if isinstance(closed, list) and closed:
                    for pr in closed:
                        merged = "merged" if pr.get("merged_at") else "closed"
                        color = GREEN if pr.get("merged_at") else YELLOW
                        print(f"  {fork_name}: {color}{merged}{RESET} PR #{pr['number']} — {pr['html_url']}")
                        any_found = True
            except RuntimeError:
                pass
            _rate_limit_sleep()
            continue
        any_found = True
        state = prs.get("state", "unknown")
        color = GREEN if state == "open" else YELLOW
        print(f"  {fork_name}: {color}{state.upper()}{RESET} PR #{prs['number']} — {prs['html_url']}")
        _rate_limit_sleep()
    if not any_found:
        print(f"  {GRAY}No sync PRs found.{RESET}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fork-sync automation for PMOVES.AI monorepo")
    sub = parser.add_subparsers(dest="command", required=True)

    p_audit = sub.add_parser("audit", help="Audit fork drift from upstream")
    p_audit.add_argument("--json", action="store_true", help="Output JSON")

    p_sync = sub.add_parser("sync", help="Sync forks from upstream")
    p_sync.add_argument("--dry-run", action="store_true", help="Preview without changes")
    p_sync.add_argument("--fork", type=str, default=None, help="Sync a specific fork by name")
    p_sync.add_argument("--threshold", type=int, default=1, help="Min behind count to sync (default: 1)")
    p_sync.add_argument("--max", type=int, default=0, help="Max forks to sync (0 = unlimited)")
    p_sync.add_argument("--json", action="store_true", help="Output JSON")

    sub.add_parser("status", help="Check sync PR status")

    args = parser.parse_args()
    if args.command == "audit":
        cmd_audit(args)
    elif args.command == "sync":
        cmd_sync(args)
    elif args.command == "status":
        cmd_status(args)


if __name__ == "__main__":
    main()
