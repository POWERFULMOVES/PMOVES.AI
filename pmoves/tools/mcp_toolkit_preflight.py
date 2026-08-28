#!/usr/bin/env python3
"""Preflight for the Docker MCP Toolkit gateway.

WHY THIS EXISTS
---------------
``scripts/mcp-toolkit-gateway-listen.sh`` checked that Docker was present and
the profile was imported, then started a gateway. It never checked that the
SECRET RESOLVER works. On 2026-08-28 the resolver was wedged
(``ResolverService/GetSecrets: deadline_exceeded``, surviving a Docker Desktop
restart) and the gateway started anyway — serving ``github-official`` with an
empty ``GITHUB_PERSONAL_ACCESS_TOKEN``. Every call returned 401 Bad
credentials, and nothing at start time said why. The failure surfaced at call
time, in a different tool, to a different person.

This reports it at START time, and names the servers affected.

A LIVE RESOLVER IS NOT COVERAGE
-------------------------------
The first cut of this file asked only "does the resolver answer?" and set
``ok`` from that alone — while already holding, unread, the list of secrets the
profile requires. A resolver that answers over a store where a secret was never
hydrated or was later wiped therefore reported ``ok: true``: strict startup and
CI passed, the server still came up uncredentialed, and it still 401'd at call
time. That is the same defect one level in — a check that reports success while
doing nothing (Codex P1 on #2806). Readiness now means BOTH the resolver
answers AND every secret the profile requires is present in the store.

Refusing to guess
-----------------
No Docker, no Toolkit, or no such profile means the gateway's readiness could
not be measured. That exits 3, not 0 — same doctrine as
``docker_host_policy_check.py``. A probe that reports "pass" when it took no
measurement is the failure mode this repo has spent a lot of effort removing.

The same doctrine governs the coverage check: a ``secret ls`` that cannot be
enumerated is exit 3, NOT an empty set of problems. "I could not read the
store" and "the store has everything" are different answers and must not share
a code path.

A wedged resolver, or a required secret that is absent, is DIFFERENT from
unmeasurable: it is a successful measurement of a broken thing, so it exits 1.
The caller decides whether that blocks. ``mcp-toolkit-gateway-listen.sh``
treats it as advisory — a wedged resolver breaks only the servers needing
credentials, and refusing to start 25 because 4 cannot authenticate is worse
than the problem — while CI and unattended bring-up should gate on the exit
code.

Python, not shell, deliberately: this has to run on every node class including
arm64 (SPARK, Jetson, the KVMs), and the repo's shell-probe tests cannot stub a
binary on Windows — Git Bash resolves ``docker`` to ``docker.exe`` and never
sees an extensionless stub, so a PATH stub silently tests the REAL daemon.

Usage:
  python pmoves/tools/mcp_toolkit_preflight.py                    # gate
  python pmoves/tools/mcp_toolkit_preflight.py --profile <id>
  python pmoves/tools/mcp_toolkit_preflight.py --json

Exit codes:
  0  gateway is ready to serve every server in the profile
  1  measured a problem — resolver down, or a required secret is absent from
     the store; either way the affected servers start unauthenticated
  3  could not measure (no docker / no Toolkit / profile absent / the secret
     store could not be enumerated) — NOT a pass
  4  usage error
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import yaml

_REPO_ROOT = str(Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from pmoves.tools._secrets_common import force_utf8_stdio

DEFAULT_PROFILE = "pmoves_5090_web"

# The resolver reports its own outage in the body with a zero-ish exit in some
# CLI versions, so the text is checked as well as the return code.
_WEDGED_MARKERS = ("deadline_exceeded", "timeout awaiting")


# --------------------------------------------------------------------------
# Reporting a secret NAME safely.
#
# CodeQL alert 376 flagged the at-risk report below as clear-text logging of a
# secret. What it prints is the secret's NAME, not its value: the value never
# transits this process. Established, not assumed —
#   * docker/mcp-gateway `pkg/catalog/types.go` defines
#         type Secret struct { Name string; Env string }
#     with NO value field, so `docker mcp profile show` has nothing to serialise
#     a value INTO; and
#   * `cmd/docker-mcp/commands/secret.go` emits `{ID, Provider}` (table) and
#     `{name, provider}` (--json) from `secret ls` — again no value at either
#     verbosity. Values are fetched by the gateway from the ResolverService at
#     container start, and never pass through this tool.
#
# That makes the taint report a false positive. The guard below is defence in
# depth for the one input the vendor schema does not constrain — a hand-authored
# or corrupted profile that puts something else where a name belongs — and it is
# NOT a rename to dodge the heuristic; it is a runtime barrier with its own
# tests. Mirrors emit_local_env._reportable_name and
# docker_mcp_secrets_hydrate._safe_name, the same call this repo has already
# made twice, extended with `/` for namespace-qualified Toolkit IDs.
#
# Honest bound: a value that is itself short and name-shaped (a bare 40-char
# `ghp_...` PAT, say) is not distinguishable from a name by shape and would
# pass. The structural argument above, not this regex, is why that cannot occur;
# the regex is what stops the malformed-input case from becoming a disclosure.
# --------------------------------------------------------------------------
_REPORTABLE_SECRET_NAME_RE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_./\-]{0,63}")


def _reportable_secret_name(name: str) -> str:
    """A secret NAME safe to print, or a redaction placeholder."""
    if _REPORTABLE_SECRET_NAME_RE.fullmatch(name or ""):
        return name
    return "<non-conforming-secret-name>"


def _redacted(rows: Optional[List[Dict[str, str]]]) -> Optional[List[Dict[str, str]]]:
    """Apply the name guard to every reportable field of every row.

    Applied at the OUTPUT boundary, not at construction: the store comparison
    has to run against the profile's real names, or a redaction would silently
    turn into a "missing secret" finding.
    """
    if rows is None:
        return None
    return [
        {
            "server": _reportable_secret_name(row.get("server", "")),
            "secret": _reportable_secret_name(row.get("secret", "")),
            "env": _reportable_secret_name(row.get("env", "")),
        }
        for row in rows
    ]


def _print_at_risk(rows: Optional[List[Dict[str, str]]]) -> None:
    """The ONE place a server/secret-name pair is written to a stream.

    Both failure paths (resolver wedged, required secret absent) used to carry
    their own copy of this loop. One writer means one guard to audit, one
    format for operators to learn, and no way for the two paths to drift.
    """
    for row in _redacted(rows) or []:
        print(f"    {row['server']}  needs  {row['secret']}", file=sys.stderr)


class Unmeasured(RuntimeError):
    """The check could not be performed. Never reported as a pass."""


def _docker(*args: str, timeout: int = 45) -> str:
    if not shutil.which("docker"):
        raise Unmeasured("docker CLI not on PATH")
    try:
        result = subprocess.run(
            ["docker", *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        raise Unmeasured(f"docker {' '.join(args)}: {exc}") from exc
    if result.returncode != 0:
        raise Unmeasured(
            f"docker {' '.join(args)} failed: {(result.stderr or '').strip()[:200]}"
        )
    return result.stdout


def profile_exists(profile: str) -> bool:
    out = _docker("mcp", "profile", "ls")
    ids = [line.split()[0] for line in out.splitlines()[1:] if line.split()]
    return profile in ids


def resolver_healthy() -> bool:
    """True when the MCP secret resolver answers.

    Every credentialed server reads its secret through this at startup, so a
    resolver that does not answer means those servers come up unauthenticated.

    Uses the plain (non---json) form on purpose: it is the one every Toolkit
    version supports, so "the resolver is wedged" stays distinguishable from
    "this CLI is too old to enumerate the store" (see ``secret_store_names``).
    """
    try:
        out = _docker("mcp", "secret", "ls")
    except Unmeasured as exc:
        # A failing `secret ls` is the resolver reporting itself down — that is
        # a measurement, not an absence of one, so long as docker itself ran.
        if "not on PATH" in str(exc):
            raise
        return False
    lowered = out.lower()
    return not any(marker in lowered for marker in _WEDGED_MARKERS)


def _bare(name: str) -> str:
    """Drop a namespace prefix so store and profile names compare like for like.

    `docker mcp secret ls --json` runs each ID through `secret.StripNamespace`
    while the table form prints the qualified `docker/mcp/<name>`. Comparing raw
    would make a namespaced store read as a store missing everything.
    """
    return (name or "").rsplit("/", 1)[-1].strip()


def secret_store_names() -> Set[str]:
    """Every secret NAME the Toolkit store currently holds.

    ``--json`` rather than the table form for three reasons, all from the vendor
    writer in ``cmd/docker-mcp/commands/secret.go``: the table is printed by
    ``PrettyPrintTable(rows, []int{40, 120})`` with NO header row and a 40-column
    TRUNCATION, and its IDs are namespace-qualified. A truncated name compared
    against a profile name yields a confident, wrong "missing" verdict.

    Raises ``Unmeasured`` whenever the store cannot be enumerated. That is the
    whole point: "I could not read the store" must never arrive at the caller
    wearing the same clothes as "nothing is missing".
    """
    raw = _docker("mcp", "secret", "ls", "--json")
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, ValueError) as exc:
        raise Unmeasured(
            "could not parse `docker mcp secret ls --json` "
            f"({exc.__class__.__name__}) — secret coverage was NOT checked"
        ) from exc
    if not isinstance(parsed, list):
        raise Unmeasured(
            "`docker mcp secret ls --json` did not return a list — secret "
            "coverage was NOT checked"
        )
    names: Set[str] = set()
    for item in parsed:
        if not isinstance(item, dict):
            raise Unmeasured(
                "unexpected row shape from `docker mcp secret ls --json` — "
                "secret coverage was NOT checked"
            )
        name = _bare(str(item.get("name") or ""))
        if name:
            names.add(name)
    return names


def servers_requiring_secrets(profile: str) -> List[Dict[str, str]]:
    """Every server in the profile that declares a secret, with the secret's name.

    Read from the profile rather than guessed, so the report names exactly
    which servers are at risk instead of a generic warning nobody can act on.
    """
    doc = yaml.safe_load(_docker("mcp", "profile", "show", profile)) or {}
    found: List[Dict[str, str]] = []
    for entry in doc.get("servers") or []:
        server = ((entry or {}).get("snapshot") or {}).get("server") or {}
        name = server.get("name")
        if not name:
            continue
        for sec in server.get("secrets") or []:
            if sec.get("name"):
                found.append(
                    {"server": name, "secret": sec["name"], "env": sec.get("env", "")}
                )
    return found


def check(profile: str) -> Dict[str, Any]:
    """Returns a verdict dict. Raises Unmeasured when it cannot look.

    ``ok`` is the conjunction, not the resolver alone: a live resolver over a
    store missing a required secret is exactly the 401-at-call-time failure this
    tool exists to catch, and it used to pass.
    """
    if not profile_exists(profile):
        raise Unmeasured(
            f"profile {profile!r} not imported — run: make -C pmoves mcp-toolkit-bootstrap"
        )
    healthy = resolver_healthy()
    at_risk = servers_requiring_secrets(profile)

    missing: Optional[List[Dict[str, str]]] = None
    if healthy:
        # Only meaningful when the resolver answers: enumerating through a
        # wedged resolver would report every secret "missing", which is a guess
        # wearing a measurement's clothes. Unmeasured propagates — a store we
        # could not read is exit 3, never an empty problem list.
        present = secret_store_names()
        missing = [row for row in at_risk if _bare(row["secret"]) not in present]

    return {
        "profile": profile,
        "resolver_healthy": healthy,
        "servers_requiring_secrets": at_risk,
        "missing_secrets": missing,
        "ok": healthy and not missing,
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default=DEFAULT_PROFILE)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    force_utf8_stdio()

    try:
        verdict = check(args.profile)
    except Unmeasured as exc:
        if args.as_json:
            print(json.dumps({"measured": False, "reason": str(exc)}, indent=2))
        else:
            print(f"UNMEASURED: {exc}", file=sys.stderr)
            print("  This is NOT a pass.", file=sys.stderr)
        return 3

    at_risk = verdict["servers_requiring_secrets"]
    missing = verdict["missing_secrets"]

    if args.as_json:
        # Names go through the guard here too: --json is read by CI logs, so a
        # text-mode-only guard would protect the wrong half of the callers.
        print(
            json.dumps(
                {
                    "measured": True,
                    **verdict,
                    "servers_requiring_secrets": _redacted(at_risk),
                    "missing_secrets": _redacted(missing),
                },
                indent=2,
            )
        )
        return 0 if verdict["ok"] else 1

    print(f"profile '{verdict['profile']}' present")

    if not verdict["resolver_healthy"]:
        print("WARN: the Docker MCP secret resolver is NOT answering.", file=sys.stderr)
        print(
            "  Servers needing a credential will start UNAUTHENTICATED and fail at\n"
            "  call time (typically 401), not here.",
            file=sys.stderr,
        )
        _print_at_risk(at_risk)
        print(
            "  Recovery: pmoves/docs/operations/MCP_TOOLKIT.md — resolver recovery",
            file=sys.stderr,
        )
        return 1

    print("secret resolver responds")

    if missing:
        print(
            "WARN: the resolver answers, but the store is MISSING a secret the\n"
            "  profile requires. These servers will start UNAUTHENTICATED and\n"
            "  fail at call time (typically 401), not here.",
            file=sys.stderr,
        )
        _print_at_risk(missing)
        print(
            "  Provision from the funnel (nothing is typed by hand, nothing is\n"
            "  rotated): make -C pmoves docker-mcp-secrets-hydrate DRY_RUN=1\n"
            "                 make -C pmoves docker-mcp-secrets-hydrate",
            file=sys.stderr,
        )
        print(
            "  OAuth-mediated servers (the Cloudflare suite) are not covered by\n"
            "  hydrate — see pmoves/docs/operations/MCP_TOOLKIT.md § 5.",
            file=sys.stderr,
        )
        return 1

    if at_risk:
        print(f"{len(at_risk)} server(s) declare a secret; all are present in the store")
    print("preflight clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
