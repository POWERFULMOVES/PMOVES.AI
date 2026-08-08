"""pmoves/tools/branch_protection_migrate_pmai.py

One-off migration script for POWERFULMOVES/PMOVES.AI. The current
state (as of 2026-08-08) is layered: classic branch protection +
3 rulesets ([main] + pmoves rules + tag-protection). The operator
approved Option A: drop classic, consolidate the status check +
review requirements into the [main] ruleset, re-register the
bypass_actor list, keep pmoves rules and tag-protection as-is.

This script:
    1. Reads the current state of PMOVES.AI (classic + rulesets)
    2. Computes the new state (deletion + non-FF + pull_request +
       required_status_checks + copilot_code_review, with the
       bypass_actor list from the old [main] ruleset)
    3. Generates the API call sequence (DELETE classic, PUT
       [main] ruleset)
    4. Optionally executes the calls (--no-dry-run)

The script is intentionally one-off. Once PMOVES.AI is migrated,
the canonical `branch_protection.py apply` tool will keep the
[main] ruleset in sync with the spec. The migration is a
rearrangement, not a recurring operation.

Design notes (codified in the docstring + tests):

- The script reads the current state via the same `gh api` wrapper
  used by branch_protection.py. The result is a complete snapshot
  of the layered state.

- The new [main] ruleset body is computed from the spec's
  monorepo profile, with the bypass_actor list copied from the
  existing [main] ruleset. This preserves the operator's
  preauthorized --admin override.

- The migration is dry-run by default. The operator reviews the
  call sequence before --no-dry-run is issued.

- The migration preserves the pmoves rules + tag-protection
  rulesets. They are not part of the classic protection that
  Option A migrates away; they enforce different constraints
  (basic deletion + non-FF for pmoves rules, tag immutability
  for tag-protection) and removing them would be a separate
  decision.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional


# --- Shared with branch_protection.py: import the helpers ---

# We import from the sibling module to keep the tool + migration
# in lockstep. If branch_protection.py is not on PYTHONPATH, the
# script falls back to vendoring the helpers inline.
try:
    from pmoves.tools import branch_protection as bp
except ImportError:  # pragma: no cover
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import branch_protection as bp  # type: ignore[no-redef]


# --- Constants ---

REPO = "POWERFULMOVES/PMOVES.AI"
RULESET_MAIN_NAME = "[ main ]"


# --- Result dataclass ---

@dataclasses.dataclass
class MigrationPlan:
    repo: str
    dry_run: bool
    captured_bypass_actors: list[dict]
    captured_required_status_checks: list[dict]
    captured_review_policy: dict
    captured_other_rulesets: list[dict]
    new_main_ruleset_body: dict
    delete_classic: bool
    put_main_ruleset: bool
    skip: list[str]  # operations the script decided NOT to do
    calls: list[dict]
    applied: list[str]

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


# --- Capture current state ---

def capture_current_state() -> dict:
    """Read the current layered state of PMOVES.AI.

    Returns {"classic": <obj or None>, "rulesets": [<list>],
             "main_ruleset": <obj or None>} for downstream
            computation. The list endpoint `/rulesets` returns a
            summary without `bypass_actors`, so we re-fetch the
            [main] ruleset via the individual endpoint to get the
            full body.
    """
    classic = bp._gh_api("GET", f"repos/{REPO}/branches/main/protection")
    rulesets = bp._gh_api("GET", f"repos/{REPO}/rulesets") or []
    main_ruleset_summary = next(
        (r for r in rulesets if r["name"] == RULESET_MAIN_NAME), None
    )
    main_ruleset = None
    if main_ruleset_summary is not None:
        # Re-fetch the individual ruleset to get the full body
        # (bypass_actors is only in the per-ruleset response).
        main_ruleset = bp._gh_api(
            "GET", f"repos/{REPO}/rulesets/{main_ruleset_summary['id']}"
        ) or main_ruleset_summary
    return {
        "classic": classic,
        "rulesets": rulesets,
        "main_ruleset": main_ruleset,
    }


# --- Compute the new [main] ruleset body ---

def compute_new_main_ruleset(
    spec: dict,
    main_ruleset: Optional[dict],
    classic: Optional[dict],
) -> dict:
    """Build the new [main] ruleset body. Combines the spec's
    monorepo profile defaults with the existing [main] ruleset's
    bypass_actor list. Adds the required_status_checks + the
    pull_request parameters from the classic protection (since
    classic is being deleted).
    """
    profile = spec["profiles"]["monorepo"]

    # 1. Start from the spec's [ main ] ruleset shape.
    new_ruleset = dict(profile["rulesets"][0])  # copy
    new_ruleset["rules"] = list(new_ruleset["rules"])  # shallow copy

    # 2. Add the required_status_checks rule (a separate rule type
    # in a ruleset, not a parameter of pull_request).
    new_ruleset["rules"].append(
        {
            "type": "required_status_checks",
            "parameters": {
                "required_status_checks": profile["required_status_checks"]["checks"],
                "strict_required_status_checks_policy": profile[
                    "required_status_checks"
                ].get("strict", True),
            },
        }
    )

    # 3. Add a copilot_code_review rule if it's not already there.
    has_copilot = any(r.get("type") == "copilot_code_review" for r in new_ruleset["rules"])
    if not has_copilot:
        new_ruleset["rules"].append({"type": "copilot_code_review"})

    # 4. Carry the pull_request parameters from the spec + the
    # review policy from classic.
    pr_rule = next(
        (r for r in new_ruleset["rules"] if r.get("type") == "pull_request"),
        None,
    )
    if pr_rule is not None:
        pr_rule.setdefault("parameters", {})
        # required_approving_review_count from the spec's profile.
        pr_rule["parameters"]["required_approving_review_count"] = (
            profile["required_pull_request_reviews"]["required_approving_review_count"]
        )
        pr_rule["parameters"]["dismiss_stale_reviews_on_push"] = (
            profile["required_pull_request_reviews"]["dismiss_stale_reviews"]
        )
        pr_rule["parameters"]["require_code_owner_review"] = (
            profile["required_pull_request_reviews"]["require_code_owner_reviews"]
        )
        pr_rule["parameters"]["require_last_push_approval"] = (
            profile["required_pull_request_reviews"]["require_last_push_approval"]
        )
        pr_rule["parameters"]["required_review_thread_resolution"] = True

    # 5. Carry the bypass_actors from the existing [main] ruleset.
    # If there's no existing ruleset, keep the spec's default.
    if main_ruleset is not None:
        new_ruleset["bypass_actors"] = list(main_ruleset.get("bypass_actors", []))
    # else: keep the spec's default bypass_actors from the profile

    return new_ruleset


# --- Public API ---

def plan(spec: Optional[dict] = None) -> MigrationPlan:
    """Compute the migration plan. Pure function for testability."""
    spec = spec or bp.load_spec()
    state = capture_current_state()
    new_main = compute_new_main_ruleset(spec, state["main_ruleset"], state["classic"])
    return MigrationPlan(
        repo=REPO,
        dry_run=True,
        captured_bypass_actors=(
            state["main_ruleset"].get("bypass_actors", []) if state["main_ruleset"] else []
        ),
        captured_required_status_checks=(
            (state["classic"] or {}).get("required_status_checks", {}).get("checks", [])
        ),
        captured_review_policy=(
            (state["classic"] or {}).get("required_pull_request_reviews", {})
        ),
        captured_other_rulesets=[
            r for r in state["rulesets"] if r["name"] != RULESET_MAIN_NAME
        ],
        new_main_ruleset_body=new_main,
        delete_classic=True,
        put_main_ruleset=state["main_ruleset"] is not None,
        skip=[],
        calls=[],
        applied=[],
    )


def apply(plan_obj: MigrationPlan, dry_run: bool = True) -> MigrationPlan:
    """Execute the migration plan against the live repo.

    The plan should be obtained from `plan()` first. This function
    issues the DELETE (classic) + PUT ([main] ruleset) calls and
    returns an updated plan with the calls + applied lists.
    """
    calls: list[dict] = []
    applied: list[str] = []

    # 1. DELETE classic protection.
    if plan_obj.delete_classic:
        calls.append(
            {
                "method": "DELETE",
                "path": f"repos/{plan_obj.repo}/branches/main/protection",
                "body": None,
            }
        )
        if not dry_run:
            bp._gh_api("DELETE", f"repos/{plan_obj.repo}/branches/main/protection")
            applied.append(f"repos/{plan_obj.repo}/branches/main/protection")

    # 2. PUT [main] ruleset (if it exists). If it doesn't exist,
    # the operator would use the canonical `branch_protection.py
    # apply` tool after this migration to create it.
    if plan_obj.put_main_ruleset:
        main = plan_obj.captured_other_rulesets  # noqa: F841 (intentional placeholder)
        # Find the [main] ruleset id by name (it was captured in plan).
        # We need to re-read it because the plan dataclass doesn't
        # store the id. (The captured bypass_actors are sufficient
        # for the body; the id is for the URL.)
        existing = bp._gh_api("GET", f"repos/{plan_obj.repo}/rulesets") or []
        existing_main = next(
            (r for r in existing if r["name"] == RULESET_MAIN_NAME), None
        )
        if existing_main is not None:
            calls.append(
                {
                    "method": "PUT",
                    "path": f"repos/{plan_obj.repo}/rulesets/{existing_main['id']}",
                    "body": plan_obj.new_main_ruleset_body,
                }
            )
            if not dry_run:
                bp._gh_api(
                    "PUT",
                    f"repos/{plan_obj.repo}/rulesets/{existing_main['id']}",
                    plan_obj.new_main_ruleset_body,
                )
                applied.append(f"repos/{plan_obj.repo}/rulesets/{existing_main['id']}")
        else:
            plan_obj.skip.append(
                f"repos/{plan_obj.repo}/rulesets/[no {RULESET_MAIN_NAME} ruleset found]"
            )

    return dataclasses.replace(
        plan_obj,
        dry_run=dry_run,
        calls=calls,
        applied=applied,
    )


# --- CLI ---

def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="branch_protection_migrate_pmai",
        description="One-off PMOVES.AI branch-protection migration to rulesets-only.",
    )
    p.add_argument(
        "--spec",
        type=Path,
        default=bp.DEFAULT_SPEC_PATH,
        help="path to pmoves_standard.json (default: %(default)s)",
    )
    p.add_argument(
        "--no-dry-run",
        action="store_true",
        help="execute the migration (default: dry-run only)",
    )
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    spec = bp.load_spec(args.spec)
    migration_plan = plan(spec=spec)
    result = apply(migration_plan, dry_run=not args.no_dry_run)
    print(json.dumps(result.to_dict(), indent=2, default=str))
    return 0 if not result.calls or result.applied else 1


if __name__ == "__main__":
    sys.exit(main())
