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
  5. Every registry fork with `sync: true` is actually reachable by the
     fork-sync workflow: it must appear in the workflow's `FORKS=` block
     AND in the GitHub App token's `repositories:` scope block. This is the
     registry -> workflow half of the cross-check. Without it, `sync: true`
     is a CLAIM with no mechanism behind it -- exactly the gap the pipecat
     fork provenance audit measured on 2026-10-30
     (pmoves/docs/services/PIPECAT_FORK_PROVENANCE_AUDIT_2026-10-30.md,
     gap 1): six registered `sync: true` forks were in neither workflow
     list, and the ratchet still exited 0.

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
WORKFLOW_PATH = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "fork-sync.yml"

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


def _workflow_app_scope(workflow_text: str) -> set[str]:
    """Repo names in the GH App token scope block (`repositories: |`).

    Parsed as TEXT, not YAML: this tool imports only the stdlib, and a YAML
    dependency would make a static gate fail for a missing optional package.
    The block is a literal scalar whose entries are one repo per line, more
    indented than the `repositories:` key.
    """
    names: set[str] = set()
    in_block = False
    key_indent = 0
    for raw in workflow_text.splitlines():
        stripped = raw.strip()
        if not in_block:
            if stripped.startswith("repositories:"):
                in_block = True
                key_indent = len(raw) - len(raw.lstrip())
            continue
        if not stripped:
            continue
        indent = len(raw) - len(raw.lstrip())
        if indent <= key_indent:
            break
        names.add(stripped)
    return names


def _workflow_forks(workflow_text: str) -> set[str]:
    """Fork names in the workflow's `FORKS="..."` block.

    The block holds one `upstream|fork|branch_override` entry per line, so
    the fork name is the second field. Parsed as TEXT (see
    _workflow_app_scope).
    """
    names: set[str] = set()
    in_block = False
    for raw in workflow_text.splitlines():
        stripped = raw.strip()
        if not in_block:
            if stripped.startswith('FORKS="'):
                in_block = True
            continue
        if stripped.startswith('"'):
            break
        if not stripped or "|" not in stripped:
            continue
        parts = stripped.split("|")
        if len(parts) >= 2 and parts[1]:
            names.add(parts[1])
    return names


def _validate_workflow_coverage(registry: dict, workflow_path: Path) -> list[str]:
    """Cross-check the registry against .github/workflows/fork-sync.yml.

    The registry and the workflow are two INDEPENDENT hand-maintained lists.
    The registry says a fork should be synced; the workflow is what actually
    syncs it. Nothing tied them together, so a `sync: true` could exist with
    no mechanism behind it -- a claim the ratchet (rules 1-3) reported as
    "decided". The pipecat fork provenance audit measured six such forks
    (gap 1 of
    pmoves/docs/services/PIPECAT_FORK_PROVENANCE_AUDIT_2026-10-30.md):
    registered `sync: true`, absent from the workflow's FORKS block AND from
    the GitHub App token scope.

    A `sync: true` fork therefore must appear in BOTH workflow lists:
      - the `FORKS="..."` block, which is what the sync step iterates over;
      - the GH App `repositories:` scope, which is what the minted token is
        scoped to. A fork in FORKS but not in the scope gets a token that
        cannot touch it -- a silent no-op, not a visible failure.

    Deliberately NOT the converse: a fork in the workflow but absent from
    the registry is a different (and legitimate) state -- the workflow may
    sync a fork the registry has not decided about yet, and flagging that
    would train people to ignore the gate.
    """
    problems: list[str] = []
    if not workflow_path.exists():
        return [f"workflow not found: {workflow_path}"]

    text = workflow_path.read_text(encoding="utf-8")
    scope = _workflow_app_scope(text)
    forks = _workflow_forks(text)

    for name, entry in (registry.get("forks") or {}).items():
        if entry.get("sync") is not True:
            continue
        if name not in forks:
            problems.append(
                f"{name}: registry says sync: true but it is not in the "
                f"FORKS block of {workflow_path.name} — the workflow will "
                "never sync it. Add it to FORKS, or set sync: false."
            )
        if name not in scope:
            problems.append(
                f"{name}: registry says sync: true but it is not in the "
                f"GitHub App 'repositories:' scope of {workflow_path.name} — "
                "the minted token cannot reach it. Add it to the scope "
                "block, or set sync: false."
            )

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
    parser.add_argument(
        "--workflow",
        type=Path,
        default=WORKFLOW_PATH,
        help=f"Path to fork-sync.yml for the registry->workflow coverage cross-check (default: {WORKFLOW_PATH})",
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

    # The workflow coverage cross-check asserts a relationship between a
    # registry and the workflow that is supposed to implement it, so the
    # same category error applies as the .gitmodules cross-check above: an
    # ARBITRARY registry file compared against the repo's REAL workflow makes
    # every fork in it report as "missing from the workflow" -- noise, not
    # signal. That one mismatched pairing is therefore skipped.
    #
    # Every COHERENT pairing is checked: this repo's own registry + workflow
    # (the CI case), this repo's registry against a candidate workflow (what
    # --workflow is for), and an explicitly matched custom registry + custom
    # workflow. The last one is what makes the negative control in
    # pmoves/tools/tests/test_fork_registry_ratchet.py runnable end to end:
    # a ratchet whose gap-detection path can only be exercised against the
    # repo's own files is a ratchet that cannot prove it can say no.
    workflow_checked = not (
        args.registry.resolve() != REGISTRY_PATH.resolve()
        and args.workflow.resolve() == WORKFLOW_PATH.resolve()
    )
    if workflow_checked:
        problems += _validate_workflow_coverage(registry, args.workflow)

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
        "workflow": str(args.workflow),
        "workflow_cross_check": workflow_checked,
        # The comment above says BRANCH_MISSING_BUDGET "may only be lowered --
        # lower it whenever one of those four gets triaged". It was computed and
        # then dropped on the floor: absent from this payload and from the
        # human output, so nothing ever told an operator the count had fallen
        # and the budget could come down. A ratchet whose current value is
        # invisible cannot be ratcheted; it just sits at its initial number.
        "branch_missing": branch_missing,
        "branch_missing_budget": BRANCH_MISSING_BUDGET,
    }

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"fork-registry ratchet: {coverage} decided")
        if branch_missing < BRANCH_MISSING_BUDGET:
            print(
                f"  branch coverage: {branch_missing} missing, budget "
                f"{BRANCH_MISSING_BUDGET} — LOWER BRANCH_MISSING_BUDGET to "
                f"{branch_missing}"
            )
        else:
            print(
                f"  branch coverage: {branch_missing} missing "
                f"(budget {BRANCH_MISSING_BUDGET})"
            )
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
            if workflow_checked:
                print("  (every sync:true fork is in the workflow FORKS block and "
                      "the GH App scope)")
            else:
                print("  (workflow cross-check skipped — non-default registry "
                      "against the default workflow)")

    # 0 problems = pass; any problem = fail (the ratchet only goes down).
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
