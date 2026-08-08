# PMOVES branch protection baseline

**Status:** enforced via `pmoves/tools/branch_protection.py` (the canonical
tool) + the JSON spec at `pmoves/configs/branch_protection/pmoves_standard.json`.
**Last updated:** 2026-08-08.

The PMOVES standard for how every repo in the org's main branches are
protected. The spec is the single source of truth — drift from the spec
is reported on `pmoves.branch_protection.drift.v1` (NATS subject, see
[`.claude/context/nats-subjects.md`](../nats-subjects.md)) by the Mavis
cron `branch_protection scan`.

## Why a baseline

The 3-PR review pass (PMOVES.AI #2477 + PMOVES-hermes-agent #4 +
PMOVES-pinokio #1) shipped the CGP bootstrap contract — same schema,
3 implementations. But the SECURITY POSTURE was wildly asymmetric:

- PMOVES.AI: 4 required status checks + reviews + linear history +
  signatures + 3 rulesets ([main] + pmoves rules + tag-protection)
- PMOVES-hermes-agent: **no protection at all** (HTTP 404 from
  `gh api .../branches/main/protection`)
- PMOVES-pinokio: **no protection at all** (HTTP 404 from
  `gh api .../branches/main/protection`)

The Hermes PR #4 was admin-merged only because there was no
required gate to be met. That's a bug-as-feature, not a designed
protection. This baseline fixes the asymmetry: the operator's
preauthorized `--admin` for hot lanes is preserved, but every repo
in the org now has at least the minimum required gate (status
check + 1 reviewer + linear history + conversation resolution).

## Profiles

Two profiles cover the PMOVES org's needs. New forks pick `fork` unless
they need a more specific shape; that decision is the operator's.

### `monorepo` — the PMOVES.AI profile

The full-power profile. Used for the monorepo only.

| Field | Value | Why |
|---|---|---|
| `required_status_checks.strict` | true | strict mode requires branch up to date before merge (per [About protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches#require-status-checks-before-merging)) |
| `required_status_checks.checks` | `merge-gate`, `python-tests`, `hardening-validation`, `verify`, `submodule-gitlink-gate` | the 5 required gates from the PMOVES GitHub App (id=15368) |
| `required_pull_request_reviews.dismiss_stale_reviews` | true | reviews dismiss on push (prevents "approved but stale" merges) |
| `required_pull_request_reviews.require_code_owner_reviews` | true | CODEOWNERS must approve any path-touching PR |
| `required_pull_request_reviews.required_approving_review_count` | 1 | minimum bar; CODEOWNERS may require more on specific paths |
| `required_linear_history` | true | squash or rebase merge only; no merge commits (per About protected branches) |
| `required_signatures` | true | all commits to main must be signed (per About protected branches) |
| `required_conversation_resolution` | true | all PR comment threads must resolve before merge (per About protected branches) |
| `enforce_admins` | false | operator preauthorized `--admin` for hot lanes; admins can bypass via the `[ main ]` ruleset's `bypass_actors` list |
| `allow_force_pushes` | false | no force-pushes to main (per About protected branches) |
| `allow_deletions` | false | main is not deletable (per About protected branches) |
| `[ main ]` ruleset | yes | the modern ruleset shape (per [About rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets)) — rules layer with classic protection, "the most restrictive version of the rule applies" |
| `[ main ]` `bypass_actors` | 3 (operator RepositoryRole + 2 Integrations) | preserved from the existing [main] ruleset (RepositoryRole id=5, Integration id=1144995, Integration id=1236702) |
| `pmoves rules` ruleset | yes | legacy — basic deletion + non-FF (operator-managed) |
| `tag-protection` ruleset | yes | tag immutability (the operator's release tag policy) |

### `fork` — the PMOVES-* profile (forks)

The minimum-protection profile for downstream forks. Used for
PMOVES-hermes-agent, PMOVES-pinokio, and any future PMOVES-* fork.

| Field | Value | Why |
|---|---|---|
| `required_status_checks.strict` | true | same as monorepo |
| `required_status_checks.checks` | **per-repo override** (e.g. CodeRabbit for Pinokio, 9 checks for Hermes) | each fork's CI is different; the override is the per-fork required check list |
| `required_pull_request_reviews.dismiss_stale_reviews` | true | same as monorepo |
| `required_pull_request_reviews.require_code_owner_reviews` | false | forks don't have a CODEOWNERS file yet |
| `required_pull_request_reviews.required_approving_review_count` | 1 | one human approval is enough |
| `required_linear_history` | true | same as monorepo |
| `required_signatures` | **false** | forks often receive upstream commits that aren't signed by the fork's contributors |
| `required_conversation_resolution` | true | same as monorepo |
| `enforce_admins` | false | same rationale as monorepo |
| `allow_force_pushes` | false | same as monorepo |
| `allow_deletions` | false | same as monorepo |
| `[ main ]` ruleset | yes | same shape as monorepo's, minus the Copilot rule (forks don't have Copilot) |
| `bypass_actors` | none | forks have no Copilot integration, no PMOVES GitHub App |

## Current state per repo (as of 2026-08-08)

| Repo | Profile | Compliant | Notes |
|---|---|---|---|
| `POWERFULMOVES/PMOVES.AI` | monorepo | no (classic + 3 rulesets, layered) | migration to rulesets-only is the pending follow-up; see "PMOVES.AI migration" below |
| `POWERFULMOVES/PMOVES-hermes-agent` | fork | **yes** (just applied) | the 9 required status checks + [main] ruleset (id=20589548) were created in Slice 2 |
| `POWERFULMOVES/PMOVES-pinokio` | fork | **yes** (just applied) | CodeRabbit required + [main] ruleset (id=20589542) were created in Slice 2 |

## How to apply / audit / drift-check

```bash
# Audit a single repo (dry-run by default, prints the would-be API calls)
python -m pmoves.tools.branch_protection audit --repo POWERFULMOVES/PMOVES.AI

# Apply the spec to a repo (dry-run by default; --no-dry-run to actually issue)
python -m pmoves.tools.branch_protection apply --repo POWERFULMOVES/PMOVES-hermes-agent
python -m pmoves.tools.branch_protection apply --repo POWERFULMOVES/PMOVES.AI --no-dry-run

# Drift-check the whole org (audits every repo in per_repo_overrides)
python -m pmoves.tools.branch_protection drift-check --org POWERFULMOVES
```

## How to add a new repo

1. Add an entry to `per_repo_overrides` in `pmoves_standard.json`:
   ```json
   "POWERFULMOVES/PMOVES-newrepo": {
     "profile": "fork",
     "required_status_checks": {
       "strict": true,
       "checks": [
         { "context": "your-check-1" },
         { "context": "your-check-2" }
       ]
     }
   }
   ```
2. Run `apply --no-dry-run --repo POWERFULMOVES/PMOVES-newrepo`
3. The drift-check cron picks it up on the next run

## How to add a new profile

If `monorepo` and `fork` don't cover your case, add a new profile to
`profiles` in `pmoves_standard.json`. The validator enforces the
schema, so a typo in a profile key fails before the tool hits the
network.

## PMOVES.AI migration (Option A, pending)

The operator approved Option A: drop classic branch protection,
consolidate the status check + review requirements into the `[ main ]`
ruleset, preserve the bypass_actor list, keep `pmoves rules` and
`tag-protection` as-is.

The migration script `pmoves/tools/branch_protection_migrate_pmai.py`
implements this. The current dry-run plan is:

- DELETE `/repos/POWERFULMOVES/PMOVES.AI/branches/main/protection` (the classic protection)
- PUT `/repos/POWERFULMOVES/PMOVES.AI/rulesets/10887588` with the new
  body: deletion + non_fast_forward + pull_request (1 reviewer +
  code owner review + dismiss stale + review thread resolution) +
  copilot_code_review + required_status_checks (5 checks) + 3
  bypass_actors (preserved)

This is a one-off migration. After it runs, the canonical
`branch_protection.py apply` tool keeps the ruleset in sync with
the spec.

## Wire-up to the harness

The branch protection tool is part of the PMOVES harness:

- `pmoves/tools/load_bootstrap.py` (harness v0) can declare the
  profile assignment in the bootstrap CGP
- `pmoves/tools/branch_protection.py` audit/apply is the runtime
- The Mavis cron `branch_protection scan` (Slice 3 follow-up) calls
  `drift_check` daily + publishes to `pmoves.branch_protection.drift.v1`
- The orchestrator (from the harness v0 slice) can dispatch a
  remediation session when drift is detected

## References

- [GitHub Docs — About rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets) — the modern protection model; "the most restrictive version of the rule applies"
- [GitHub Docs — About protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches) — the classic model; `enforce_admins`, `required_status_checks.strict`, etc.
- [GitHub Docs — Troubleshooting required status checks](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks) — strict vs loose, name-collision pitfalls
- [GraphQL `MergeStateStatus` enum](https://docs.github.com/v4/enum/mergestatestatus) — `UNSTABLE` = "mergeable with non-passing commit status; merge is still allowed"
- `pmoves/tools/LEARNINGS/mavis-harness-v0-multi-fork_LEARNINGS.md` — the pattern-update LEARNINGS from the 3-PR review pass (where the harness + protection fan-out started)
