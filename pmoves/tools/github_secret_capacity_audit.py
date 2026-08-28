#!/usr/bin/env python3
"""Reconcile the CHIT manifest's GitHub-secret targets against what GitHub holds.

WHY THIS EXISTS
---------------
GitHub caps secrets at **100 per scope** — 100 for the repository, and 100 more
for EACH environment, counted separately. Nothing in this repo compared what the
manifest declares against that ceiling, so the funnel could declare more secrets
than the platform can ever store and report success the whole way.

Measured 2026-08-28 on POWERFULMOVES/PMOVES.AI:

    manifest declares   158 distinct github_secret names
    Prod environment    100 / 100        <- at the hard cap
    repository scope     88 / 100
    PMOVES environment    1 / 100        <- 99 slots unreachable (see below)

So 58 declared names cannot exist anywhere, and 79 were absent at the time of
measurement. That is not a backlog; it is over-subscription, and it was silent.

Two structural facts make it worse, both worth stating because they rule out the
usual fixes:

  1. POWERFULMOVES is a USER account, not an org (`type=User`, and the
     org-secrets endpoint 404s). There is no org-secret tier to lift into.
  2. The manifest's target is a bare ``{github_secret: NAME}`` with NO
     environment. So the pipeline cannot address Prod vs PMOVES even though one
     is full and the other is nearly empty. Adding an environment to that target
     shape is the change that unlocks the free capacity; this tool measures the
     problem, it does not paper over it.

WHAT IT REPORTS
---------------
  * over-capacity — declared names exceed the ceiling of the scope they target
  * absent        — declared in the manifest, not present in the scope
  * orphans       — present in GitHub, declared nowhere in the manifest
                    (unmanaged by the funnel; reconciling them is free headroom)

Names only. The GitHub API never returns secret VALUES and neither does this.

Refusing to guess
-----------------
No `gh`, no auth, or an unreadable manifest means the reconciliation could not be
performed. That exits 3, not 0 — same doctrine as docker_host_policy_check.py.

Usage:
  python pmoves/tools/github_secret_capacity_audit.py
  python pmoves/tools/github_secret_capacity_audit.py --repo OWNER/REPO --env Prod
  python pmoves/tools/github_secret_capacity_audit.py --json

Exit codes:
  0  within capacity, nothing absent, no orphans
  1  findings (over capacity, absent, or orphaned)
  3  could not measure — NOT a pass
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = _REPO_ROOT / "pmoves" / "chit" / "secrets_manifest_v2.yaml"
DEFAULT_REPO = "POWERFULMOVES/PMOVES.AI"

# GitHub's documented per-scope ceiling. Repository and each environment get
# their own 100; they do not pool.
SECRET_LIMIT = 100


class Unmeasured(RuntimeError):
    """The reconciliation could not be performed. Never reported as a pass."""


def _gh(*args: str, timeout: int = 60) -> str:
    if not shutil.which("gh"):
        raise Unmeasured("gh CLI not on PATH")
    try:
        result = subprocess.run(
            ["gh", *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        raise Unmeasured(f"gh {' '.join(args)}: {exc}") from exc
    if result.returncode != 0:
        raise Unmeasured(
            f"gh {' '.join(args)} failed: {(result.stderr or '').strip()[:200]}"
        )
    return result.stdout


def declared_secret_names(manifest: Optional[Path] = None) -> Set[str]:
    """Distinct `github_secret` target names in the v2 CHIT manifest."""
    path = manifest or DEFAULT_MANIFEST
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise Unmeasured(f"cannot read manifest {path}: {exc}") from exc

    entries: List[Dict[str, Any]] = []
    for value in doc.values() if isinstance(doc, dict) else []:
        if isinstance(value, list) and value and isinstance(value[0], dict) and "targets" in value[0]:
            entries = value
            break
    if not entries:
        raise Unmeasured(f"no entries with `targets` found in {path}")

    return {
        target["github_secret"]
        for entry in entries
        for target in (entry.get("targets") or [])
        if isinstance(target, dict) and target.get("github_secret")
    }


def present_secret_names(repo: str, environment: Optional[str] = None) -> Set[str]:
    """Secret NAMES in a scope. --paginate: the API pages at 30, and a truncated
    read would under-report usage and over-report absences."""
    if environment:
        endpoint = f"repos/{repo}/environments/{environment}/secrets"
    else:
        endpoint = f"repos/{repo}/actions/secrets"
    out = _gh("api", "--paginate", endpoint, "--jq", ".secrets[].name")
    return {line.strip() for line in out.splitlines() if line.strip()}


def audit(
    repo: str,
    environment: Optional[str],
    manifest: Optional[Path] = None,
) -> Dict[str, Any]:
    declared = declared_secret_names(manifest)
    present = present_secret_names(repo, environment)

    absent = sorted(declared - present)
    orphans = sorted(present - declared)
    scope = f"{repo} env:{environment}" if environment else f"{repo} (repository)"

    over_capacity = max(0, len(declared) - SECRET_LIMIT)
    return {
        "scope": scope,
        "limit": SECRET_LIMIT,
        "declared": len(declared),
        "present": len(present),
        "headroom": SECRET_LIMIT - len(present),
        "over_capacity": over_capacity,
        "absent": absent,
        "orphans": orphans,
        "ok": not absent and not orphans and over_capacity == 0,
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--env", dest="environment", default=None)
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    try:
        report = audit(args.repo, args.environment, args.manifest)
    except Unmeasured as exc:
        if args.as_json:
            print(json.dumps({"measured": False, "reason": str(exc)}, indent=2))
        else:
            print(f"UNMEASURED: {exc}", file=sys.stderr)
            print("  This is NOT a pass.", file=sys.stderr)
        return 3

    if args.as_json:
        print(json.dumps({"measured": True, **report}, indent=2))
        return 0 if report["ok"] else 1

    print(f"scope: {report['scope']}")
    print(
        f"  declared {report['declared']}  present {report['present']}/{report['limit']}"
        f"  headroom {report['headroom']}"
    )
    if report["over_capacity"]:
        print(
            f"  OVER CAPACITY by {report['over_capacity']}: the manifest declares more\n"
            f"    names than this scope can ever hold. They cannot all be provisioned.",
            file=sys.stderr,
        )
    if report["absent"]:
        print(f"  absent ({len(report['absent'])}): declared, not present here", file=sys.stderr)
        for name in report["absent"][:20]:
            print(f"    {name}", file=sys.stderr)
        if len(report["absent"]) > 20:
            print(f"    … {len(report['absent']) - 20} more", file=sys.stderr)
    if report["orphans"]:
        print(
            f"  orphans ({len(report['orphans'])}): present, declared nowhere —\n"
            f"    unmanaged by the funnel; reconciling these is free headroom",
            file=sys.stderr,
        )
        for name in report["orphans"][:20]:
            print(f"    {name}", file=sys.stderr)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
