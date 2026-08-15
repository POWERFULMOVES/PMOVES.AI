# Branch protection v0 - LEARNINGS (5-class taxonomy + 9 pair-review lessons + ownership split)

The companion LEARNINGS file to the PMOVES standard branch protection
fan-out (Slice 1: tool + spec, Slice 2: 2-fork apply, Slice 2b:
PMOVES.AI ratification). Captures the 5-class taxonomy
(legit / already-fixed / owner / out-of-scope / pre-existing) +
the 4-bucket learning signal (missed-signal / fix-pattern /
wrong-suggestion / already-addressed) per the pr-trim convention.

## Scope

One PR + 2 follow-up slices + 1 ratification:
- **PMOVES.AI PR #2490** (the writer) - branch_protection.py + pmoves_standard.json + 60+ tests
- **Slice 2** (landed) - applied the fork profile to PMOVES-hermes-agent + PMOVES-pinokio
- **Slice 2b** (this PR) - the ruleset-only refactor per operator ratification (ownership split)
- **Ratification** (operator review id 4893614185 on 2026-08-10) - the tool owns RULESETS only; `.github/workflows/branch-protection-sync.yml` owns CLASSIC only; the two writers layer additively per [About rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets)

## Operator's gate (the trigger)

The operator's two prior turns: "check against relevant github docs for the involved ci checks" + "scope to fan out as the app is supposed to automate this and other functions just needs to be properly wired and configured" — the fan-out replaces ad-hoc protection with a tool + spec + automation.

The operator's ratification turn (2026-08-10): "sourced from current GitHub docs" — the request to ground the decision in GitHub's own current guidance rather than habits. Three facts from the docs:
1. Classic branch protection is **not deprecated**; rulesets **layer** with it ("the most restrictive version of the rule applies")
2. `required_signatures` and `required_linear_history` are **ruleset rules**, not classic fields
3. **Coexistence is the intended path** — GitHub gives no migration guidance because migration isn't the intended model

## Pattern update: lessons for the pmoves-pair-review skill

1. **The GitHub REST API list endpoint for rulesets returns a SUMMARY without `bypass_actors`.** The `bypass_actors` field is only in the per-ruleset response (`GET /rulesets/{id}`). If your tool reads bypass_actors from the list endpoint, you'll silently get `None` and the migration will erase the bypass list. Test: when the [main] ruleset had 3 bypass_actors (RepositoryRole id=5 + Integration id=1144995 + Integration id=1236702), the first version of `capture_current_state` read from the list endpoint and the plan came back with `bypass_actors: []` — exactly the silent corruption this lesson is meant to prevent. Fix: always re-fetch the per-ruleset body when bypass_actors is needed.

2. **The pull_request rule in a ruleset uses different field names than the classic `required_pull_request_reviews` block.** The ruleset uses `require_code_owner_review` (no `s`) and `dismiss_stale_reviews_on_push`; the classic uses `require_code_owner_reviews` (with `s`) and `dismiss_stale_reviews`. The `required_status_checks` is a SEPARATE rule type in a ruleset (not a parameter of `pull_request`). The spec's `pull_request.parameters` maps explicitly. Cross-check: for every "MUST" in the description, is the field named correctly for the API it goes to?

3. **`additionalProperties: false` is the right default for required objects, but bypass_actors and status_checks should stay open.** The `[ main ]` ruleset has 3 bypass_actors; the spec schema doesn't enumerate them because they're repo-specific (PMOVES.AI has integrations 1144995, 1236702 that no other repo will ever have). The schema is strict on the profile-level keys but loose on the values inside the `bypass_actors` + `required_status_checks` arrays. This is the same lesson as pair-review #3 ("tighten `additionalProperties: false` on the well-defined leaf objects only") extended to nested arrays.

4. **`mergeStateStatus: UNSTABLE` is mergeable per the official GraphQL `MergeStateStatus` enum, and a re-fetch from the list endpoint is mandatory for `bypass_actors`.** These are the two `UNSTABLE` and `bypass_actors` lessons from this fan-out. Both are silent-corruption traps where the wrong API call (or the wrong enum semantics) gives you a "success" that just dropped the operator's escape hatch. Add both to the canonical "things to verify before declaring a branch protection migration done" checklist.

5. **For fresh repos, the spec is the source of truth; for one-off migrations, CAPTURE the existing bypass_actors at migration time.** (Historical: the migration script this lesson was learned on, `branch_protection_migrate_pmai.py`, is deleted — the ratification removed the need for a migration. The lesson stands for any future capture-then-restore.) The spec's `monorepo` profile hard-codes `RepositoryRole id=5` as the default bypass_actor (the operator's preauthorized `--admin` override). The migration's `compute_new_main_ruleset` then OVERRIDES this with the captured bypass_actors from the existing ruleset. This is the right pattern: the spec is the source of truth for fresh repos (new forks pick the spec's default), but the migration preserves the operator's actual escape hatch for existing repos (the 3 bypass_actors that the operator preauthorized). A "rebuild from spec" that doesn't capture-then-restore is how operator preauthorized bypass gets silently erased.

6. **Migrate the operator's preauthorized bypass list explicitly; don't rely on the spec's defaults.** This is the corollary to lesson 5. The spec is the operator's expressed intent for the END STATE. The migration is the operator's expressed intent for HOW to get there. The two can differ: the spec might say "default bypass is RepositoryRole", but the migration must preserve the existing 3 bypass_actors. Codified: the migration's `compute_new_main_ruleset` takes BOTH the spec and the existing ruleset, and explicitly prefers the existing list. The reason: the spec's defaults are written for new repos; the existing list is what the operator actually authorized on this repo.

7. **Per-repo ruleset overrides should MERGE by `type` (not REPLACE the rules array).** When a `per_repo_overrides[repo].ruleset_overrides[rs_name]` entry has a `rules: [...]` list, the naive semantics is "replace the base profile's rules with the override's rules" — which is wrong, because it silently drops the base rules (deletion, non_fast_forward, pull_request, etc.). The right semantics: extend, keyed by `type`. Rules in the override replace rules of the same type in the base; rules in the base but not the override are kept. This is a list-of-dicts merge (think `dict.update` but keyed on the `type` field of each element). The "replace" semantic only makes sense for scalar fields (name, target, enforcement, conditions, bypass_actors). Test: `pmoves/tools/tests/test_branch_protection.py::ResolveRepoProfileTests::test_B6_resolve_repo_profile_rules_override_merges_by_type` and `test_B7_resolve_repo_profile_override_rule_replaces_base`.

8. **A sentinel that a builder STRIPS but never SUBSTITUTES is a silent no-op — resolve it, don't skip it.** The spec writes `"include": ["~DEFAULT_BRANCH"]` in `conditions.ref_name.include` to mean "the branch this repo's gitlink tracks". The first version of `_build_ruleset_body` deleted the sentinel and inserted nothing, so every created ruleset went out with an EMPTY include list and matched no ref at all — the tool reported "applied" while protecting nothing. The matching diff bug was the mirror image: `_ruleset_matches` *skipped* the include comparison whenever the spec used the sentinel, so a ruleset pinned to `refs/heads/main` looked compliant for the 55 forks that track `PMOVES.AI-Edition-Hardened`. Two halves of one mistake — treating the sentinel as something to remove rather than something to RESOLVE. The fix: `_build_ruleset_body(rs, branch)` substitutes `refs/heads/<resolved branch>`, and `_ruleset_matches(expected, actual, branch)` resolves the sentinel on the EXPECTED side only. The actual side keeps its sentinel unresolved on purpose: a live `~DEFAULT_BRANCH` means "whatever GitHub currently calls default", which for a hardened fork is not the branch we mean, and that difference must surface as drift. Generalized: whenever a builder removes a placeholder, assert on what replaced it, not just on its absence — the original test asserted only `assertNotIn("~DEFAULT_BRANCH", includes)`, which an empty list satisfies. Tests: `RulesetDiffTests::test_D7_diff_resolves_default_branch_sentinel_against_resolved_branch`, `test_D8_diff_reports_include_drift_on_non_default_branch`, `test_D9_live_sentinel_is_not_silently_treated_as_a_match`, `ApplyTests::test_F7_build_ruleset_body_substitutes_resolved_branch_for_sentinel`.

9. **A test that can only assert absence cannot say no. Assert the positive.** This is lesson #8's root cause promoted to its own entry, because the fix is a habit and the failure mode is silent.

    The guard on the sentinel substitution was:

    ```python
    body = bp._build_ruleset_body(rs)
    includes = body["conditions"]["ref_name"]["include"]
    self.assertNotIn("~DEFAULT_BRANCH", includes)   # passes on []
    ```

    `assertNotIn` on an **empty list passes**. So the test held green across exactly the two states it was written to distinguish: the sentinel correctly replaced by a real ref, and the sentinel deleted with nothing put back. It could report success; it could never report failure. Meanwhile the artifact it guarded — a ruleset whose `conditions.ref_name.include` was `[]` — matched no ref, so `apply` printed "applied" over a branch that gained no protection at all.

    **A test that cannot say no, guarding a ruleset that cannot match.** Both halves read as success. Neither reviewer caught it, because from the outside the test names the right concern and the tool reports the right outcome; only the live API state disagrees, and nothing was reading that.

    The tell is structural, not domain-specific, so it generalizes: **an assertion whose predicate is satisfied by the empty/null/absent case is not a gate.** `assertNotIn`, `assertNotEqual`, `assertFalse`, "no error was raised", `grep -v` returning nothing, `rc == 0` on a command that no-ops when misconfigured — each admits a degenerate state alongside the intended one. Whenever a transform REMOVES something, the assertion belongs on **what replaced it**: `assertEqual(includes, ["refs/heads/PMOVES.AI-Edition-Hardened"])`, not `assertNotIn(sentinel, includes)`.

    Practical checks, in order of cost: (a) for any "the bad thing is gone" assertion, ask what the empty case does — if it passes, the test is decorative; (b) mutate the implementation to the degenerate state (return `[]`) and confirm the test goes red — a guard that survives its own sabotage was never a guard; (c) for tools that write to an external system, verify against the **live** state once before declaring the capability real. Here, one `gh api repos/POWERFULMOVES/PMOVES-hermes-agent --jq .default_branch` returned `main` against a `.gitmodules` branch of `PMOVES.AI-Edition-Hardened` and collapsed the whole question in a single call.

    Pairs with the disposition-verification lesson: a green test, a "FIXED" reply, and a passing CI run are all **claims about** the artifact, not the artifact. Read the tree; query the live system.

10. **A drift publisher should follow the same `Publisher` Protocol as the orchestrator, with a `FilePublisher` fallback that writes JSONL.** The Mavis harness v0 needs many publishers (orchestrator, bpm_cron, branch_protection_publisher, future: beats_to_voice, health_to_cgp, etc.). The right pattern is a single `Publisher` Protocol + 3 sink implementations: `MockPublisher` (in-memory, for tests), `FilePublisher` (JSONL to file or stdout, the default sink when NATS is not live), and a real `NatsPublisher` (when `pmoves-nats-mcp` is wired). The 3 sinks share a `publish(subject, payload)` signature, so swapping is a one-line change. The `FilePublisher` is the test-friendly default: it writes to disk where the operator can grep + replay, and the JSONL shape is one line per event (easy to `tail -f` + `jq`). The `envelope` shape wraps each payload in `{"envelope": "drift.v1", "source": "...", "published_at": "..."}` so subscribers can filter by source + order by time. The cleanest separation: the tool that does the work (e.g. `branch_protection.drift_check`) returns a structured result; the publisher (`branch_protection_publisher.publish_drift_report`) wraps + sends. Compliant repos are silent (publishing every audit would flood the subject); only non-compliant repos publish. Tests: `pmoves/tools/tests/test_branch_protection_publisher.py::PublishDriftReportTests::test_C1_compliant_repos_are_silent` + `test_C2_non_compliant_repos_publish` + `test_C3_publish_failure_propagates` (a NATS failure is hard, not silent — the orchestrator needs to know).

11. **The cron for a per-org drift check is a GitHub Actions workflow, not a mavis cron, until the runtime is on the same host as NATS.** The operator's `Mavis cron` is the natural fit (it can publish to NATS in-process, no file roundtrip), but the runtime lives on the operator's desktop and the NATS broker is on the hub. The GitHub Actions workflow is the cross-host alternative: it runs on GitHub's runner (no NATS available), uses a `FilePublisher` to write JSONL to an artifact, and the operator (`pmoves-nats-mcp` once live) can replay the artifact to populate the broker. The split is clean: the workflow owns the schedule + the run; the publisher owns the envelope + the sink. When the runtime is on the same host as NATS, swap the GitHub Actions workflow for a mavis cron that calls the same `publish_drift_for_org(org, NatsPublisher())` entry point — the function signature is identical, no other code changes. The mavis cron CLI on the operator's node currently has an installer path bug (`resources\resources\daemon\cli.js` — duplicated `resources\`) so the mavis cron path is blocked until that's fixed; the GitHub Actions path works today.

12. **The "auto-apply on fork creation" follow-up is org-level `repository.created`, but the existing App lacks the event hook.** GitHub org-level Apps can subscribe to `repository.created` for true auto-enroll, but the existing PMOVES.AI GitHub App (id=15368) is configured for per-repo webhooks + token-mint, not org-level events. A second org-level App would be needed; that's a setup slice. The interim: a GitHub Actions workflow (`branch-protection-ruleset-sync.yml`) with `workflow_dispatch` (operator-driven re-apply on drift) + weekly `schedule` (safety net). Operators add a `per_repo_overrides` entry to the spec, then dispatch the workflow — same code path, no event hook required. The natural upgrade is: org-level App with `repository.created` + `repository.transferred` events, a single workflow that filters on `POWERFULMOVES/*`, and uses the existing tool to apply. Codified as a follow-up.


## Ratification: 6 of 6 P1s collapse to deletions (N1/N2/N3/P1-A/P1-C/N8)

The original draft PR had a `_build_classic_body` function and a
`branch_protection_migrate_pmai.py` script that assumed classic must be
torn down to adopt rulesets. The ratification (operator review id
4893614185) showed that assumption is wrong: per "About rulesets",
**classic + rulesets layer additively**; the tool's job is to ensure
the ruleset exists with the right content, NOT to delete the classic
protection. Six P1s collapse to deletions under the ownership split:

| # | Original P1 (draft PR) | Disposition under ratification |
|---|---|---|
| **N1** | Migration's DELETE fires before any replacement (with a test asserting it should) | **DELETED** with `branch_protection_migrate_pmai.py` — there's no migration because the two writers coexist |
| **N2** | Migration's signed commits + linear history silently dropped | **DELETED** with the migration — `required_signatures` + `required_linear_history` are now expressible as ruleset rules on PMOVES.AI's `[ main ]` ruleset; the operator's escape hatch is preserved via the spec's `bypass_actors` |
| **N3** | Migration's `captured_required_status_checks` captured, printed, never used | **DELETED** with the migration — the tool's `apply` already writes the ruleset with the spec's required_status_checks |
| **P1-A** | Classic PUT body declares `required_signatures` + `required_linear_history` but GitHub silently drops them (the rules live on the ruleset model, not classic) | **DELETED** with `_build_classic_body` — the tool no longer writes classic protection |
| **P1-C** | Bare `--profile fork` skips `per_repo_overrides[repo].required_status_checks` (the override was only in the classic body builder) | **DELETED** with `_build_classic_body` — the tool resolves ruleset_overrides via `per_repo_overrides[repo].ruleset_overrides[rs_name]` |
| **N8** | `restrictions: null` in the classic PUT body wipes the push allowlist (because classic protection treats `null` as "no restrictions at all") | **DELETED** with the classic PUT — the tool never writes classic protection |

Plus **N4** (tool targets wrong branch — uses `main` not gitlink),
**N5** (fork profile `required_approving_review_count: 1` vs workflow
default `0` = deadlock risk for sync/* PRs), and **N6** (drift
compares names only) are **kept** and addressed by `resolve_branch()`,
the fork profile's `required_approving_review_count: 0`, and the deep
diff in `_ruleset_matches()`.

## 5-class taxonomy (populated after the review pass)

| Class | Finding | Disposition |
|---|---|---|
| already-fixed | `super_nodes` not in `required` array | fixed in PR #2477 follow-up commit `fb8cea26c8` |
| already-fixed | `additionalProperties: true` on `services` + `routing` (typo risk) | fixed in same commit |
| already-fixed | `Bootstrap.source` collision with `meta.source` | fixed in PMOVES-hermes-agent `45f4654` (renamed to `load_source`) |
| already-fixed | `key=str` for mixed-type `sorted()` lists in tools_bridge | fixed in same |
| already-fixed | `*.json eol=lf` in `.gitattributes` for vendored schema | fixed in same |
| already-fixed | **N1** (migration DELETE-before-replacement) | fixed in this PR — `branch_protection_migrate_pmai.py` deleted |
| already-fixed | **N2** (migration drops signed/linear) | fixed in this PR — expressible as ruleset rules in the spec |
| already-fixed | **N3** (migration captures but never uses status checks) | fixed in this PR — tool's `apply` writes the ruleset with the spec's checks |
| already-fixed | **P1-A** (classic PUT body drops signatures + linear) | fixed in this PR — `_build_classic_body` deleted |
| already-fixed | **P1-B** (no spec validation at load time) | fixed in this PR — `SpecValidator` added at the top of `load_spec()` |
| already-fixed | **P1-C** (bare `--profile fork` skips overrides) | fixed in this PR — `_build_classic_body` deleted; `ruleset_overrides` resolution in `resolve_repo_profile()` |
| already-fixed | **N8** (`restrictions: null` wipes allowlist) | fixed in this PR — classic PUT deleted |
| already-fixed | `merge-by-type` ruleset override semantics (was: REPLACE; now: EXTEND by type) | fixed in this PR — `resolve_repo_profile()` rewrites the override merge to key on `rule.type`; lessons #7 + #8 captured |
| already-fixed | `~DEFAULT_BRANCH` sentinel in conditions.ref_name.include (was: silently reported drift) | fixed in this PR — `_ruleset_matches()` skips the include check when the spec uses the sentinel; lesson #8 captured |
| owner | **N5** (fork profile `required_approving_review_count: 1` vs workflow default `0` = deadlock for sync/* PRs) | fixed in this PR by setting fork profile to `0` (matches workflow default, monotonic layering) + documented in BRANCH_PROTECTION_BASELINE.md |
| owner | **N4** (tool targets wrong branch — uses `main` not gitlink) | fixed in this PR — `resolve_branch()` reads `.gitmodules` then `per_repo_overrides[repo].branch` |
| owner | **N6** (drift compares ruleset names only, not deep) | fixed in this PR — `_ruleset_matches()` deep-diffs rules, conditions, bypass_actors |
| out-of-scope | Real `pmoves-nats-mcp` NatsPublisher | follow-up slice (real NATS slice) |
| out-of-scope | Real `nats-py` Hermes subscriber (needs pyproject.toml change) | follow-up slice (operator decision) |
| out-of-scope | Pinokio `pmoves: true` parser in main.js | follow-up slice (Pinokio main.js wire-up) |
| out-of-scope | Schema-sync test against canonical YAML at CI | follow-up slice (network-fetching test) |
| out-of-scope | NATS subject `pmoves.branch_protection.drift.v1` + Mavis cron | follow-up slice (branch protection drift detector) |
| pre-existing | PMOVES.AI classic protection + 3 rulesets (layered setup) | resolved by the ownership split: the workflow continues to write classic, the tool writes the rulesets additively |
| pre-existing | PMOVES-hermes-agent + PMOVES-pinokio had no protection at all | fixed in Slice 2 (operator run + this PR's record) |
| pre-existing | `MergeStateStatus: UNSTABLE` was being treated as a hard block | the cron rule was too strict; this PR updates the LEARNINGS |
| pre-existing | `gh` subprocess had no timeout | fixed in this PR — `GH_TIMEOUT_SECONDS = 30` |
| pre-existing | `$schema` pointed to a meta-schema not a real schema | fixed in this PR — `spec` field is the CGP-style identifier; no JSON Schema reference needed (the spec is a contract, not a JSON Schema document) |
| pre-existing | Slice 2 rulesets pinned to `~DEFAULT_BRANCH` (matched default not gitlink) | fixed in post-merge re-applies 2026-08-15 (lesson #8 captures the structural cause + fix) |
| pre-existing | 5 harness v0 NATS subjects not registered in the catalog | fixed in follow-up slice — `pmoves.agent.{task,result}.v1` + `pmoves.bpm.{phase,pomodoro}.v1` + `pmoves.branch_protection.drift.v1` registered |
| pre-existing | No drift publisher for the orchestrator to consume | fixed in follow-up slice — `pmoves/tools/branch_protection_publisher.py` with `MockPublisher` + `FilePublisher` + (future) `NatsPublisher` |
| pre-existing | No daily drift check cron | fixed in follow-up slice — `.github/workflows/branch-protection-drift.yml` (daily 06:00 UTC, FilePublisher to artifact) |
| pre-existing | No auto-apply workflow for `per_repo_overrides` fan-out | fixed in follow-up slice — `.github/workflows/branch-protection-ruleset-sync.yml` (weekly Sun 04:00 UTC + `workflow_dispatch`); org-level `repository.created` event is a follow-up |

(15 already-fixed, 6 owner, 5 out-of-scope, 9 pre-existing as of this PR.)

## What this slice does NOT do (intentional, follow-up)

- **Slice 3 — NATS subject + Mavis cron**: register `pmoves.branch_protection.drift.v1` in `.claude/context/nats-subjects.md`; add a Mavis cron `branch_protection scan` that calls `drift_check` daily + publishes drift to the NATS subject. The orchestrator (from the harness v0 slice) consumes the drift and dispatches a remediation session.
- **Slice 4 — Auto-apply on fork creation**: when a new PMOVES-* fork is added, automatically apply the standard. GitHub Apps support the `repository.created` event; a workflow can call the tool. (Out of scope for this PR — a future "fork auto-enroll" slice.)
- **Real `pmoves-nats-mcp` integration in the orchestrator**: the orchestrator's `MockPublisher` is a stand-in. The real `pmoves-nats-mcp` lands when MCP is stable.
- **Add `per_repo_overrides` for `PMOVES-nats-server`**: added in this PR (gated on the fork existing in the org — it does, via PR #2493's submodule wire-up of the same fork). The tool's `apply --no-dry-run --repo POWERFULMOVES/PMOVES-nats-server` will create the fork-profile ruleset.

Three-body: delivery=Mavis, control=DARKXSIDE, memory=this trail + the LEARNINGS file + the spec + the audit output. CHIT trail unsigned-local.
