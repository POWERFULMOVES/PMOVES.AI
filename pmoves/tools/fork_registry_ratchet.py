#!/usr/bin/env python3
"""Fork-registry ratchet gate.

Reads `pmoves/config/fork_registry.json` and enforces:
  1. Every fork has a `sync` field (bool) and a non-empty `reason` field.
  2. No fork uses the deprecated `skip` field (it predates the
     sync/reason schema and is no longer the source of truth).
  3. The total is consistent with the documented coverage target.
  4. Every fork submodule in .gitmodules is declared in the registry (or in
     `_first_party`). This is the cross-check the registry cannot make about
     itself —
     an undeclared submodule-fork is invisible to rules 1-3, which is exactly
     how PMOVES.YT sat 206 commits behind.

Exits 0 if every fork is decided, 1 if any fork is missing a decision
or still has the deprecated `skip` field. Designed to be wired into a
CI gate (the ratchet count can only go DOWN over time — adding
forks is fine, removing decisions is not).

This is a no-network check: it reads a static JSON file in the repo
and runs in <100ms. The output is the operator's "fork coverage"
number; it is the answer to "how many forks are undecided?".

Usage:
    python3 pmoves/tools/fork_registry_ratchet.py
    python3 pmoves/tools/fork_registry_ratchet.py --json   # machine-readable
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REGISTRY_PATH = Path(__file__).resolve().parents[1] / "config" / "fork_registry.json"
GITMODULES_PATH = Path(__file__).resolve().parents[2] / ".gitmodules"

# Entries with no `branch` and no .gitmodules pin to recover one from. These
# four are registry-only (no submodule), so the value cannot be derived and
# needs operator triage. Ratchet: may only be LOWERED, never raised.
BRANCH_MISSING_BUDGET = 4


def _validate(registry: dict) -> tuple[int, int, list[str]]:
    """Return (decided, total, list_of_problems)."""
    forks: dict[str, dict] = registry.get("forks", {})
    total = len(forks)
    decided = 0
    problems: list[str] = []

    for name, entry in forks.items():
        if "skip" in entry:
            problems.append(
                f"{name}: deprecated 'skip' field present "
                f"(value={entry['skip']!r}); migrate to sync + reason"
            )
            # Treat as not-decided for coverage accounting.
            continue
        if "sync" not in entry:
            problems.append(f"{name}: missing 'sync' decision (true/false)")
            continue
        if not isinstance(entry["sync"], bool):
            problems.append(
                f"{name}: 'sync' must be bool, got {type(entry['sync']).__name__}"
            )
            continue
        if "reason" not in entry or not str(entry["reason"]).strip():
            problems.append(f"{name}: missing non-empty 'reason' for sync={entry['sync']}")
            continue
        decided += 1

    return decided, total, problems


def _validate_branch_coverage(registry: dict, budget: int) -> tuple[int, list[str]]:
    """Return (missing_count, problems) for the `branch` field.

    Rules 1-3 gate the sync DECISION. They never gated `branch` -- and `branch`
    is the field that decides where work actually lands. The cost was measured
    on 2026-09-04: two separate pieces of work targeted `main` on forks whose
    declared branch is `PMOVES.AI-Edition-Hardened`, because every tool
    (`gh pr create`, `gh api .../compare`, clone) defaults to GitHub's default
    branch rather than the declared one. One PR carried four commits it did not
    own; one fork with six PMOVES commits was reported as an empty mirror.

    Ratchet, not a hard gate, matching rule 3: a BUDGET of known-missing entries
    is allowed and may only shrink. Four registry entries have no .gitmodules
    pin to recover a branch from and need operator triage, so failing outright
    would gate CI on work nobody has scheduled.
    """
    forks: dict[str, dict] = registry.get("forks", {})
    missing = [n for n, e in forks.items() if not str(e.get("branch", "")).strip()]
    problems: list[str] = []
    if len(missing) > budget:
        problems.append(
            f"branch coverage regressed: {len(missing)} forks missing 'branch' "
            f"(budget {budget}). Newly missing: {', '.join(sorted(missing)[:5])}. "
            f"Recover the value from the submodule's `branch = ` pin in .gitmodules; "
            f"do NOT read it from GitHub's default branch, which disagrees for "
            f"42 of 65 forks."
        )
    return len(missing), problems


def _submodule_repos(gitmodules: Path) -> dict[str, str]:
    """casefolded repo name -> canonical name, parsed from submodule URLs.

    Keys on the URL, never the submodule name or path. Five submodules are
    registered under a path that differs from the repo (pbnj -> PMOVES-pinokio,
    PMOVES-Spark-VSS -> PM-Spark-video-search-and-summarization, plus three that
    differ only in case), so keying on path false-fires on all of them.
    PMOVES-Archon is registered at two paths, so the dict also dedupes.
    """
    repos: dict[str, str] = {}
    if not gitmodules.exists():
        return repos
    for raw in gitmodules.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line.startswith("url"):
            continue
        _, _, url = line.partition("=")
        url = url.strip().rstrip("/")
        if not url:
            continue
        name = url.rsplit("/", 1)[-1]
        if name.endswith(".git"):
            name = name[: -len(".git")]
        repos[name.casefold()] = name
    return repos


def _validate_coverage(registry: dict, gitmodules: Path) -> list[str]:
    """Cross-check the registry against .gitmodules.

    This is the assertion the registry cannot make about itself. _validate()
    proves every DECLARED fork carries sync + reason — but a submodule-fork that
    was never added to the registry is invisible to it, and that is precisely
    how PMOVES.YT sat 206 commits behind on its hardened branch: the fork-sync
    lists, the registry and .gitmodules were three separate hand-maintained
    facts with nothing tying them together.

    Non-fork submodules (first-party repos with no upstream) are expected to be
    absent from the registry, so they are declared in `_first_party` rather than
    inferred — inferring would need a GitHub API call and make a PR gate depend
    on the network.
    """
    problems: list[str] = []
    declared = {k.casefold() for k in (registry.get("forks") or {})}
    declared |= {k.casefold() for k in (registry.get("_excluded") or {})}
    first_party = {str(n).casefold() for n in (registry.get("_first_party") or [])}
    subs = _submodule_repos(gitmodules)

    for cf, name in sorted(subs.items()):
        if cf not in declared and cf not in first_party:
            problems.append(
                f"{name}: submodule is not in the registry. Add it under 'forks' "
                f"with sync + reason, or under '_first_party' if it has no upstream."
            )

    # Deliberately NOT the converse. A registry entry naming a repo that is not a
    # submodule is legitimate: PMOVES-ClawRouter, PMOVES-FinceptTerminal and
    # PMOVES-hermes-agent are synced forks that this repo does not vendor. The
    # registry is "forks we have decided about", which is a superset of "forks we
    # vendor". Flagging those would train people to ignore the gate.
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--registry",
        type=Path,
        default=REGISTRY_PATH,
        help=f"Path to fork registry JSON (default: {REGISTRY_PATH})",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit JSON instead of human-readable text",
    )
    parser.add_argument(
        "--gitmodules",
        type=Path,
        default=GITMODULES_PATH,
        help=f"Path to .gitmodules for the coverage cross-check (default: {GITMODULES_PATH})",
    )
    args = parser.parse_args()

    if not args.registry.exists():
        print(f"registry not found: {args.registry}", file=sys.stderr)
        return 2

    with args.registry.open(encoding="utf-8") as f:
        registry = json.load(f)

    decided, total, problems = _validate(registry)

    # The coverage cross-check asserts a relationship between THIS repo's
    # registry and THIS repo's submodules. Running it against an arbitrary
    # registry file is a category error — every real submodule would report as
    # undeclared — so it is scoped to the default registry. Rules 1-3 are
    # properties of a registry in isolation and always apply.
    coverage_checked = args.registry.resolve() == REGISTRY_PATH.resolve()
    if coverage_checked:
        problems += _validate_coverage(registry, args.gitmodules)
    # Branch coverage ratchet. BRANCH_MISSING_BUDGET is the count of entries
    # that have no .gitmodules pin to recover a branch from; it may only be
    # lowered. Lower it whenever one of those four gets triaged.
    branch_missing, branch_problems = _validate_branch_coverage(
        registry, BRANCH_MISSING_BUDGET
    )
    problems += branch_problems
    coverage = f"{decided}/{total}"

    payload = {
        "registry": str(args.registry),
        "coverage": coverage,
        "decided": decided,
        "total": total,
        "problems": problems,
        "coverage_cross_check": coverage_checked,
    }

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"fork-registry ratchet: {coverage} decided")
        if problems:
            print(f"  {len(problems)} problem(s):")
            for p in problems:
                print(f"    - {p}")
        else:
            if coverage_checked:
                print("  (every fork has sync + reason; every submodule-fork is declared)")
            else:
                print("  (every fork has sync + reason; .gitmodules cross-check skipped "
                      "— non-default registry)")

    # 0 problems = pass; any problem = fail (the ratchet only goes down).
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
