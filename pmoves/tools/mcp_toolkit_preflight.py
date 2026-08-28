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

Refusing to guess
-----------------
No Docker, no Toolkit, or no such profile means the gateway's readiness could
not be measured. That exits 3, not 0 — same doctrine as
``docker_host_policy_check.py``. A probe that reports "pass" when it took no
measurement is the failure mode this repo has spent a lot of effort removing.

A wedged resolver is DIFFERENT from unmeasurable: it is a successful
measurement of a broken thing, so it exits 1. The caller decides whether that
blocks. ``mcp-toolkit-gateway-listen.sh`` treats it as advisory — a wedged
resolver breaks only the servers needing credentials, and refusing to start 25
because 4 cannot authenticate is worse than the problem — while CI and
unattended bring-up should gate on the exit code.

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
  1  measured a problem (resolver down) — servers will start unauthenticated
  3  could not measure (no docker / no Toolkit / profile absent) — NOT a pass
  4  usage error
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

_REPO_ROOT = str(Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from pmoves.tools._secrets_common import force_utf8_stdio

DEFAULT_PROFILE = "pmoves_5090_web"

# The resolver reports its own outage in the body with a zero-ish exit in some
# CLI versions, so the text is checked as well as the return code.
_WEDGED_MARKERS = ("deadline_exceeded", "timeout awaiting")


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
    """Returns a verdict dict. Raises Unmeasured when it cannot look."""
    if not profile_exists(profile):
        raise Unmeasured(
            f"profile {profile!r} not imported — run: make -C pmoves mcp-toolkit-bootstrap"
        )
    healthy = resolver_healthy()
    at_risk = servers_requiring_secrets(profile)
    return {
        "profile": profile,
        "resolver_healthy": healthy,
        "servers_requiring_secrets": at_risk,
        "ok": healthy,
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

    if args.as_json:
        print(json.dumps({"measured": True, **verdict}, indent=2))
        return 0 if verdict["ok"] else 1

    print(f"profile '{verdict['profile']}' present")
    at_risk = verdict["servers_requiring_secrets"]
    if verdict["resolver_healthy"]:
        print("secret resolver responds")
        if at_risk:
            print(f"{len(at_risk)} server(s) declare a secret; resolver is up so they can be provisioned")
            print("  verify coverage: make -C pmoves docker-mcp-secrets-hydrate DRY_RUN=1")
        print("preflight clean")
        return 0

    print("WARN: the Docker MCP secret resolver is NOT answering.", file=sys.stderr)
    print(
        "  Servers needing a credential will start UNAUTHENTICATED and fail at\n"
        "  call time (typically 401), not here.",
        file=sys.stderr,
    )
    for row in at_risk:
        print(f"    {row['server']}  needs  {row['secret']}", file=sys.stderr)
    print(
        "  Recovery: pmoves/docs/operations/MCP_TOOLKIT.md — resolver recovery",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
