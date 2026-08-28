#!/usr/bin/env python3
"""Is persistent memory actually reachable for this session?

WHY THIS EXISTS
---------------
Cipher is a startup REQUIREMENT, not a nice-to-have: without it an agent runs
with no persistent memory and does not know that it is. The failure is silent by
construction — an MCP server that never connects simply contributes no tools, so
the session looks normal and every recalled fact is missing.

`.claude/mcp.json` carries TWO cipher entries, and which one answers matters:

    pmoves-cipher        http://${TS_Z890}:8105/mcp/sse   the Z890 node
    pmoves-cipher-local  http://localhost:8105/mcp/sse    this node

#2792 added the local entry precisely because the roster had carried only the
fleet one — "memory that silently wasn't there" when Z890 was unreachable. This
tool reports WHICH endpoint answered, so "memory is up" never quietly means
"someone else's memory is up".

SSE is why this cannot be a naive health check
----------------------------------------------
`/mcp/sse` is a Server-Sent Events stream: the response headers arrive at once
and the body NEVER closes. A check that waits for the request to finish reads a
perfectly healthy Cipher as a timeout — measured on the 4090, a 10s budget
returned HTTP 200 after exactly 10.0s because the deadline, not the server,
ended it. So this reads the STATUS LINE and stops.

Refusing to guess
-----------------
An endpoint that cannot be resolved or reached at all is reported as such and
exits 3, not 0 — same doctrine as docker_host_policy_check.py. A probe that
says "pass" when it took no measurement is the failure mode this repo has spent
a lot of effort removing.

Usage:
  python pmoves/tools/cipher_preflight.py
  python pmoves/tools/cipher_preflight.py --json
  python pmoves/tools/cipher_preflight.py --url http://localhost:8105/mcp/sse

Exit codes:
  0  at least one cipher endpoint answered — memory is available
  1  every candidate endpoint was reached and none answered usably
  3  could not measure (no roster, nothing resolvable) — NOT a pass
"""
from __future__ import annotations

import argparse
import json
import socket
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ROSTER = _REPO_ROOT / ".claude" / "mcp.json"

# Long enough to cross the tailnet, short enough that a wedged endpoint does not
# hold up a session start. Only the status line is awaited, never the body.
CONNECT_TIMEOUT = 6.0


class Unmeasured(RuntimeError):
    """The check could not be performed. Never reported as a pass."""


def cipher_urls_from_roster(roster: Optional[Path] = None) -> List[Dict[str, str]]:
    """Every enabled cipher entry in the roster, in roster order.

    Keys starting with `_` are skipped: that is the repo's real off-switch
    (mcp_roster_normalize.py P2), and `_pmoves-cipher-legacy-python-wrapper` is
    a broken duplicate that must not be probed as though it counted.
    """
    path = roster or DEFAULT_ROSTER
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise Unmeasured(f"cannot read MCP roster {path}: {exc}") from exc

    found: List[Dict[str, str]] = []
    for name, spec in (doc.get("mcpServers") or {}).items():
        if name.startswith("_") or "cipher" not in name.lower():
            continue
        url = (spec or {}).get("url")
        if url:
            found.append({"name": name, "url": url})
    return found


def probe(url: str, timeout: float = CONNECT_TIMEOUT) -> Dict[str, Any]:
    """Reach the endpoint and read ONLY the status line.

    Returns a row describing the outcome; never raises for a reachability
    failure, because "this one is down" is a measurement.
    """
    row: Dict[str, Any] = {"url": url, "ok": False, "status": None, "error": None}
    if "${" in url:
        # An unexpanded ${TS_<NODE>} means the launcher's tailnet helper did not
        # resolve it. Claude Code would use the literal text as a hostname, so
        # this is a real "not configured", not a transient outage.
        row["error"] = "unresolved variable in URL (tailnet helper did not run?)"
        return row
    req = urllib.request.Request(url, headers={"Accept": "text/event-stream"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            row["status"] = resp.status
            row["ok"] = 200 <= resp.status < 400
    except urllib.error.HTTPError as exc:
        # A 4xx still proves something is LISTENING and speaking HTTP, which is
        # a different problem from an absent Cipher — say which.
        row["status"] = exc.code
        row["error"] = f"HTTP {exc.code}"
    except (urllib.error.URLError, socket.timeout, TimeoutError, OSError) as exc:
        row["error"] = str(getattr(exc, "reason", exc))
    return row


def check(urls: Optional[List[str]] = None, roster: Optional[Path] = None) -> Dict[str, Any]:
    if urls:
        candidates = [{"name": "--url", "url": u} for u in urls]
    else:
        candidates = cipher_urls_from_roster(roster)
        if not candidates:
            raise Unmeasured(
                "no cipher entry in the MCP roster — memory is not configured at all"
            )

    rows = []
    for cand in candidates:
        result = probe(cand["url"])
        result["name"] = cand["name"]
        rows.append(result)

    reachable = [r for r in rows if r["ok"]]
    return {
        "endpoints": rows,
        "reachable": [r["name"] for r in reachable],
        "ok": bool(reachable),
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", action="append", dest="urls")
    parser.add_argument("--roster", type=Path, default=None)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    try:
        verdict = check(args.urls, args.roster)
    except Unmeasured as exc:
        if args.as_json:
            print(json.dumps({"measured": False, "reason": str(exc)}, indent=2))
        else:
            print(f"UNMEASURED: {exc}", file=sys.stderr)
            print("  This is NOT a pass — assume no persistent memory.", file=sys.stderr)
        return 3

    if args.as_json:
        print(json.dumps({"measured": True, **verdict}, indent=2))
        return 0 if verdict["ok"] else 1

    for row in verdict["endpoints"]:
        if row["ok"]:
            print(f"cipher OK   {row['name']}  ({row['url']}) -> {row['status']}")
        else:
            print(
                f"cipher DOWN {row['name']}  ({row['url']}) -> {row['error']}",
                file=sys.stderr,
            )
    if verdict["ok"]:
        return 0

    print(
        "No cipher endpoint answered. This session has NO persistent memory —\n"
        "  fall back to the auto-memory directory and say so rather than\n"
        "  recalling nothing silently.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
