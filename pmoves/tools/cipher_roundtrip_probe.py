#!/usr/bin/env python3
"""Can this session WRITE a memory and READ IT BACK, authenticated, as itself?

WHY THIS EXISTS
---------------
`cipher_preflight.py` answers "is the endpoint reachable and does it accept my
bearer?" -- it reads the status line of `/mcp/sse` and stops. `cipher_identity.py`
answers "which agent_id will my writes be filed under?" without touching the
network. Neither one stores anything, so neither can tell you that memory
actually works: a 200 on the SSE handshake says nothing about whether a write
persists, whether it can be read back, or whether the vector path is live.

`make -C pmoves cipher-memory-smoke` was the only write->read check, and under
token enforcement it could not pass. It sent no `Authorization` header, and it
wrote as agentId `cipher-memory-smoke` -- an identity no token resolves to, so
even with a bearer every call was 403 (`assertAgentId`, memory-routes.ts:13-27).
Behind `curl -sf` both surfaced as `POST FAILED:` with an empty message.

This probe does the round trip the way a real client does:

    POST   /api/memory            write a unique marker as the token's agent
    GET    /api/memory/{id}       read it back by id; content must match
    GET    /api/memory/search     find it again by query, scoped to the agent
    DELETE /api/memory/{id}       clean up (skip with --keep)

THE CREDENTIAL AND THE IDENTITY COME FROM THE SAME PLACES THE SESSION USES
--------------------------------------------------------------------------
The bearer is read from the environment `cipher_preflight.layered_environ()`
builds -- process env with pmoves/env.shared over it, exactly as the launcher
sources it -- so this probe authenticates the way the session will, and from a
named VARIABLE, never argv. The agentId is the one auth.ts will accept for that
bearer (`cipher_identity.classify_token`): a non-`cipher_` token is always
`bootstrap`; a minted `cipher_` token is the session's resolved identity. Pass
`--agent` to override.

NEVER LOG THE CREDENTIAL. The token goes onto the request and nowhere else.

Exit codes (same vocabulary as cipher_preflight.py):
  0  round trip complete -- written, read back, found by search
  1  findings -- cipher ANSWERED but the round trip did not hold (401/403,
     read-back mismatch, search miss, or --require-vector and the vector path
     is dead)
  3  could not measure -- unreachable, no identity to write as, or a crash.
     NOT a pass
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Tuple

_tools_dir = Path(__file__).resolve().parent
if str(_tools_dir) not in sys.path:
    sys.path.insert(0, str(_tools_dir))

import cipher_identity as ci  # noqa: E402
import cipher_preflight as cp  # noqa: E402

DEFAULT_TOKEN_ENV = cp.DEFAULT_TOKEN_ENV
TIMEOUT = 30.0
# Written content is prefixed so a probe record is recognisable if --keep (or a
# failed DELETE) leaves one behind.
MARKER = "cipher-roundtrip-probe"
# Advisory mode (no bearer): the server takes the agentId on trust, so any
# stable name works. It is NOT used when a token is present.
ADVISORY_AGENT = MARKER


def default_base_url(environ: Mapping[str, str]) -> str:
    return f"http://localhost:{environ.get('CIPHER_PORT') or '8105'}"


def _urlopen(req: urllib.request.Request, timeout: float):
    """The single network seam. Tests patch this.

    Delegates to cipher_preflight's opener, which refuses redirects: the request
    carries a bearer and urllib would forward it to any Location.
    """
    return cp._urlopen(req, timeout)


def resolve_agent(
    explicit: Optional[str], token: Optional[str], environ: Mapping[str, str]
) -> Tuple[str, str]:
    """``(agent_id, why)`` -- the agentId auth.ts will accept for this bearer.

    Returns an empty agent_id when there is nothing honest to write as.
    """
    if explicit:
        return explicit, "--agent"
    mode = ci.classify_token(token)
    if mode == ci.MODE_BOOTSTRAP:
        return ci.BOOTSTRAP_AGENT, "single-token bearer resolves to 'bootstrap' (auth.ts)"
    if mode == ci.MODE_PER_AGENT:
        agent = (
            environ.get("PMOVES_RESOLVED_IDENTITY")
            or environ.get("PMOVES_NODE_IDENTITY")
            or ""
        ).strip()
        if agent:
            return agent, "minted bearer + session identity"
        return "", (
            "minted bearer but no session identity (PMOVES_RESOLVED_IDENTITY / "
            "PMOVES_NODE_IDENTITY unset) -- pass --agent <signing-card agent_id>"
        )
    return ADVISORY_AGENT, "no bearer: advisory mode, agentId self-declared"


def _call(
    method: str,
    url: str,
    token: Optional[str],
    body: Optional[Dict[str, Any]] = None,
    timeout: float = TIMEOUT,
) -> Tuple[Optional[int], Any, Optional[str]]:
    """``(status, parsed_json_or_None, error)``. Never raises for HTTP/network failure.

    ``status is None`` means nothing answered. The error text carries the
    server's own ``error`` field (e.g. the 403 identity mismatch) and never a
    header value.
    """
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with _urlopen(req, timeout) as resp:
            raw = resp.read()
            payload = json.loads(raw.decode("utf-8")) if raw else None
            return resp.status, payload, None
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            parsed = json.loads(exc.read().decode("utf-8"))
            if isinstance(parsed, dict) and isinstance(parsed.get("error"), str):
                detail = ": " + parsed["error"][:200]
        except Exception:  # noqa: BLE001 - a non-JSON error body is still an HTTP status
            pass
        return exc.code, None, f"HTTP {exc.code}{detail}"
    except (urllib.error.URLError, socket.timeout, TimeoutError, OSError) as exc:
        return None, None, str(getattr(exc, "reason", exc))
    except ValueError:
        # Deliberately NOT interpolated: http.client names a rejected header
        # value -- the credential -- in this message.
        return None, None, "request rejected before send -- detail withheld"


def _fail(row: Dict[str, Any], step: str, status: Optional[int], error: Optional[str]) -> Dict[str, Any]:
    row["failed_step"] = step
    row["error"] = error
    if status is None:
        row["verdict"] = "unreachable"
    elif status in (401, 403):
        row["verdict"] = "unauthorized"
    else:
        row["verdict"] = "http_error"
    return row


def roundtrip(
    base_url: str,
    agent: str,
    token: Optional[str],
    require_vector: bool = False,
    keep: bool = False,
) -> Dict[str, Any]:
    """Run the round trip. Returns a result row; never contains the token."""
    base = base_url.rstrip("/")
    content = f"{MARKER} {uuid.uuid4().hex}"
    row: Dict[str, Any] = {
        "base_url": base,
        "agent": agent,
        "auth": "presented" if token else "none",
        "verdict": "ok",
        "failed_step": None,
        "error": None,
        "id": None,
        "embedded": None,
        "vector_hit": None,
        "cleaned_up": None,
    }

    status, created, err = _call(
        "POST", f"{base}/api/memory", token,
        {"content": content, "category": "test", "tags": ["smoke", "roundtrip"], "agentId": agent},
    )
    if status is None or status >= 300:
        return _fail(row, "write", status, err)
    if not isinstance(created, dict) or not created.get("id"):
        row.update(verdict="http_error", failed_step="write", error="write answered without an id")
        return row
    mem_id = str(created["id"])
    row["id"] = mem_id
    row["embedded"] = created.get("embedding_id") is not None

    try:
        status, got, err = _call("GET", f"{base}/api/memory/{urllib.parse.quote(mem_id, safe='')}", token)
        if status is None or status >= 300:
            return _fail(row, "read", status, err)
        if not isinstance(got, dict) or got.get("content") != content:
            row.update(verdict="readback_mismatch", failed_step="read",
                       error="record read back by id does not carry the written content")
            return row

        query = urllib.parse.urlencode({"q": content, "limit": 5, "agentId": agent})
        status, found, err = _call("GET", f"{base}/api/memory/search?{query}", token)
        if status is None or status >= 300:
            return _fail(row, "search", status, err)
        results = (found or {}).get("results") if isinstance(found, dict) else None
        hit = next((r for r in results or [] if isinstance(r, dict) and r.get("id") == mem_id), None)
        if hit is None:
            row.update(verdict="search_miss", failed_step="search",
                       error=f"search for the written content as '{agent}' did not return it")
            return row
        # memory-routes.ts sets `score` only on Qdrant hits; lexicalFallback()
        # results carry none. embedding_id is null unless the embed succeeded.
        row["vector_hit"] = "score" in hit
        if require_vector and not (row["embedded"] and row["vector_hit"]):
            row.update(verdict="vector_path_dead", failed_step="search", error=(
                "round trip held only through the lexical fallback "
                f"(embedded={row['embedded']}, vector_hit={row['vector_hit']}); "
                "embedded=False means sidecar.embed() failed -- check TENSORZERO_URL / "
                "OLLAMA_URL is reachable FROM the cipher container; vector_hit=False "
                "with embedded=True means the collection is missing -- provision with "
                "make -C pmoves qdrant-provision-cipher"
            ))
        return row
    finally:
        if not keep:
            q = urllib.parse.urlencode({"agentId": agent})
            status, _, _ = _call(
                "DELETE", f"{base}/api/memory/{urllib.parse.quote(mem_id, safe='')}?{q}", token
            )
            row["cleaned_up"] = status is not None and status < 300


def exit_code(row: Dict[str, Any]) -> int:
    if row["verdict"] == "ok":
        return 0
    if row["verdict"] in ("unreachable", "no_identity", "unmeasured"):
        return 3
    return 1


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-url", default=None,
                        help="cipher HTTP base (default http://localhost:$CIPHER_PORT, 8105)")
    parser.add_argument("--agent", default=None,
                        help="agentId to write as (default: what auth.ts accepts for the bearer)")
    parser.add_argument("--token-env", default=DEFAULT_TOKEN_ENV,
                        help="variable holding the bearer; '' probes anonymously. Never the token itself")
    parser.add_argument("--env-file", type=Path, default=None)
    parser.add_argument("--no-env-file", action="store_false", dest="use_env_file")
    parser.add_argument("--require-vector", action="store_true",
                        help="fail when the round trip only held through the lexical fallback")
    parser.add_argument("--keep", action="store_true", help="do not DELETE the probe record")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    try:
        if args.use_env_file:
            environ, note = cp.layered_environ(args.env_file)
            if note:
                print(f"[cipher-roundtrip] {note}", file=sys.stderr)
        else:
            environ = dict(os.environ)
        token = (environ.get(args.token_env) or "").strip() if args.token_env else ""
        if token and not cp._header_safe([token]):
            row = {"verdict": "unmeasured", "error": "credential contains CR/LF -- value withheld"}
        else:
            agent, why = resolve_agent(args.agent, token or None, environ)
            if not agent:
                row = {"verdict": "no_identity", "error": why}
            else:
                row = roundtrip(args.base_url or default_base_url(environ), agent,
                                token or None, args.require_vector, args.keep)
                row["agent_source"] = why
    except Exception as exc:  # noqa: BLE001 - a crash is COULD-NOT-MEASURE, never a pass
        row = {"verdict": "unmeasured", "error": f"probe crashed ({type(exc).__name__})"}

    if args.as_json:
        print(json.dumps(row, indent=2, sort_keys=True))
    elif row["verdict"] == "ok":
        print(f"cipher round trip OK as '{row['agent']}' at {row['base_url']} "
              f"(embedded={row['embedded']}, vector_hit={row['vector_hit']}, "
              f"cleaned_up={row['cleaned_up']})")
    else:
        step = f" at {row['failed_step']}" if row.get("failed_step") else ""
        print(f"cipher round trip FAILED{step}: {row['verdict']} -- {row.get('error')}",
              file=sys.stderr)
    return exit_code(row)


if __name__ == "__main__":
    sys.exit(main())
