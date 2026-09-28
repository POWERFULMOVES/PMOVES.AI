#!/usr/bin/env python3
"""Tailscale policy checks: live DRIFT (repo vs tailnet) and server-side VALIDATE.

The repo file ``pmoves/configs/tailscale-acl-policy.json`` is declared the source
of truth and is pushed by ``.github/workflows/deploy-tailscale-acl.yml`` on merge
to main. Nothing checked that the tailnet still *holds* it afterwards, and the
PR-time "test" (gitops-pusher) silently skips validation whenever the live ETag
equals the local hash.

Two modes, both READ-ONLY against the tailnet:

``drift`` (default)
    One ``GET /api/v2/tailnet/{tailnet}/acl``. Both sides are normalised (HuJSON
    comments and trailing commas stripped) and compared as parsed JSON, type-strict
    (``true`` is not ``1``); object key order is irrelevant, LIST order is kept.

    The repo is PUBLIC, and drift is by definition content that is NOT in the
    public file, so the default report is STRUCTURAL ONLY: which sections differ,
    counts of added/removed/changed entries, and the paths of the changed entries,
    never a value. A key that exists only on the live side is printed as
    ``<live-only key>`` (its name may itself be topology: a host name, a tag).
    ``--show-values`` adds a unified diff with key/secret/token fields redacted; it
    is for a LOCAL terminal and the workflows never pass it.

``validate``
    One ``POST /api/v2/tailnet/{tailnet}/acl/validate`` with the repo policy as the
    body. Per the Tailscale API this endpoint never modifies the tailnet: it parses
    the posted policy as a hypothetical new policy file and runs its tests against
    it. It is sent on EVERY run (no ETag short-circuit). Any error, ``message`` or
    ``data`` in the response is a finding.

Credentials (first match wins, values are never printed):
  * ``TS_OAUTH_CLIENT_ID`` + ``TS_OAUTH_SECRET``  -> OAuth client-credentials token
  * ``TS_API_KEY`` / ``TAILSCALE_API_KEY`` / ``TAILSCALE_APIKEY`` -> API key
Tailnet: ``TS_TAILNET`` / ``TAILSCALE_TAILNET``, default ``-`` (the credential's
own tailnet, per the Tailscale API).

Exit codes (fleet doctrine): 0 clean, 1 finding (drift / validation failure),
3 could-not-measure. ANY failure other than a completed comparison or a completed
validation maps to 3, so a broken measurement is never reported as drift.
"""

from __future__ import annotations

import argparse
import base64
import difflib
import http.client
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

# Kept separate from __doc__: under ``python -OO`` docstrings are stripped.
DESCRIPTION = "Tailscale policy drift (repo vs live) and server-side validation. Read-only."

API_BASE = "https://api.tailscale.com/api/v2"
DEFAULT_POLICY = "pmoves/configs/tailscale-acl-policy.json"
REDACT_RE = re.compile(r"key|secret|token", re.IGNORECASE)
REDACTED = "<redacted>"
LIVE_ONLY_KEY = "<live-only key>"
MAX_PATHS = 200
MAX_LINE = 300

EXIT_CLEAN = 0
EXIT_FINDING = 1
EXIT_DRIFT = EXIT_FINDING
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
# Normalise / compare (structural, value-free by default)
# --------------------------------------------------------------------------- #
def canonical(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def same(a: Any, b: Any) -> bool:
    """Type-strict equality: JSON serialisation distinguishes true/1 and 1/1.0."""
    return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def redact(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {
            k: (REDACTED if REDACT_RE.search(str(k)) else redact(v)) for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [redact(v) for v in obj]
    return obj


def _safe(text: str) -> str:
    """Neutralise markdown fences/backticks and clip, for logs and step summaries."""
    return text.replace("`", "'").replace("\r", " ").replace("\n", " ")[:MAX_LINE]


def _render_path(parts: list[Any]) -> str:
    out = ""
    for i, p in enumerate(parts):
        if isinstance(p, int):
            out += f"[{p}]"
        elif p == LIVE_ONLY_KEY:
            out += f"[{LIVE_ONLY_KEY}]"
        elif i == 0:
            out += str(p)
        elif re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", str(p)):
            out += f".{p}"
        else:
            out += f"[{json.dumps(p)}]"
    return _safe(out)


def structural_changes(repo: Any, live: Any) -> list[tuple[list[Any], str]]:
    """Paths of differences, without values.

    A dict key is only named if it exists in the REPO document (already public),
    or at the top level (Tailscale schema section names). Keys that exist only on
    the live side are masked. List comparison is positional.
    """
    changes: list[tuple[list[Any], str]] = []

    def walk(r: Any, l: Any, path: list[Any]) -> None:
        if same(r, l):
            return
        if isinstance(r, dict) and isinstance(l, dict):
            for k in sorted(set(r) | set(l), key=str):
                if k not in l:
                    changes.append((path + [k], "removed on live"))
                elif k not in r:
                    name = k if not path else LIVE_ONLY_KEY
                    changes.append((path + [name], "added on live"))
                else:
                    walk(r[k], l[k], path + [k])
        elif isinstance(r, list) and isinstance(l, list):
            for i in range(max(len(r), len(l))):
                if i >= len(l):
                    changes.append((path + [i], "removed on live"))
                elif i >= len(r):
                    changes.append((path + [i], "added on live"))
                else:
                    walk(r[i], l[i], path + [i])
        elif type(r) is not type(l):
            changes.append((path, "type changed"))
        else:
            changes.append((path, "changed"))

    walk(repo, live, [])
    return changes


def compare(
    repo: Any, live: Any, repo_label: str, live_label: str, show_values: bool = False
) -> tuple[bool, str]:
    """Return (drifted, report). The default report contains no policy VALUES."""
    if same(repo, live):
        return False, f"OK: no drift -- {repo_label} is semantically identical to {live_label}.\n"
    changes = structural_changes(repo, live)
    lines = [f"DRIFT: {repo_label} differs from {live_label}.", "Sections (added / removed / changed):"]
    per: dict[str, list[int]] = {}
    for path, kind in changes:
        section = _safe(str(path[0])) if path else "<root>"
        counts = per.setdefault(section, [0, 0, 0])
        counts[0 if kind == "added on live" else 1 if kind == "removed on live" else 2] += 1
    for section in sorted(per):
        a, r, c = per[section]
        lines.append(f"  - {section}: +{a} / -{r} / ~{c}")
    lines.append("Changed paths (values withheld: this output may be public):")
    for path, kind in changes[:MAX_PATHS]:
        lines.append(f"  - {_render_path(path) or '<root>'}: {kind}")
    if len(changes) > MAX_PATHS:
        lines.append(f"  ... {len(changes) - MAX_PATHS} more")
    if show_values:
        diff = difflib.unified_diff(
            canonical(redact(repo)).splitlines(keepends=True),
            canonical(redact(live)).splitlines(keepends=True),
            fromfile=repo_label,
            tofile=live_label,
            n=3,
        )
        text = "".join(diff).rstrip("\n")
        lines.append("")
        lines.append("--show-values: unified diff (LOCAL ONLY; key/secret/token redacted):")
        lines.append(text or "(difference lies only inside redacted fields)")
    return True, "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- #
# Tailscale API (read-only)
# --------------------------------------------------------------------------- #
def _request(
    req: urllib.request.Request, what: str, finding_codes: tuple[int, ...] = ()
) -> tuple[int, bytes]:
    """Return (status, body). HTTP codes in ``finding_codes`` return their body
    instead of raising; everything else that is not 2xx is could-not-measure."""
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 - fixed https host
            return resp.status if hasattr(resp, "status") else 200, resp.read()
    except urllib.error.HTTPError as exc:
        if exc.code in finding_codes:
            try:
                body = exc.read() or b""
            except (OSError, http.client.HTTPException):
                body = b""
            return exc.code, body
        hint = ""
        if exc.code in (401, 403):
            hint = (
                " -- credential rejected or lacks policy scope "
                "(API key expired/revoked, or OAuth client without policy_file scope)"
            )
        elif exc.code == 404:
            hint = " -- tailnet name not found for this credential"
        raise CouldNotMeasure(f"{what}: HTTP {exc.code}{hint}") from None
    except (urllib.error.URLError, TimeoutError, OSError, http.client.HTTPException) as exc:
        raise CouldNotMeasure(f"{what}: transport error: {type(exc).__name__}") from None


def _env(*names: str) -> str:
    for name in names:
        val = os.environ.get(name, "").strip()
        if val:
            return val
    return ""


def resolve_auth_header() -> tuple[str, str]:
    """Return (Authorization header value, auth kind). Never logs the secret."""
    cid = _env("TS_OAUTH_CLIENT_ID")
    csec = _env("TS_OAUTH_SECRET")
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
        _, raw = _request(req, "OAuth token exchange")
        try:
            doc = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise CouldNotMeasure("OAuth token exchange: response is not JSON") from exc
        token = doc.get("access_token") if isinstance(doc, dict) else None
        if not isinstance(token, str) or not token:
            raise CouldNotMeasure("OAuth token exchange: no access_token in response")
        return f"Bearer {token}", "oauth"
    key = _env("TS_API_KEY", "TAILSCALE_API_KEY", "TAILSCALE_APIKEY")
    if key:
        basic = base64.b64encode(f"{key}:".encode()).decode()
        return f"Basic {basic}", "api-key"
    raise CouldNotMeasure(
        "no credential: set TS_OAUTH_CLIENT_ID+TS_OAUTH_SECRET or "
        "TS_API_KEY/TAILSCALE_API_KEY/TAILSCALE_APIKEY"
    )


def _acl_url(tailnet: str, suffix: str = "") -> str:
    return f"{API_BASE}/tailnet/{urllib.parse.quote(tailnet, safe='-.@')}/acl{suffix}"


def _decode(raw: bytes, what: str) -> str:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CouldNotMeasure(f"{what}: response is not UTF-8") from exc


def fetch_live_policy(tailnet: str, auth_header: str) -> str:
    req = urllib.request.Request(
        _acl_url(tailnet),
        headers={"Authorization": auth_header, "Accept": "application/hujson"},
        method="GET",
    )
    _, raw = _request(req, "GET tailnet policy")
    return _decode(raw, "GET tailnet policy")


def validate_policy(tailnet: str, auth_header: str, policy_text: str) -> tuple[bool, list[str]]:
    """POST the policy to /acl/validate. Returns (ok, finding lines)."""
    req = urllib.request.Request(
        _acl_url(tailnet, "/validate"),
        data=policy_text.encode("utf-8"),
        headers={
            "Authorization": auth_header,
            "Content-Type": "application/hujson",
            "Accept": "application/json",
        },
        method="POST",
    )
    # 400/422: the API rejected the POLICY (a finding), not the request.
    status, raw = _request(req, "POST policy validate", finding_codes=(400, 422))
    text = raw.decode("utf-8", errors="replace").strip()
    if status in (400, 422):
        detail = ""
        try:
            doc = json.loads(text) if text else {}
            if isinstance(doc, dict) and doc.get("message"):
                detail = f": {doc['message']}"
        except ValueError:
            pass
        return False, [_safe(f"policy rejected (HTTP {status}){detail}")]
    if not text:
        return True, []
    try:
        doc = json.loads(text)
    except ValueError as exc:
        raise CouldNotMeasure("POST policy validate: 2xx response is not JSON") from exc
    if not isinstance(doc, dict):
        raise CouldNotMeasure("POST policy validate: 2xx response is not a JSON object")
    findings: list[str] = []
    if doc.get("message"):
        findings.append(_safe(f"message: {doc['message']}"))
    data = doc.get("data")
    if data:
        entries = data if isinstance(data, list) else [data]
        for entry in entries:
            if isinstance(entry, dict):
                who = entry.get("user") or entry.get("src") or "?"
                for field in ("errors", "warnings"):
                    for item in entry.get(field) or []:
                        findings.append(_safe(f"test {field[:-1]} [{who}]: {item}"))
                if not (entry.get("errors") or entry.get("warnings")):
                    findings.append(_safe(f"data: {json.dumps(entry, sort_keys=True)}"))
            else:
                findings.append(_safe(f"data: {entry}"))
    for key in ("errors", "error"):
        if doc.get(key):
            findings.append(_safe(f"{key}: {doc[key]}"))
    return (not findings), findings


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _write_summary(title: str, body: str) -> None:
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary:
        return
    try:
        with open(summary, "a", encoding="utf-8") as fh:
            # Indented block, not a ``` fence: nothing in body can break out of it.
            fh.write(f"## {title}\n\n")
            fh.write("".join(f"    {line}\n" for line in body.splitlines()))
            fh.write("\n")
    except OSError as exc:  # the verdict stands; only the summary is lost
        print(f"warning: could not write step summary: {type(exc).__name__}", file=sys.stderr)


def _read(path: str, what: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise CouldNotMeasure(f"{what} {path}: {type(exc).__name__}") from None


def run(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=DESCRIPTION)
    ap.add_argument("mode", nargs="?", choices=("drift", "validate"), default="drift")
    ap.add_argument("--policy-file", default=DEFAULT_POLICY, help="repo policy (HuJSON)")
    ap.add_argument("--live-file", help="drift: compare against this file instead of fetching")
    ap.add_argument(
        "--save-live", help="drift: write the fetched live policy (redacted) to this LOCAL path"
    )
    ap.add_argument(
        "--report-only",
        action="store_true",
        help="drift: print drift but exit 0 (PR preview: the PR is EXPECTED to differ)",
    )
    ap.add_argument(
        "--show-values",
        action="store_true",
        help="drift: add a redacted value diff. LOCAL USE ONLY; never in CI logs",
    )
    args = ap.parse_args(argv)

    try:
        repo_text = _read(args.policy_file, "policy file")
        if args.mode == "validate":
            tailnet = _env("TS_TAILNET", "TAILSCALE_TAILNET") or "-"
            auth_header, kind = resolve_auth_header()
            print(f"Validating policy server-side (auth={kind}, tailnet={'<set>' if tailnet != '-' else '-'})")
            ok, findings = validate_policy(tailnet, auth_header, repo_text)
            report = (
                "OK: Tailscale validated the policy and its tests passed.\n"
                if ok
                else "VALIDATION FAILED:\n" + "".join(f"  - {f}\n" for f in findings)
            )
            sys.stdout.write(report)
            _write_summary("Tailscale policy validate", report)
            return EXIT_CLEAN if ok else EXIT_FINDING

        repo = parse_policy(repo_text, f"repo:{args.policy_file}")
        if args.live_file:
            live_text = _read(args.live_file, "live file")
            live_label = "live:file"
        else:
            tailnet = _env("TS_TAILNET", "TAILSCALE_TAILNET") or "-"
            auth_header, kind = resolve_auth_header()
            print(f"Fetching live policy (auth={kind}, tailnet={'<set>' if tailnet != '-' else '-'})")
            live_text = fetch_live_policy(tailnet, auth_header)
            live_label = "live:tailnet"
        live = parse_policy(live_text, live_label)
        if args.save_live:
            try:
                Path(args.save_live).write_text(canonical(redact(live)), encoding="utf-8")
            except OSError as exc:
                raise CouldNotMeasure(f"--save-live: {type(exc).__name__}") from None
    except CouldNotMeasure as exc:
        print(f"COULD-NOT-MEASURE: {_safe(str(exc))}", file=sys.stderr)
        return EXIT_UNMEASURED

    # The ONLY source of a drift exit: a completed comparison.
    drifted, report = compare(repo, live, "repo", live_label, show_values=args.show_values)
    sys.stdout.write(report)
    _write_summary("Tailscale policy drift", report if not args.show_values else report.split("\n--show-values")[0])
    if drifted and not args.report_only:
        return EXIT_DRIFT
    return EXIT_CLEAN


def main(argv: list[str] | None = None) -> int:
    """Exit-code integrity: anything that is not a completed verdict is 3."""
    try:
        return run(argv)
    except SystemExit as exc:  # argparse usage error (2) or --help (0)
        if exc.code in (0, None):
            return EXIT_CLEAN
        print("COULD-NOT-MEASURE: invalid arguments", file=sys.stderr)
        return EXIT_UNMEASURED
    except Exception as exc:  # noqa: BLE001 - deliberate: never let a crash read as drift
        print(f"COULD-NOT-MEASURE: unexpected {type(exc).__name__}: {_safe(str(exc))[:200]}", file=sys.stderr)
        return EXIT_UNMEASURED


if __name__ == "__main__":
    sys.exit(main())
