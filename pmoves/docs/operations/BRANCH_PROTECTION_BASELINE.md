# PMOVES branch protection baseline

**Status:** enforced via `pmoves/tools/branch_protection.py` (the canonical
**ruleset** tool) + the JSON spec at `pmoves/configs/branch_protection/pmoves_standard.json`.
**Last updated:** 2026-08-10 (post-ratification: ownership split with `branch-protection-sync.yml`).

The PMOVES standard for how every repo in the org's main branches are
protected. The spec is the single source of truth — drift from the spec
is reported on `pmoves.branch_protection.drift.v1` (NATS subject, see
[`.claude/context/nats-subjects.md`](../nats-subjects.md)) by the Mavis
cron `branch_protection scan`.

## Ownership split (the post-ratification model)

Per the operator's 2026-08-10 ratification (GitHub review id 4893614185 on
PR #2490), grounded in GitHub's own "About rulesets" docs, branch protection
is split between **two writers** that coexist additively:

| Writer | Owns | Touches |
|---|---|---|
| `.github/workflows/branch-protection-sync.yml` | **Classic** branch protection (PUT/DELETE `/branches/{branch}/protection`) | `enforce_admins`, `required_pull_request_reviews`, `required_status_checks`, `required_linear_history`, `required_signatures`, `required_conversation_resolution`, `restrictions`, `allow_force_pushes`, `allow_deletions` |
| `pmoves/tools/branch_protection.py` (this tool) | **Rulesets** only (POST/PUT `/rulesets`, `/rulesets/{id}`) | All the same rules — but expressed as `rules[]` entries on a `[ main ]` ruleset |

Per [About rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets):

> "rulesets also layer with protection rules targeting the same branch or tag"
> "if the same rule is defined in different ways across the aggregated rulesets, **the most restrictive version of the rule applies**"
> "you can start using rulesets **without overriding any of your existing protection rules**"

That monotonicity is the property the operator's ratification was sourcing:
**additive adoption can only make a branch stricter, never weaker**. There
is no downgrade failure mode, no "ruleset migration" to plan, and no need
for a `branch_protection_migrate_pmai.py` step (the original Option A
migration script in the draft PR is deleted in this slice — N1, N2, N3
collapse per the ratification).

The two writers **do not know each other exists**. The workflow derives
the fork list from `.gitmodules` and writes classic protection; the tool
reads `per_repo_overrides` and writes rulesets. They layer, per
"the most restrictive version of the rule applies". Drift detection
(`drift_check`) only audits the ruleset side; classic is the workflow's
responsibility.

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
protection. This baseline fixes the asymmetry: every repo
in the org now has at least the minimum ruleset (deletion + non-FF +
pull_request with 0 reviewers — the workflow writes the human-review
gate via classic on top).

## Profiles

Two profiles cover the PMOVES org's needs. New forks pick `fork` unless
they need a more specific shape; that decision is the operator's.

### `monorepo` — the PMOVES.AI profile

The full-power profile. Used for the monorepo only. Expressed as a
`[ main ]` ruleset whose rules layer on top of whatever classic
protection `branch-protection-sync.yml` writes.

| Ruleset rule | Parameters | Why |
|---|---|---|
| `deletion` | (n/a) | main is not deletable |
| `non_fast_forward` | (n/a) | no force-pushes to main |
| `required_signatures` | (n/a) | all commits to main must be signed (per [About rulesets — available rules](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets)) |
| `require_linear_history` | (n/a) | squash or rebase merge only; no merge commits |
| `required_conversation_resolution` | (n/a) | all PR comment threads must resolve before merge |
| `copilot_code_review` | (n/a) | the operator uses Copilot for the first pass |
| `required_status_checks` | strict; 5 checks (`merge-gate`, `python-tests`, `hardening-validation`, `verify`, `submodule-gitlink-gate`) | the 5 required gates from the PMOVES GitHub App (id=15368) |
| `pull_request` | `require_code_owner_review: true`, `dismiss_stale_reviews_on_push: true`, `required_approving_review_count: 1`, `required_review_thread_resolution: true` | CODEOWNERS must approve; reviews dismiss on push; minimum 1 human approval |
| `bypass_actors` | `RepositoryRole id=5` (operators) | the operator's preauthorized `--admin` override |

The most-restrictive-wins layering means the workflow's classic
`required_approving_review_count=0` (so automation can self-merge hot
lanes) is dominated by the ruleset's 1 — humans must approve. The
operator's `--admin` override still works (it bypasses both writers).

### `fork` — the PMOVES-* profile (forks)

The minimum-protection ruleset for downstream forks. Used for
PMOVES-hermes-agent, PMOVES-pinokio, PMOVES-nats-server, and any
future PMOVES-* fork.

| Ruleset rule | Parameters | Why |
|---|---|---|
| `deletion` | (n/a) | main is not deletable |
| `non_fast_forward` | (n/a) | no force-pushes to main |
| `pull_request` | `require_code_owner_review: false`, `dismiss_stale_reviews_on_push: true`, `required_approving_review_count: 0`, `required_review_thread_resolution: true` | matches the workflow's classic `required_approving_review_count=0` default to avoid sync/* PR deadlock (per #2490 review N5); the operator can override per_repo_overrides to bump a specific fork to 1 |
| `bypass_actors` | (none) | forks have no PMOVES GitHub App, no Copilot integration |

Forks that need required status checks (PMOVES-pinokio needs `CodeRabbit`,
PMOVES-hermes-agent needs 9 checks) add a `required_status_checks` rule
via `per_repo_overrides[repo].ruleset_overrides`.

## Current state per repo (as of 2026-08-10)

| Repo | Profile | Ruleset state | Notes |
|---|---|---|---|
| `POWERFULMOVES/PMOVES.AI` | monorepo | 3 rulesets (well-configured) | classic protection is layered on top by the workflow; the tool's `apply --no-dry-run` would CREATE the monorepo's `[ main ]` ruleset as a 4th — most-restrictive-wins makes that monotonic |
| `POWERFULMOVES/PMOVES-hermes-agent` | fork | 1 ruleset id=20589548 + 9 status checks | classic (9 required status checks) + ruleset (deletion + non-FF + pull_request) |
| `POWERFULMOVES/PMOVES-pinokio` | fork | 1 ruleset id=20589542 + CodeRabbit | classic (CodeRabbit required) + ruleset (deletion + non-FF + pull_request) |
| `POWERFULMOVES/PMOVES-nats-server` | fork | (no ruleset yet) | spec entry added 2026-08-10; `apply --no-dry-run` will create the fork-profile ruleset. Fork lives in the PMOVES org; submodule wire-up is a separate PR (#2493) |

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

The tool writes **rulesets only** — never classic. Classic protection
is the workflow's responsibility.

## How to add a new repo

1. Add an entry to `per_repo_overrides` in `pmoves_standard.json`:
   ```json
   "POWERFULMOVES/PMOVES-newrepo": {
     "profile": "fork",
     "branch": "main",
     "ruleset_overrides": {
       "[ main ]": {
         "rules": [
           {
             "type": "required_status_checks",
             "parameters": {
               "required_status_checks": [{ "context": "your-check-1" }],
               "strict_required_status_checks_policy": true
             }
           }
         ]
       }
     }
   }
   ```
2. Run `apply --no-dry-run --repo POWERFULMOVES/PMOVES-newrepo`
3. The drift-check cron picks it up on the next run

The spec validator (`SpecValidator` in `branch_protection.py`) enforces
the schema, so a typo in a profile key fails before the tool hits the
network. The branch resolution also reads `.gitmodules` (matching the
workflow's logic) — so for forks that track `PMOVES.AI-Edition-Hardened`
as the gitlink branch, the tool writes to the right branch automatically.

## How to add a new profile

If `monorepo` and `fork` don't cover your case, add a new profile to
`profiles` in `pmoves_standard.json`. The validator enforces the
schema, so a typo in a profile key fails before the tool hits the
network.

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

- [GitHub Docs — About rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets) — the modern protection model; "the most restrictive version of the rule applies", "start using rulesets without overriding any of your existing protection rules"
- [GitHub Docs — Available rules for rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets) — the ruleset-rule catalog (deletion, non_fast_forward, required_signatures, require_linear_history, required_conversation_resolution, copilot_code_review, required_status_checks, pull_request, etc.)
- [GitHub Docs — About protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches) — the classic model (the workflow's domain)
- [GraphQL `MergeStateStatus` enum](https://docs.github.com/v4/enum/mergestatestatus) — `UNSTABLE` = "mergeable with non-passing commit status; merge is still allowed"
- `pmoves/tools/LEARNINGS/mavis-harness-v0-multi-fork_LEARNINGS.md` — the pattern-update LEARNINGS from the 3-PR review pass (where the harness + protection fan-out started)
- `pmoves/tools/LEARNINGS/branch-protection-v0_LEARNINGS.md` — this PR's LEARNINGS (5-class taxonomy + 6 pair-review lessons + ownership-split ratification)
