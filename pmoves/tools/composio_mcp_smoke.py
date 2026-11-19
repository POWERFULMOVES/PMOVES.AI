#!/usr/bin/env python3
"""Smoke the Composio MCP fleet proxy: MCP initialize + tools/list, print tool count.

The proxy (deploy/kvm2/composio-mcp/) is supergateway 4.2.0 re-serving the
hosted Composio Connect MCP server over streamable HTTP. A container that is
"healthy" only proves the gateway process is up: its /healthz deliberately does
not dial Composio. This proves the whole path -- caller -> gateway key ->
proxy -> x-consumer-api-key -> Connect -> tool list.

Secrets: the gateway key is read from the environment variable named by
--key-env (default COMPOSIO_MCP_GATEWAY_KEY) and sent as a Bearer header. It is
never printed, logged, or put in an error message; neither is any response
header.

Usage:
  python3 pmoves/tools/composio_mcp_smoke.py
  python3 pmoves/tools/composio_mcp_smoke.py --url http://127.0.0.1:8190/composio/mcp --json

Exit codes (repo doctrine):
  0  handshake completed and at least one tool listed
  1  the proxy answered but the result is wrong (upstream refused, zero tools)
  3  could not measure (proxy unreachable, gateway key missing) -- NOT a pass
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import List, Optional, Tuple

DEFAULT_URL = os.environ.get(
    "COMPOSIO_MCP_SMOKE_URL",
    f"http://127.0.0.1:{os.environ.get('COMPOSIO_MCP_PORT', '8190')}/composio/mcp",
)
PROTOCOL_VERSION = "2025-06-18"


class Unmeasured(RuntimeError):
    """No verdict is possible (exit 3)."""


class Finding(RuntimeError):
    """The proxy answered, and the answer is wrong (exit 1)."""


def _parse_body(body: str) -> Optional[dict]:
    """Parse a streamable-HTTP reply: plain JSON or SSE framing (last data: line)."""
    if not body.strip():
        return None
    text = body
    if body.lstrip().startswith(("event:", "data:", "id:")) or "\ndata:" in body:
        chunks = [line[5:].strip() for line in body.splitlines() if line.startswith("data:")]
        chunks = [c for c in chunks if c]
        if not chunks:
            return None
        text = chunks[-1]
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise Finding(f"response is not JSON ({len(text)} bytes)") from exc
    return parsed if isinstance(parsed, dict) else None


def _post(url: str, key: str, payload: dict, session: Optional[str]) -> Tuple[Optional[dict], Optional[str]]:
    request = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), method="POST")
    request.add_header("Content-Type", "application/json")
    request.add_header("Accept", "application/json, text/event-stream")
    request.add_header("Authorization", f"Bearer {key}")
    request.add_header("MCP-Protocol-Version", PROTOCOL_VERSION)
    if session:
        request.add_header("Mcp-Session-Id", session)
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            body = response.read().decode("utf-8", errors="replace")
            sid = response.headers.get("Mcp-Session-Id") or session
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            raise Finding(
                "HTTP 401 from the proxy: the gateway key was refused "
                "(COMPOSIO_MCP_GATEWAY_KEY differs from the proxy's env file)"
            ) from exc
        raise Finding(f"HTTP {exc.code} {exc.reason} from the proxy") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        reason = getattr(exc, "reason", exc)
        raise Unmeasured(f"proxy unreachable at {url}: {reason}") from exc
    parsed = _parse_body(body)
    if parsed and "error" in parsed:
        err = parsed["error"] or {}
        message = str(err.get("message", ""))[:200] if isinstance(err, dict) else str(err)[:200]
        # supergateway reports an upstream refusal as "MCP server process
        # failed"; the cause is in the container log. Measured 2026-10-21 with a
        # dummy ck_ key: Connect answers 401 "Authorization required".
        raise Finding(
            f"JSON-RPC error from upstream via proxy: {message} -- if Connect refused "
            "the consumer key, `docker logs pmoves-composio-mcp` shows "
            "'Authorization required'; check COMPOSIO_MCP_CONSUMER_KEY (ck_*) in the proxy env file"
        )
    return parsed, sid


def list_tools(url: str, key: str) -> Tuple[dict, List[dict]]:
    """initialize -> notifications/initialized -> tools/list (following nextCursor)."""
    init, session = _post(url, key, {
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "pmoves-composio-mcp-smoke", "version": "1.0.0"},
        },
    }, None)
    if not init or "result" not in init:
        raise Finding("initialize returned no result")
    _post(url, key, {"jsonrpc": "2.0", "method": "notifications/initialized"}, session)
    tools: List[dict] = []
    cursor: Optional[str] = None
    for page in range(20):
        params = {"cursor": cursor} if cursor else {}
        reply, session = _post(url, key, {"jsonrpc": "2.0", "id": 2 + page,
                                          "method": "tools/list", "params": params}, session)
        result = (reply or {}).get("result") or {}
        tools.extend(result.get("tools") or [])
        cursor = result.get("nextCursor")
        if not cursor:
            break
    return init["result"], tools


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--key-env", default="COMPOSIO_MCP_GATEWAY_KEY",
                        help="environment variable holding the proxy's gateway key")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    def report(status: str, detail: str, code: int, **extra) -> int:
        if args.json:
            print(json.dumps({"status": status, "url": args.url, "detail": detail, **extra}, indent=2))
        else:
            print(f"[{status}] {detail}", file=sys.stderr if code else sys.stdout)
        return code

    key = os.environ.get(args.key_env, "")
    if not key:
        return report("unmeasured", f"{args.key_env} is not set -- no verdict, this is not a pass", 3)
    try:
        server, tools = list_tools(args.url, key)
    except Unmeasured as exc:
        return report("unmeasured", f"{exc} -- this is not a pass", 3)
    except Finding as exc:
        return report("fail", str(exc), 1)

    names = sorted(t.get("name", "") for t in tools)
    info = server.get("serverInfo") or {}
    if not names:
        return report("fail", "handshake ok but tools/list is empty", 1,
                      server=info.get("name"), tool_count=0)
    if args.json:
        print(json.dumps({"status": "pass", "url": args.url, "server": info.get("name"),
                          "protocol": server.get("protocolVersion"),
                          "tool_count": len(names), "tools": names}, indent=2))
    else:
        print(f"Composio MCP proxy {args.url}: server={info.get('name')!s} "
              f"protocol={server.get('protocolVersion')!s} tools={len(names)}")
        for name in names:
            print(f"  - {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
