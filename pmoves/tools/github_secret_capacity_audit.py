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
    PMOVES environment    1 / 100        <- 99 slots effectively unreachable

THE SCOPE PROBLEM, AND WHY THIS TOOL READS EVERY SCOPE
------------------------------------------------------
The manifest's target is a bare ``{github_secret: NAME}`` with NO environment.
The scope is chosen at PUSH time, not declaration time: `push-gh-secrets.sh`
takes `--env` on the command line and passes it to `gh secret set`; omitting it
writes to the repository scope instead.

So a declared name may legitimately live in ANY scope, and comparing the full
declared set against a single scope produces two false verdicts: names that live
in the repository scope get reported "absent from Prod", and the count overflow
gets reported against a scope those names may not target at all.

This tool therefore reads EVERY scope by default -- repository plus each
environment -- and reports:

  * absent   -- declared, and present in NO scope. A true absence.
  * orphans  -- present in some scope, declared nowhere. Unmanaged by the
                funnel; reconciling them is free headroom.
  * capacity -- per scope, which needs no manifest at all: it is a fact about
                GitHub. Reported for every scope so the full and the empty ones
                are both visible.

`--env X` narrows the audit to one scope. That is an ASSERTION by the caller
that the funnel targets X, and the output says so, because absence under a
single-scope read is only true if that assertion holds.

One structural fact worth stating, because it rules out the usual fix:
POWERFULMOVES is a USER account, not an org (`type=User`, and the org-secrets
endpoint 404s). There is no org-secret tier to lift into. Adding an environment
to the manifest's target shape is the change that makes the free capacity
addressable; this tool measures the problem, it does not paper over it.

Names only. The GitHub API never returns secret VALUES and neither does this.

Refusing to guess
-----------------
No `gh`, no auth, an unreadable manifest, a manifest that declares no GitHub
secret targets, or an unenumerable scope list all mean the reconciliation could
not be performed. Those exit 3, not 0 -- same doctrine as
docker_host_policy_check.py.

Usage:
  python pmoves/tools/github_secret_capacity_audit.py
  python pmoves/tools/github_secret_capacity_audit.py --repo OWNER/REPO --env Prod
  python pmoves/tools/github_secret_capacity_audit.py --json

Exit codes:
  0  within capacity, nothing absent, no orphans
  1  findings (over capacity, absent, or orphaned)
  3  could not measure -- NOT a pass
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

# The repository scope has no name. `None` denotes it everywhere a scope is
# passed around, and renders as "(repository)".
REPO_SCOPE: Optional[str] = None


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

    names = {
        target["github_secret"]
        for entry in entries
        for target in (entry.get("targets") or [])
        if isinstance(target, dict) and target.get("github_secret")
    }
    if not names:
        # Entries exist and carry `targets`, but none targets GitHub -- a
        # file/Docker-only manifest, or the wrong manifest selected. Proceeding
        # would make every existing secret an "orphan" and hand back a deletion
        # signal built from nothing. Refuse instead.
        raise Unmeasured(f"no `github_secret` targets declared in {path}")
    return names


def discover_scopes(repo: str) -> List[Optional[str]]:
    """Every scope secrets can live in: the repository, then each environment.

    Enumerating this is REQUIRED, not best-effort. Auditing only the scopes we
    happened to think of would reintroduce the exact defect this replaces:
    calling a name "absent" when it is sitting in an environment nobody read.
    So a failure to list environments is Unmeasured, never a partial answer.
    """
    out = _gh(
        "api", "--paginate", f"repos/{repo}/environments", "--jq", ".environments[].name"
    )
    return [REPO_SCOPE] + [line.strip() for line in out.splitlines() if line.strip()]


def present_secret_names(repo: str, environment: Optional[str] = None) -> Set[str]:
    """Secret NAMES in one scope. --paginate: the API pages at 30, and a
    truncated read would under-report usage and over-report absences."""
    if environment:
        endpoint = f"repos/{repo}/environments/{environment}/secrets"
    else:
        endpoint = f"repos/{repo}/actions/secrets"
    out = _gh("api", "--paginate", endpoint, "--jq", ".secrets[].name")
    return {line.strip() for line in out.splitlines() if line.strip()}


def _scope_label(scope: Optional[str]) -> str:
    return f"env:{scope}" if scope else "(repository)"


def audit(
    repo: str,
    environment: Optional[str] = None,
    manifest: Optional[Path] = None,
) -> Dict[str, Any]:
    declared = declared_secret_names(manifest)

    # `--env X` asserts "the funnel targets X". Absence is only true under that
    # assertion, so it is carried into the report and stated in the output.
    assumed_single_scope = environment is not None
    scopes = [environment] if assumed_single_scope else discover_scopes(repo)

    per_scope: List[Dict[str, Any]] = []
    union: Set[str] = set()
    for scope in scopes:
        present = present_secret_names(repo, scope)
        union |= present
        per_scope.append(
            {
                "scope": _scope_label(scope),
                "present": len(present),
                "headroom": SECRET_LIMIT - len(present),
                "at_cap": len(present) >= SECRET_LIMIT,
            }
        )

    # The funnel writes ONE scope per run (push-gh-secrets.sh --env), so more
    # declared names than a single scope holds cannot be satisfied by one run.
    # That is the true claim; a bare "over capacity" would not be, since an
    # operator can split the set across scopes over several runs.
    single_scope_overflow = max(0, len(declared) - SECRET_LIMIT)

    absent = sorted(declared - union)
    orphans = sorted(union - declared)
    return {
        "repo": repo,
        "scopes_read": [_scope_label(s) for s in scopes],
        "assumed_single_scope": assumed_single_scope,
        "limit": SECRET_LIMIT,
        "declared": len(declared),
        "present_union": len(union),
        "per_scope": per_scope,
        "single_scope_overflow": single_scope_overflow,
        "absent": absent,
        "orphans": orphans,
        "ok": not absent and not orphans and single_scope_overflow == 0,
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument(
        "--env",
        dest="environment",
        default=None,
        help="Audit only this environment, asserting the funnel targets it. "
        "Default reads the repository scope AND every environment.",
    )
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

    # Everything printed below is a NAME or a COUNT. Secret values are never
    # returned by the GitHub API and are never handled here.
    print(f"repo: {report['repo']}")
    if report["assumed_single_scope"]:
        print(
            f"  scope: {report['scopes_read'][0]} only -- absence below is true ONLY if\n"
            f"    the funnel targets this scope (push-gh-secrets.sh --env)."
        )
    for row in report["per_scope"]:  # lgtm[py/clear-text-logging-sensitive-data] -- counts and scope names only; the API never returns secret VALUES
        flag = "  <- AT CAP" if row["at_cap"] else ""
        print(
            f"  {row['scope']:<24} {row['present']:>3}/{report['limit']}"
            f"  headroom {row['headroom']:>3}{flag}"
        )
    print(
        f"  declared {report['declared']}"
        f"  present across all scopes {report['present_union']}"
    )

    if report["single_scope_overflow"]:
        print(
            f"  SINGLE-SCOPE OVERFLOW by {report['single_scope_overflow']}: the manifest\n"
            f"    declares {report['declared']} names but the funnel writes one scope per run,\n"
            f"    and no scope holds more than {report['limit']}. One run cannot provision them all.",
            file=sys.stderr,
        )
    if report["absent"]:
        print(
            f"  absent ({len(report['absent'])}): declared, present in NO scope read",
            file=sys.stderr,
        )
        for name in report["absent"][:20]:  # lgtm[py/clear-text-logging-sensitive-data] -- secret NAMES only, never values
            print(f"    {name}", file=sys.stderr)
        if len(report["absent"]) > 20:
            print(f"    ... {len(report['absent']) - 20} more", file=sys.stderr)
    if report["orphans"]:
        print(
            f"  orphans ({len(report['orphans'])}): present, declared nowhere --\n"
            f"    unmanaged by the funnel; reconciling these is free headroom",
            file=sys.stderr,
        )
        for name in report["orphans"][:20]:  # lgtm[py/clear-text-logging-sensitive-data] -- secret NAMES only, never values
            print(f"    {name}", file=sys.stderr)
        if len(report["orphans"]) > 20:
            print(f"    ... {len(report['orphans']) - 20} more", file=sys.stderr)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
