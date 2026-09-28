#!/usr/bin/env python3
"""Detect drift between the repo's Tailscale policy and the LIVE tailnet policy.

The repo file ``pmoves/configs/tailscale-acl-policy.json`` is declared the source
of truth and is pushed by ``.github/workflows/deploy-tailscale-acl.yml`` on merge
to main. Nothing checked that the tailnet still *holds* it afterwards: an edit in
the admin console (or a second gitops pipeline) silently diverges the two, and the
repo's ``sshTests`` keep reading green against a policy that is no longer live.

This tool is READ-ONLY. It performs one ``GET /api/v2/tailnet/{tailnet}/acl``
(plus, for OAuth, one token exchange) and never writes to the tailnet.

Both sides are normalised before comparison: HuJSON comments and trailing commas
are stripped, then the documents are compared as parsed JSON (object key order and
whitespace are irrelevant; LIST order is kept, because rule order is how a human
reads the policy and a reorder is worth seeing). Values under any key matching
``/key|secret|token/i`` are redacted in the printed diff as a precaution; the
equality check itself uses the unredacted documents, so drift inside a redacted
field is still reported (as a path, without the value).

Credentials (first match wins, values are never printed):
  * ``TS_OAUTH_CLIENT_ID`` + ``TS_OAUTH_SECRET``  -> OAuth client-credentials token
  * ``TS_API_KEY`` / ``TAILSCALE_API_KEY`` / ``TAILSCALE_APIKEY`` -> API key
Tailnet: ``TS_TAILNET`` / ``TAILSCALE_TAILNET``, default ``-`` (the credential's
own tailnet, per the Tailscale API).

Exit codes (fleet doctrine): 0 no drift, 1 drift, 3 could-not-measure.
"""

from __future__ import annotations

import argparse
import base64
import difflib
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

API_BASE = "https://api.tailscale.com/api/v2"
DEFAULT_POLICY = "pmoves/configs/tailscale-acl-policy.json"
REDACT_RE = re.compile(r"key|secret|token", re.IGNORECASE)
REDACTED = "<redacted>"

EXIT_CLEAN = 0
EXIT_DRIFT = 1
EXIT_UNMEASURED = 3


class CouldNotMeasure(Exception):
    """The comparison could not be made (no credentials, HTTP failure, bad input)."""


# --------------------------------------------------------------------------- #
# HuJSON -> JSON
# --------------------------------------------------------------------------- #
def strip_hujson(text: str) -> str:
    """Remove // and /* */ comments and trailing commas, respecting strings.

    A character-level scanner, not a regex: a policy value such as
    ``"https://login.example"`` contains ``//`` inside a string and must survive.
    """
    out: list[str] = []
    i, n = 0, len(text)
    in_str = False
    while i < n:
        c = text[i]
        if in_str:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if c == '"':
                in_str = False
            i += 1
            continue
        if c == '"':
            in_str = True
            out.append(c)
            i += 1
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "/":
            j = text.find("\n", i)
            i = n if j == -1 else j
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "*":
            j = text.find("*/", i + 2)
            if j == -1:
                raise ValueError("unterminated /* comment")
            i = j + 2
            continue
        out.append(c)
        i += 1
    if in_str:
        raise ValueError("unterminated string")
    # Trailing commas: a comma followed only by whitespace before } or ].
    # Safe now that comments are gone; strings cannot contain a raw newline,
    # but they can contain ",]" -- so rescan with string awareness.
    return _strip_trailing_commas("".join(out))


def _strip_trailing_commas(text: str) -> str:
    out: list[str] = []
    i, n = 0, len(text)
    in_str = False
    while i < n:
        c = text[i]
        if in_str:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if c == '"':
                in_str = False
            i += 1
            continue
        if c == '"':
            in_str = True
        elif c == ",":
            j = i + 1
            while j < n and text[j] in " \t\r\n":
                j += 1
            if j < n and text[j] in "}]":
                i += 1
                continue
        out.append(c)
        i += 1
    return "".join(out)


def parse_policy(text: str, source: str) -> Any:
    try:
        return json.loads(strip_hujson(text))
    except (ValueError, json.JSONDecodeError) as exc:
        raise CouldNotMeasure(f"{source}: not parseable as HuJSON/JSON: {exc}") from exc


# --------------------------------------------------------------------------- #
# Normalise / redact / diff
# --------------------------------------------------------------------------- #
def canonical(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def redact(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {
            k: (REDACTED if REDACT_RE.search(str(k)) else redact(v)) for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [redact(v) for v in obj]
    return obj


def section_status(repo: Any, live: Any) -> dict[str, str]:
    """Per top-level key: same / changed / repo-only / live-only."""
    if not (isinstance(repo, dict) and isinstance(live, dict)):
        return {"<root>": "same" if repo == live else "changed"}
    out: dict[str, str] = {}
    for key in sorted(set(repo) | set(live)):
        if key not in live:
            out[key] = "repo-only"
        elif key not in repo:
            out[key] = "live-only"
        else:
            out[key] = "same" if repo[key] == live[key] else "changed"
    return out


def compare(repo: Any, live: Any, repo_label: str, live_label: str) -> tuple[bool, str]:
    """Return (drifted, human report). Equality is on UNREDACTED documents."""
    drifted = repo != live
    lines: list[str] = []
    if not drifted:
        lines.append(f"OK: no drift -- {repo_label} is semantically identical to {live_label}.")
        return False, "\n".join(lines) + "\n"
    status = section_status(repo, live)
    lines.append(f"DRIFT: {repo_label} differs from {live_label}.")
    lines.append("Top-level sections:")
    for key, st in status.items():
        if st != "same":
            lines.append(f"  - {key}: {st}")
    diff = list(
        difflib.unified_diff(
            canonical(redact(repo)).splitlines(keepends=True),
            canonical(redact(live)).splitlines(keepends=True),
            fromfile=repo_label,
            tofile=live_label,
            n=3,
        )
    )
    if diff:
        lines.append("")
        lines.append("Unified diff (canonical JSON, comments stripped, secrets redacted):")
        lines.append("".join(diff).rstrip("\n"))
    else:
        lines.append("")
        lines.append(
            "The difference lies ONLY inside redacted (key/secret/token) fields; "
            "values withheld."
        )
    return True, "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- #
# Live fetch (read-only)
# --------------------------------------------------------------------------- #
def _http(req: urllib.request.Request, what: str) -> bytes:
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 - fixed https host
            return resp.read()
    except urllib.error.HTTPError as exc:
        hint = ""
        if exc.code in (401, 403):
            hint = (
                " -- credential rejected or lacks policy READ scope "
                "(API key expired/revoked, or OAuth client without policy_file:read / acl:read)"
            )
        elif exc.code == 404:
            hint = " -- tailnet name not found for this credential"
        raise CouldNotMeasure(f"{what}: HTTP {exc.code}{hint}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise CouldNotMeasure(f"{what}: network error: {exc}") from None


def _env(*names: str) -> str:
    for name in names:
        val = os.environ.get(name, "").strip()
        if val:
            return val
    return ""


def resolve_auth_header(env_get=_env) -> tuple[str, str]:
    """Return (Authorization header value, auth kind). Never logs the secret."""
    cid = env_get("TS_OAUTH_CLIENT_ID")
    csec = env_get("TS_OAUTH_SECRET")
    if cid and csec:
        body = urllib.parse.urlencode(
            {"client_id": cid, "client_secret": csec, "grant_type": "client_credentials"}
        ).encode()
        req = urllib.request.Request(
            f"{API_BASE}/oauth/token",
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        raw = _http(req, "OAuth token exchange")
        try:
            token = json.loads(raw)["access_token"]
        except (ValueError, KeyError) as exc:
            raise CouldNotMeasure("OAuth token exchange: no access_token in response") from exc
        return f"Bearer {token}", "oauth"
    key = env_get("TS_API_KEY", "TAILSCALE_API_KEY", "TAILSCALE_APIKEY")
    if key:
        basic = base64.b64encode(f"{key}:".encode()).decode()
        return f"Basic {basic}", "api-key"
    raise CouldNotMeasure(
        "no credential: set TS_OAUTH_CLIENT_ID+TS_OAUTH_SECRET or "
        "TS_API_KEY/TAILSCALE_API_KEY/TAILSCALE_APIKEY"
    )


def fetch_live_policy(tailnet: str, auth_header: str) -> str:
    url = f"{API_BASE}/tailnet/{urllib.parse.quote(tailnet, safe='-.@')}/acl"
    req = urllib.request.Request(
        url,
        headers={"Authorization": auth_header, "Accept": "application/hujson"},
        method="GET",
    )
    return _http(req, "GET tailnet policy").decode("utf-8")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def run(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--policy-file", default=DEFAULT_POLICY, help="repo policy (HuJSON)")
    ap.add_argument(
        "--live-file",
        help="compare against this file instead of fetching (offline / fixtures)",
    )
    ap.add_argument(
        "--save-live",
        help="write the fetched live policy (canonical JSON, redacted) to this path",
    )
    ap.add_argument(
        "--report-only",
        action="store_true",
        help="print drift but exit 0 (PR preview: the PR is EXPECTED to differ)",
    )
    args = ap.parse_args(argv)

    try:
        repo_path = Path(args.policy_file)
        if not repo_path.is_file():
            raise CouldNotMeasure(f"policy file not found: {repo_path}")
        repo = parse_policy(repo_path.read_text(encoding="utf-8"), str(repo_path))

        if args.live_file:
            live_text = Path(args.live_file).read_text(encoding="utf-8")
            live_label = f"live:{args.live_file}"
        else:
            tailnet = _env("TS_TAILNET", "TAILSCALE_TAILNET") or "-"
            auth_header, kind = resolve_auth_header()
            print(f"Fetching live policy (auth={kind}, tailnet={'<set>' if tailnet != '-' else '-'})")
            live_text = fetch_live_policy(tailnet, auth_header)
            live_label = "live:tailnet"
        live = parse_policy(live_text, live_label)
    except CouldNotMeasure as exc:
        print(f"COULD-NOT-MEASURE: {exc}", file=sys.stderr)
        return EXIT_UNMEASURED

    if args.save_live:
        Path(args.save_live).write_text(canonical(redact(live)), encoding="utf-8")

    drifted, report = compare(repo, live, f"repo:{args.policy_file}", live_label)
    sys.stdout.write(report)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write("## Tailscale policy drift\n\n```diff\n" + report + "```\n")
    if drifted and not args.report_only:
        return EXIT_DRIFT
    return EXIT_CLEAN


if __name__ == "__main__":
    sys.exit(run())
