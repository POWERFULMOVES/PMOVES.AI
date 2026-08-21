#!/usr/bin/env python3
"""Prove the PMOVES MCP Gateway actually federates — not just that a port answers.

Why this is not a health check
------------------------------
An open port proves a process is listening. It does not prove the gateway
reached the servers behind it. The failure this repo keeps finding is exactly
that gap: `github-issue-triage` depends on `botz-gateway` with
`condition: service_healthy`, that dependency genuinely resolves, and every MCP
call behind it still 404s on the wrong port and a route that does not exist.

So this asks the gateway for its tool list and checks that tools from EACH
catalogued server are present. A gateway that started but federated nothing
answers `tools/list` perfectly happily with an empty list.

Usage:
  python pmoves/tools/mcp_gateway_verify.py
  python pmoves/tools/mcp_gateway_verify.py --json
  python pmoves/tools/mcp_gateway_verify.py --url http://host:8091/mcp

Exit codes:
  0  every catalogued server contributed at least one tool
  1  the gateway answered but a server contributed nothing
  3  the gateway could not be reached — NOT a pass
  4  usage / catalog parse error
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOG = REPO_ROOT / "pmoves" / "config" / "mcp-gateway" / "catalog.yaml"
DEFAULT_URL = os.environ.get(
    "MCP_GATEWAY_URL", f"http://localhost:{os.environ.get('MCP_GATEWAY_PORT', '8091')}/mcp"
)

# Tool-name prefixes each catalogued server is expected to contribute. Derived
# from what the servers actually advertise, probed directly:
#   botz-mcp-bridge  23 tools: hirag_*, nats_*, tensorzero_*, supabase_*, cast_*
#   cipher           persistent-memory tools
EXPECTED_PREFIXES: Dict[str, List[str]] = {
    "botz-mcp-bridge": ["hirag_", "nats_", "tensorzero_", "supabase_", "cast_"],
    "cipher": ["cipher", "memory", "ask_", "search"],
}


class Unreachable(RuntimeError):
    """The gateway could not be consulted, so no verdict is possible."""


def load_catalog_servers() -> List[str]:
    try:
        import yaml  # noqa: PLC0415
    except ImportError:
        # Stdlib-only fallback: the catalog's server names are the top-level
        # keys under `registry:`, two spaces in.
        names, in_registry = [], False
        for line in CATALOG.read_text(encoding="utf-8").splitlines():
            if line.startswith("registry:"):
                in_registry = True
                continue
            if in_registry and line and not line.startswith((" ", "#")):
                break
            if in_registry and line.startswith("  ") and not line.startswith("   ") \
               and line.strip().endswith(":") and not line.strip().startswith("#"):
                names.append(line.strip().rstrip(":"))
        return names
    data = yaml.safe_load(CATALOG.read_text(encoding="utf-8")) or {}
    return sorted((data.get("registry") or {}).keys())


def list_tools(url: str, token: Optional[str]) -> List[dict]:
    payload = json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
    ).encode("utf-8")
    request = urllib.request.Request(url, data=payload, method="POST")
    request.add_header("Content-Type", "application/json")
    request.add_header("Accept", "application/json, text/event-stream")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raise Unreachable(f"{url}: HTTP {exc.code} {exc.reason}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise Unreachable(f"{url}: {exc}") from exc

    # streaming transport may answer as SSE; take the last data: line.
    if body.lstrip().startswith("event:") or "\ndata:" in body:
        chunks = [l[5:].strip() for l in body.splitlines() if l.startswith("data:")]
        body = chunks[-1] if chunks else body
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError as exc:
        raise Unreachable(f"{url}: response is not JSON: {body[:160]!r}") from exc
    if "error" in parsed:
        raise Unreachable(f"{url}: gateway returned error: {parsed['error']}")
    return (parsed.get("result") or {}).get("tools") or []


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if not CATALOG.is_file():
        print(f"[error] catalog not found at {CATALOG}", file=sys.stderr)
        return 4
    servers = load_catalog_servers()
    if not servers:
        print("[error] catalog declares no servers", file=sys.stderr)
        return 4

    token = os.environ.get("MCP_GATEWAY_AUTH_TOKEN")
    try:
        tools = list_tools(args.url, token)
    except Unreachable as exc:
        print(f"[unmeasured] {exc}", file=sys.stderr)
        print("[unmeasured] no verdict reached — this is not a pass", file=sys.stderr)
        if args.json:
            print(json.dumps({"status": "unmeasured", "detail": str(exc)}, indent=2))
        return 3

    names = [t.get("name", "") for t in tools]
    per_server = {}
    for server in servers:
        prefixes = EXPECTED_PREFIXES.get(server, [server.replace("-", "_")])
        per_server[server] = [n for n in names if any(n.startswith(p) or p in n for p in prefixes)]

    silent = [s for s, found in per_server.items() if not found]

    if args.json:
        print(json.dumps({
            "status": "fail" if silent else "pass",
            "url": args.url,
            "total_tools": len(names),
            "per_server": {s: len(v) for s, v in per_server.items()},
            "servers_contributing_nothing": silent,
        }, indent=2))
        return 1 if silent else 0

    print(f"MCP Gateway {args.url}: {len(names)} tool(s) across {len(servers)} catalogued server(s)")
    for server, found in per_server.items():
        mark = "ok   " if found else "EMPTY"
        print(f"  [{mark}] {server}: {len(found)} tool(s)"
              + (f"  e.g. {', '.join(found[:3])}" if found else ""))
    if silent:
        print(f"\nFAILED: {len(silent)} catalogued server(s) contributed no tools: "
              f"{', '.join(silent)}\n"
              f"  The gateway is up but is not federating them. Check the catalog URL,\n"
              f"  and that the gateway shares a network with that server.")
        return 1
    print("\nPASS: every catalogued server is federated through the gateway.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
