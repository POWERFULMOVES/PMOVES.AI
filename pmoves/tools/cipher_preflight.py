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

/mcp/sse REQUIRES a bearer, so the probe must present one
---------------------------------------------------------
Measured on B850 2026-09-05 against the live container:

    GET /health                       -> 200
    GET /mcp/sse  (no Authorization)  -> 401
    GET /mcp/sse  (Bearer $TOKEN)     -> 200

Both roster entries already carry ``headers.Authorization: "Bearer
${CIPHER_API_TOKEN}"``. This tool used to read only ``url`` out of the roster
and throw the header away, so it sent no credential — against an endpoint that
requires one, the only reachable outcome was 401. Then 401 was folded into
"DOWN" and the summary said *No cipher endpoint answered*. It had answered; the
answer was 401, which is proof of life.

That is the mirror of the usual bug. Not a check that cannot fail — a check
that could not pass. Three consecutive sessions were told they had no
persistent memory while Cipher was healthy and reachable throughout.

``${VAR}`` expansion is imported from mcp_roster_normalize (P4) rather than
reimplemented, so the roster resolves the same way here as it does on the path
into Claude Code. Per that module's P5 split verdict, an unresolvable
*header* is announced and the probe continues anonymously — it is not fatal
the way an unresolvable *url* is.

NEVER LOG THE CREDENTIAL. Header values are consumed by the request and never
enter a result row, the JSON payload, or a message. Only variable NAMES do.

Refusing to guess
-----------------
An endpoint that cannot be resolved or reached at all is reported as such and
exits 3, not 0 — same doctrine as docker_host_policy_check.py and
mcp_toolkit_preflight.py. A probe that says "pass" when it took no measurement
is the failure mode this repo has spent a lot of effort removing.

The corollary matters just as much: a probe that says "fail, and by the way you
have no memory" when it DID take a measurement is the same sin inverted. 401 is
a measurement. It gets its own verdict and its own remedy — bind the token,
which is not the same instruction as start the service.

Usage:
  python pmoves/tools/cipher_preflight.py
  python pmoves/tools/cipher_preflight.py --json
  python pmoves/tools/cipher_preflight.py --url http://localhost:8105/mcp/sse

Exit codes:
  0  at least one cipher endpoint answered usably — memory is available
  1  findings: something ANSWERED but not usably (401 unauthorized, or another
     HTTP status). The service is up; the session's access to it is not
  3  could not measure — no roster, nothing resolvable, nothing reachable at
     all, or the check itself crashed. NOT a pass

A crash lands on 3 and not on python's own uncaught-exception 1, because the
launcher treats 1 as "it answered, the service is UP". Reporting health from a
run that took no measurement is the failure this file exists to end, and it
would be no better for the tool to commit it than for the thing it checks.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import socket
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ROSTER = _REPO_ROOT / ".claude" / "mcp.json"

# Reuse the roster expander rather than writing a second one. Divergence here
# would mean the credential resolves differently for the preflight than for the
# session it is vouching for, which is worse than no preflight.
_tools_dir = Path(__file__).resolve().parent
if str(_tools_dir) not in sys.path:
    sys.path.insert(0, str(_tools_dir))

try:
    from mcp_roster_normalize import expand as _expand_vars  # noqa: E402
except Exception as _exc:  # pragma: no cover - depends on the tree layout
    # An uncaught ImportError here aborted the module and python exits 1 on an
    # uncaught exception -- which claude-pmoves.sh reads as "findings: the
    # service is UP, do not restart it". A crash is COULD-NOT-MEASURE. Degrade
    # to a verdict the caller can act on instead of asserting health we never
    # observed. Class name only, never the message: see the ValueError handler
    # in probe() for why an exception's text is not safe to print here.
    _EXPANDER_ERROR = (
        f"cannot import mcp_roster_normalize ({type(_exc).__name__}) — the "
        "roster cannot be resolved the way the session will resolve it"
    )
    _expand_vars = None  # type: ignore[assignment]
else:
    _EXPANDER_ERROR = None

# Long enough to cross the tailnet, short enough that a wedged endpoint does not
# hold up a session start. Only the status line is awaited, never the body.
CONNECT_TIMEOUT = 6.0

# http.client refuses these in a header value -- and names the value in the
# exception. We check first so the secret never reaches that message.
_ILLEGAL_HEADER_CHARS = re.compile(r"[\r\n]")


class Unmeasured(RuntimeError):
    """The check could not be performed. Never reported as a pass."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse redirects, because this request carries a bearer token.

    urllib forwards EVERY header except content-length/content-type to the
    redirect target, including ``Authorization``, and including a target on a
    different host (see ``HTTPRedirectHandler.redirect_request`` — unlike
    ``requests``, there is no cross-host strip). Following a redirect here
    would hand the Cipher credential to whatever the Location header names.

    That vector did not exist before this probe started sending a credential,
    so it is introduced by the fix and closed in the same change. Declining is
    also the honest answer on the merits: a 3xx is not an open SSE stream, so
    "memory is available" was never established.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, msg, headers, fp)


def _urlopen(req: urllib.request.Request, timeout: float):
    """The single network seam, so redirect refusal cannot be bypassed.

    Tests patch THIS rather than `urllib.request.urlopen`: an opener-based call
    does not route through that function, so a stub on it would silently let
    the suite hit the real network — which is exactly what happened when the
    opener was first introduced.
    """
    return urllib.request.build_opener(_NoRedirect).open(req, timeout=timeout)


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

    found: List[Dict[str, Any]] = []
    for name, spec in (doc.get("mcpServers") or {}).items():
        if name.startswith("_") or "cipher" not in name.lower():
            continue
        url = (spec or {}).get("url")
        if url:
            # `headers` rides along. Dropping it here was the whole bug: the
            # roster declares the bearer /mcp/sse requires, and a probe that
            # discards it can only ever be told 401.
            headers = (spec or {}).get("headers") or {}
            found.append({"name": name, "url": url, "headers": headers})
    return found


def _resolve_headers(
    headers: Dict[str, str], environ: Optional[Mapping[str, str]] = None
) -> tuple[Dict[str, str], List[str]]:
    """Expand ``${VAR}`` in header values. Returns ``(resolved, missing_names)``.

    A header whose references did not all resolve is OMITTED rather than sent:
    transmitting the literal text ``Bearer ${CIPHER_API_TOKEN}`` would earn a
    401 that looks exactly like a wrong token and would send the operator after
    the wrong fix. Its variable NAMES are returned so the caller can say which
    one to set.

    The returned values are secret. Callers put them on the request and nowhere
    else — never into a row, a log line, or the JSON payload.
    """
    env = os.environ if environ is None else environ
    resolved: Dict[str, str] = {}
    missing: List[str] = []
    for key, raw in (headers or {}).items():
        if not isinstance(raw, str):
            continue
        misses: List[str] = []
        value = _expand_vars(raw, env, misses)
        if misses:
            missing.extend(misses)
            continue
        # RFC 7230 3.2.4: a field value excludes leading/trailing OWS. Stripping
        # is spec-correct, not a workaround, and it disposes of the common real
        # case -- a token carrying a trailing newline from an env file, a
        # `$(cat ...)`, or a CRLF paste. Left in place, http.client rejects the
        # header with a ValueError whose message embeds the SECRET verbatim.
        resolved[key] = value.strip()
    return resolved, missing


def _header_safe(values: Iterable[str]) -> bool:
    """No CR/LF left inside a header value.

    Anything still containing them after OWS stripping is either corrupt or a
    header-injection attempt. Refuse to hand it to http.client, whose
    ``ValueError('Invalid header value %r' % value)`` would print the
    credential.
    """
    return not any(_ILLEGAL_HEADER_CHARS.search(v) for v in values)


def probe(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = CONNECT_TIMEOUT,
    environ: Optional[Mapping[str, str]] = None,
) -> Dict[str, Any]:
    """Reach the endpoint, present its credential, and read ONLY the status line.

    Returns a row describing the outcome; never raises for a reachability
    failure, because "this one is down" is a measurement.

    The row records the credential's DISPOSITION (`auth`) and the NAMES of any
    variables that would not resolve (`missing_env`). It never records the
    header value.
    """
    row: Dict[str, Any] = {
        "url": url,
        "ok": False,
        "status": None,
        "error": None,
        "verdict": "unreachable",
        "auth": "none",
        "missing_env": [],
    }
    if "${" in url:
        # An unexpanded ${TS_<NODE>} means the launcher's tailnet helper did not
        # resolve it. Claude Code would use the literal text as a hostname, so
        # this is a real "not configured", not a transient outage.
        row["error"] = "unresolved variable in URL (tailnet helper did not run?)"
        row["verdict"] = "unresolved"
        return row

    sent, missing = _resolve_headers(headers or {}, environ)
    row["missing_env"] = sorted(set(missing))
    if sent:
        row["auth"] = "presented"
    elif missing:
        row["auth"] = "unresolved"

    if sent and not _header_safe(sent.values()):
        # Never build the request. http.client would raise
        # ValueError('Invalid header value %r' % value), printing the token.
        row["error"] = (
            "credential is not a valid HTTP header value (embedded CR/LF) — "
            "value withheld"
        )
        row["verdict"] = "credential_malformed"
        row["auth"] = "malformed"
        return row

    # `sent` holds the secret. It goes onto the request and is not retained.
    request_headers = {"Accept": "text/event-stream", **sent}
    try:
        req = urllib.request.Request(url, headers=request_headers)
    except ValueError:
        # `Request()` raises ValueError("unknown url type: ...") for a
        # schemeless or otherwise unparseable url. This construction sat
        # OUTSIDE the try, so a bad roster entry crashed the whole run -- and
        # an uncaught exception exits 1, which the launcher reports as "the
        # service is UP". One malformed row is a per-row verdict, not a crash,
        # and certainly not a health assertion.
        #
        # NOT interpolated. ValueError is also how a rejected header value
        # surfaces out of http.client, message and credential included, so this
        # handler stays as blind as the one below.
        row["error"] = "endpoint URL is not a usable HTTP URL — detail withheld"
        row["verdict"] = "invalid_url"
        return row
    try:
        with _urlopen(req, timeout) as resp:
            row["status"] = resp.status
            row["ok"] = 200 <= resp.status < 400
            row["verdict"] = "ok" if row["ok"] else "http_error"
    except urllib.error.HTTPError as exc:
        # A 4xx still proves something is LISTENING and speaking HTTP, which is
        # a different problem from an absent Cipher — say which. 401/403 get
        # their own verdict because the remedy differs: bind the token, versus
        # start the service.
        row["status"] = exc.code
        row["error"] = f"HTTP {exc.code}"
        if exc.code in (401, 403):
            row["verdict"] = "unauthorized"
        elif 300 <= exc.code < 400:
            # Declined by _NoRedirect. Say so, and say the token stayed put.
            row["verdict"] = "redirect"
            row["error"] = f"HTTP {exc.code} redirect refused (credential not forwarded)"
        else:
            row["verdict"] = "http_error"
    except (urllib.error.URLError, socket.timeout, TimeoutError, OSError) as exc:
        row["error"] = str(getattr(exc, "reason", exc))
        row["verdict"] = "unreachable"
    except ValueError:
        # Deliberately NOT interpolated. http.client puts the rejected header
        # value in the message, so `str(exc)` here would be the credential.
        # _header_safe should have caught this already; this is the backstop.
        row["error"] = "request rejected before send (malformed header) — value withheld"
        row["verdict"] = "credential_malformed"
    return row


def check(urls: Optional[List[str]] = None, roster: Optional[Path] = None) -> Dict[str, Any]:
    if _EXPANDER_ERROR:
        # Without the shared expander the credential would resolve differently
        # here than on the path into Claude Code, so any answer this probe got
        # would be vouching for something else. Say so; do not guess.
        raise Unmeasured(_EXPANDER_ERROR)
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
        result = probe(cand["url"], cand.get("headers"))
        result["name"] = cand["name"]
        rows.append(result)

    reachable = [r for r in rows if r["ok"]]
    # "Answered" is the distinction the old code lacked. An endpoint that
    # returned 401 answered; it is up. Only a probe that reached NOTHING
    # justifies telling a session it has no memory.
    answered = [
        r for r in rows
        if r["verdict"] in ("ok", "unauthorized", "http_error", "redirect")
    ]
    unauthorized = [r for r in rows if r["verdict"] == "unauthorized"]
    missing_env: List[str] = []
    for r in rows:
        for name in r.get("missing_env") or []:
            if name not in missing_env:
                missing_env.append(name)
    return {
        "endpoints": rows,
        "reachable": [r["name"] for r in reachable],
        "answered": [r["name"] for r in answered],
        "unauthorized": [r["name"] for r in unauthorized],
        "missing_env": missing_env,
        "ok": bool(reachable),
        "measured": bool(answered),
    }


def exit_code(verdict: Dict[str, Any]) -> int:
    """0 clean / 1 findings / 3 could-not-measure. Fleet doctrine.

    Shared with mcp_toolkit_preflight.py and docker_host_policy_check.py so an
    operator reading a non-zero code does not have to remember which tool it
    came from.
    """
    if verdict["ok"]:
        return 0
    if verdict["measured"]:
        return 1  # something answered, just not usably — a finding
    return 3  # nothing answered at all — no measurement was taken


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", action="append", dest="urls")
    parser.add_argument("--roster", type=Path, default=None)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    try:
        return _run(args)
    except Exception as exc:  # noqa: BLE001 - deliberate backstop, see below
        # A CRASH IS COULD-NOT-MEASURE. Python exits 1 on an uncaught
        # exception, and claude-pmoves.sh reads exit 1 as "something ANSWERED
        # — the service is UP, do not restart it". So without this, any
        # unexpected failure asserted the health of a service it never
        # contacted: the exact inversion this tool was written to remove.
        #
        # The TYPE only, never `str(exc)`. http.client's ValueError for a
        # rejected header embeds the credential verbatim — the same reason the
        # ValueError handlers in probe() are deliberately blind. A backstop
        # that leaks the token would be worse than the crash it catches.
        detail = f"unexpected {type(exc).__name__} during the check"
        if args.as_json:
            print(json.dumps(
                {"measured": False, "reason": f"{detail} — detail withheld"}, indent=2
            ))
        else:
            print(f"UNMEASURED: {detail} — detail withheld", file=sys.stderr)
            print("  This is NOT a pass — assume no persistent memory.", file=sys.stderr)
        return 3


def _run(args: argparse.Namespace) -> int:
    try:
        verdict = check(args.urls, args.roster)
    except Unmeasured as exc:
        if args.as_json:
            print(json.dumps({"measured": False, "reason": str(exc)}, indent=2))
        else:
            print(f"UNMEASURED: {exc}", file=sys.stderr)
            print("  This is NOT a pass — assume no persistent memory.", file=sys.stderr)
        return 3

    rc = exit_code(verdict)

    if args.as_json:
        # `measured` here means a measurement was TAKEN (something answered),
        # not merely that the roster was readable.
        print(json.dumps(verdict, indent=2))
        return rc

    for row in verdict["endpoints"]:
        if row["ok"]:
            # Prefix is load-bearing: claude-pmoves.sh awks /^cipher OK/ for $3.
            print(f"cipher OK   {row['name']}  ({row['url']}) -> {row['status']}")
        elif row["verdict"] == "unauthorized":
            print(
                f"cipher UNAUTHORIZED {row['name']}  ({row['url']}) -> "
                f"{row['error']} — reachable, credential not accepted",
                file=sys.stderr,
            )
        else:
            # The second token IS the verdict class, and claude-pmoves.sh
            # branches on it. "DOWN" for a 404 was the same collapse this tool
            # exists to undo one layer down: something answered, so the remedy
            # is not "start the service" either.
            label = "ANSWERED" if row["verdict"] in ("http_error", "redirect") else "DOWN"
            print(
                f"cipher {label} {row['name']}  ({row['url']}) -> {row['error']}",
                file=sys.stderr,
            )

    if verdict["ok"]:
        return 0

    if verdict["unauthorized"]:
        # The service is UP. Saying "no memory" here is the false negative that
        # cost three sessions their memory layer.
        lines = [
            "Cipher ANSWERED but did not accept the credential (HTTP 401/403).",
            "  The service is UP — this is an access problem, not an outage.",
            "  Do not restart Cipher; bind its token.",
        ]
        if verdict["missing_env"]:
            names = ", ".join(verdict["missing_env"])
            lines.append(f"  Unresolved in the roster: {names} (set and re-launch).")
        else:
            lines.append(
                "  A credential WAS presented and refused — it is stale or wrong."
            )
        lines.append("  Recovery: pmoves/docs/operations/MCP_TOOLKIT.md")
        print("\n".join(lines), file=sys.stderr)
        return rc

    if verdict["measured"]:
        print(
            "Cipher answered, but not usably (see the status above). The service\n"
            "  is reachable; memory may be degraded rather than absent.",
            file=sys.stderr,
        )
        return rc

    print(
        "No cipher endpoint answered. This session has NO persistent memory —\n"
        "  fall back to the auto-memory directory and say so rather than\n"
        "  recalling nothing silently.",
        file=sys.stderr,
    )
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
