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

ROUTED TARGETS
--------------
That change exists now: a target may be the mapping ``{name, repo, env}``
(github_secret_targets.py is the one definition of both forms). A routed name
is measured in the repo the manifest names, and ONLY in the scope it pins --
``env`` names an environment, its absence means the repository scope -- because
for a routed name the manifest said where it lives, so any other scope is the
wrong one. Bare names keep the rules above, against ``--repo``.

Every repo the manifest names is read, not only PMOVES.AI. Per repo: absent and
orphans as above, where "declared" means declared FOR THAT REPO -- so a name
routed away from PMOVES.AI whose old copy still sits there reads as an orphan,
which is exactly the headroom the routing was meant to free. The same holds
INSIDE one repo: a routed name found in a scope it is not pinned to (moved from
env:Prod to env:PMOVES, old copy left behind) is a STALE COPY -- declared for
the repo, so never an orphan, yet still occupying a slot. It is reported and
fails the audit; without it Prod stays full while the audit exits 0. A pinned
environment that does not exist makes its names absent (a measurement), while a
repo that cannot be read at all is Unmeasured. A pinned scope declared past the
ceiling is reported, and routed names do not count toward the single-scope
overflow, since a push run never writes them to the caller's scope.

``--env X`` still asserts where BARE names live, and a manifest with only bare
names still skips discovery under it. Pinned scopes need no assertion: when
there are any, the repo's environments are listed so that a pinned environment
that does not exist is reported absent under ``--env`` exactly as without it.

Repo and environment names match case-insensitively, as GitHub's do: a
mapping pinned to ``powerfulmoves/pmoves.ai`` env ``prod`` IS env:Prod of
POWERFULMOVES/PMOVES.AI, not a second repo with a missing environment.

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
from urllib.parse import quote

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from pmoves.tools.github_secret_targets import MalformedTarget, normalize  # noqa: E402

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


def declared_routes(manifest: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Every `github_secret` target in the v2 CHIT manifest, normalized."""
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

    routes: List[Dict[str, Any]] = []
    for entry in entries:
        for target in (entry.get("targets") or []):
            try:
                route = normalize(target)
            except MalformedTarget as exc:
                raise Unmeasured(f"{path}: {exc}") from exc
            if route:
                routes.append(route)
    if not routes:
        # Entries exist and carry `targets`, but none targets GitHub -- a
        # file/Docker-only manifest, or the wrong manifest selected. Proceeding
        # would make every existing secret an "orphan" and hand back a deletion
        # signal built from nothing. Refuse instead.
        raise Unmeasured(f"no `github_secret` targets declared in {path}")
    return routes


def declared_secret_names(manifest: Optional[Path] = None) -> Set[str]:
    """Distinct `github_secret` target names in the v2 CHIT manifest."""
    return {route["name"] for route in declared_routes(manifest)}


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
        # Quoted: an environment name is a path segment, and `--env` is free
        # text from the command line.
        endpoint = f"repos/{repo}/environments/{quote(environment, safe='')}/secrets"
    else:
        endpoint = f"repos/{repo}/actions/secrets"
    out = _gh("api", "--paginate", endpoint, "--jq", ".secrets[].name")
    return {line.strip() for line in out.splitlines() if line.strip()}


def _scope_label(scope: Optional[str]) -> str:
    return f"env:{scope}" if scope else "(repository)"


def _scope_order(scope: Optional[str]):
    """Repository scope first, then environments by name."""
    return (scope is not None, scope or "")


def _fold(scope: Optional[str]) -> Optional[str]:
    """GitHub compares environment names case-insensitively; so does this."""
    return None if scope is None else scope.casefold()


def _audit_repo(
    repo: str,
    unrouted: Set[str],
    pinned: Dict[Optional[str], Set[str]],
    environment: Optional[str],
    takes_unrouted: bool,
) -> Dict[str, Any]:
    """Absent / orphans / capacity for ONE repo.

    `unrouted` are bare names, which may live in any scope read for the caller
    (every scope, or just `environment`). `pinned` maps a scope to the routed
    names the manifest put there; each is looked for in that scope alone.
    """
    discovered = discover_scopes(repo) if environment is None or pinned else None
    if environment is None:
        scopes = list(discovered or [])
    else:
        scopes = [environment] if takes_unrouted else []
    unrouted_scopes = list(scopes)

    # Resolve each pinned scope to the spelling GitHub reports, merging case
    # variants. One GitHub does not have is MISSING: its names are absent -- a
    # measurement, not a failure to measure -- with or without --env.
    canonical = {_fold(s): s for s in (discovered or [])}
    canonical.update({_fold(s): s for s in scopes})
    resolved: Dict[Optional[str], Set[str]] = {}
    missing: List[Optional[str]] = []
    missing_names: Set[str] = set()
    for scope in sorted(pinned, key=_scope_order):
        if _fold(scope) in canonical:
            resolved.setdefault(canonical[_fold(scope)], set()).update(pinned[scope])
        else:
            if _fold(scope) not in {_fold(m) for m in missing}:
                missing.append(scope)
            missing_names |= pinned[scope]
    pinned = resolved
    for scope in sorted(pinned, key=_scope_order):
        if scope not in scopes:
            scopes.append(scope)

    per_scope: List[Dict[str, Any]] = []
    present: Dict[Optional[str], Set[str]] = {}
    union: Set[str] = set()
    for scope in scopes:
        present[scope] = present_secret_names(repo, scope)
        union |= present[scope]
        per_scope.append(
            {
                "scope": _scope_label(scope),
                "present": len(present[scope]),
                "headroom": SECRET_LIMIT - len(present[scope]),
                "at_cap": len(present[scope]) >= SECRET_LIMIT,
            }
        )

    reachable: Set[str] = set()
    for scope in unrouted_scopes:
        reachable |= present[scope]
    absent = {name for name in unrouted if name not in reachable}
    for scope, names in pinned.items():
        absent |= {name for name in names if name not in present.get(scope, set())}
    absent |= missing_names

    # A routed name belongs ONLY in the scope(s) it is pinned to. A copy
    # anywhere else in this repo is stale -- unless the same name is also a
    # bare name here, which may legitimately live in any scope.
    pinned_to: Dict[str, Set[Optional[str]]] = {}
    for scope, names in pinned.items():
        for name in names:
            pinned_to.setdefault(name, set()).add(scope)
    for name in missing_names:
        # Pinned only to a scope that does not exist: every copy is elsewhere.
        pinned_to.setdefault(name, set())
    stale = [
        {"name": name, "scope": _scope_label(scope)}
        for scope in scopes
        for name in sorted(present[scope])
        if name in pinned_to and name not in unrouted and scope not in pinned_to[name]
    ]

    declared = set(unrouted).union(missing_names, *pinned.values())
    return {
        "repo": repo,
        "scopes_read": [_scope_label(s) for s in scopes],
        "missing_scopes": [_scope_label(s) for s in missing],
        "declared": len(declared),
        "present_union": len(union),
        "per_scope": per_scope,
        "absent": sorted(absent),
        "orphans": sorted(union - declared),
        "stale_copies": stale,
    }


def audit(
    repo: str,
    environment: Optional[str] = None,
    manifest: Optional[Path] = None,
) -> Dict[str, Any]:
    routes = declared_routes(manifest)

    # Bare names go wherever the caller pushes them: `repo`, one scope per run.
    # Routed names go where the manifest pins them, repo AND scope.
    unrouted = {r["name"] for r in routes if not r["routed"]}
    # Keyed by the case-folded repo (GitHub's own matching); `display` keeps
    # the first spelling the manifest used.
    pinned: Dict[str, Dict[Optional[str], Set[str]]] = {}
    display: Dict[str, str] = {}
    for r in routes:
        if r["routed"]:
            key = r["repo"].casefold()
            display.setdefault(key, r["repo"])
            pinned.setdefault(key, {}).setdefault(r["env"], set()).add(r["name"])

    # `--env X` asserts "the funnel targets X". Absence is only true under that
    # assertion, so it is carried into the report and stated in the output.
    assumed_single_scope = environment is not None
    main_report = _audit_repo(repo, unrouted, pinned.get(repo.casefold(), {}), environment, True)
    other_repos = [
        _audit_repo(display[other], set(), pinned[other], environment, False)
        for other in sorted(pinned)
        if other != repo.casefold()
    ]

    # The funnel writes ONE scope per run (push-gh-secrets.sh --env), so more
    # declared names than a single scope holds cannot be satisfied by one run.
    # That is the true claim; a bare "over capacity" would not be, since an
    # operator can split the set across scopes over several runs. Only bare
    # names share that scope -- routed ones never land in it.
    single_scope_overflow = max(0, len(unrouted) - SECRET_LIMIT)

    # A pinned scope has no such escape: every name routed to it must fit.
    routed_overflow: List[Dict[str, Any]] = []
    for pinned_repo in sorted(pinned):
        by_scope: Dict[Optional[str], Set[str]] = {}
        spelling: Dict[Optional[str], Optional[str]] = {}
        for scope, names in pinned[pinned_repo].items():
            spelling.setdefault(_fold(scope), scope)
            by_scope.setdefault(_fold(scope), set()).update(names)
        for folded in sorted(by_scope, key=_scope_order):
            count = len(by_scope[folded])
            if count > SECRET_LIMIT:
                routed_overflow.append(
                    {
                        "repo": display[pinned_repo],
                        "scope": _scope_label(spelling[folded]),
                        "declared": count,
                        "over": count - SECRET_LIMIT,
                    }
                )

    ok = (
        not main_report["absent"]
        and not main_report["orphans"]
        and single_scope_overflow == 0
        and not routed_overflow
        and not main_report["stale_copies"]
        and all(
            not r["absent"] and not r["orphans"] and not r["stale_copies"]
            for r in other_repos
        )
    )
    return {
        "repo": repo,
        "scopes_read": main_report["scopes_read"],
        "assumed_single_scope": assumed_single_scope,
        "limit": SECRET_LIMIT,
        "declared": main_report["declared"],
        "present_union": main_report["present_union"],
        "per_scope": main_report["per_scope"],
        "single_scope_overflow": single_scope_overflow,
        "absent": main_report["absent"],
        "orphans": main_report["orphans"],
        "ok": ok,
        "missing_scopes": main_report["missing_scopes"],
        "stale_copies": main_report["stale_copies"],
        "routed_overflow": routed_overflow,
        "other_repos": other_repos,
    }


def _print_repo(report: Dict[str, Any], limit: int) -> None:
    print(f"repo: {report['repo']}")
    if report.get("assumed_single_scope"):
        print(
            f"  scope: {report['scopes_read'][0]} only -- absence below is true ONLY if\n"
            f"    the funnel targets this scope (push-gh-secrets.sh --env)."
        )
    for row in report["per_scope"]:
        flag = "  <- AT CAP" if row["at_cap"] else ""
        print(
            f"  {row['scope']:<24} {row['present']:>3}/{limit}"
            f"  headroom {row['headroom']:>3}{flag}"
        )
    print(
        f"  declared {report['declared']}"
        f"  present across all scopes {report['present_union']}"
    )


def _print_findings(report: Dict[str, Any]) -> None:
    for scope in report["missing_scopes"]:
        print(
            f"  {scope} does not exist in {report['repo']}; every name pinned to it is absent",
            file=sys.stderr,
        )
    if report["absent"]:
        print(
            f"  absent ({len(report['absent'])}): declared, present in NO scope read",
            file=sys.stderr,
        )
        for name in report["absent"][:20]:
            print(f"    {name}", file=sys.stderr)
        if len(report["absent"]) > 20:
            print(f"    ... {len(report['absent']) - 20} more", file=sys.stderr)
    if report["orphans"]:
        print(
            f"  orphans ({len(report['orphans'])}): present, declared nowhere --\n"
            f"    unmanaged by the funnel; reconciling these is free headroom",
            file=sys.stderr,
        )
        for name in report["orphans"][:20]:
            print(f"    {name}", file=sys.stderr)
        if len(report["orphans"]) > 20:
            print(f"    ... {len(report['orphans']) - 20} more", file=sys.stderr)
    if report["stale_copies"]:
        print(
            f"  stale copies ({len(report['stale_copies'])}): routed names also present in a\n"
            f"    scope they are not pinned to -- reclaimable headroom",
            file=sys.stderr,
        )
        for row in report["stale_copies"][:20]:
            print(f"    {row['name']}  {row['scope']}", file=sys.stderr)
        if len(report["stale_copies"]) > 20:
            print(f"    ... {len(report['stale_copies']) - 20} more", file=sys.stderr)


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

    # Everything printed below is a NAME or a COUNT. `gh api .../secrets`
    # returns `.secrets[].name` and no value, so no secret value exists in this
    # process to leak.
    #
    # CodeQL flags the name loops in _print_findings as
    # py/clear-text-logging-sensitive-data:
    # its heuristic taints anything returned by an identifier matching /secret/,
    # so printing the names this tool exists to print will always alert. That is
    # resolved by DISMISSING the alert with this justification, not by a comment
    # marker -- `# lgtm[...]` is LGTM.com syntax that GitHub code scanning
    # ignores. Three lines in launcher_profile_select.py carry that marker and
    # remain open alerts today; do not copy it expecting suppression.
    _print_repo(report, report["limit"])
    if report["single_scope_overflow"]:
        print(
            f"  SINGLE-SCOPE OVERFLOW by {report['single_scope_overflow']}: the manifest\n"
            f"    declares {report['single_scope_overflow'] + report['limit']} names but the funnel writes one scope per run,\n"
            f"    and no scope holds more than {report['limit']}. One run cannot provision them all.",
            file=sys.stderr,
        )
    _print_findings(report)
    for other in report["other_repos"]:
        _print_repo(other, report["limit"])
        _print_findings(other)
    for row in report["routed_overflow"]:
        print(
            f"  PINNED-SCOPE OVERFLOW by {row['over']}: {row['repo']} {row['scope']} declares"
            f" {row['declared']} names,\n"
            f"    and no scope holds more than {report['limit']}.",
            file=sys.stderr,
        )
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
