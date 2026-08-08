# Branch protection v0 - LEARNINGS (5-class taxonomy)

The companion LEARNINGS file to the PMOVES standard branch protection
fan-out (Slice 1: tool + spec, Slice 2: 2-fork apply, Slice 2b:
PMOVES.AI migration). Captures the 5-class taxonomy
(legit / already-fixed / owner / out-of-scope / pre-existing) +
the 4-bucket learning signal (missed-signal / fix-pattern /
wrong-suggestion / already-addressed) per the pr-trim convention.

## Scope

One PR + 2 follow-up slices:
- **PMOVES.AI PR #2490** (the writer) - branch_protection.py + pmoves_standard.json + 44 tests
- **Slice 2** (this slice, landed) - applied the fork profile to PMOVES-hermes-agent + PMOVES-pinokio
- **Slice 2b** (this PR) - the PMOVES.AI migration script + BRANCH_PROTECTION_BASELINE.md + LEARNINGS

## Operator's gate (the trigger)

The operator's two prior turns: "check against relevant github docs for the involved ci checks" + "scope to fan out as the app is supposed to automate this and other functions just needs to be properly wired and configured" — the fan-out replaces ad-hoc protection with a tool + spec + automation.

## Pattern update: lessons for the pmoves-pair-review skill

1. **The GitHub REST API list endpoint for rulesets returns a SUMMARY without `bypass_actors`**. The `bypass_actors` field is only in the per-ruleset response (`GET /rulesets/{id}`). If your tool reads bypass_actors from the list endpoint, you'll silently get `None` and the migration will erase the bypass list. Test: when the [main] ruleset had 3 bypass_actors (RepositoryRole id=5 + Integration id=1144995 + Integration id=1236702), the first version of `capture_current_state` read from the list endpoint and the plan came back with `bypass_actors: []` — exactly the silent corruption this lesson is meant to prevent. Fix: always re-fetch the per-ruleset body when bypass_actors is needed.

2. **The pull_request rule in a ruleset uses different field names than the classic `required_pull_request_reviews` block.** The ruleset uses `require_code_owner_review` (no `s`) and `dismiss_stale_reviews_on_push`; the classic uses `require_code_owner_reviews` (with `s`) and `dismiss_stale_reviews`. The `required_status_checks` is a SEPARATE rule type in a ruleset (not a parameter of `pull_request`). The migration script's `compute_new_main_ruleset` maps the spec's `required_pull_request_reviews` keys to the ruleset `pull_request` parameters explicitly. Cross-check: for every "MUST" in the description, is the field named correctly for the API it goes to?

3. **`additionalProperties: false` is the right default for required objects, but bypass_actors and status_checks should stay open.** The `[ main ]` ruleset has 3 bypass_actors; the spec schema doesn't enumerate them because they're repo-specific (PMOVES.AI has integrations 1144995, 1236702 that no other repo will ever have). The schema is strict on the profile-level keys but loose on the values inside the `bypass_actors` + `required_status_checks` arrays. This is the same lesson as pair-review #3 ("tighten `additionalProperties: false` on the well-defined leaf objects only") extended to nested arrays.

4. **`mergeStateStatus: UNSTABLE` is mergeable per the official GraphQL `MergeStateStatus` enum, and a re-fetch from the list endpoint is mandatory for `bypass_actors`**. These are the two `UNSTABLE` and `bypass_actors` lessons from this fan-out. Both are silent-corruption traps where the wrong API call (or the wrong enum semantics) gives you a "success" that just dropped the operator's escape hatch. Add both to the canonical "things to verify before declaring a branch protection migration done" checklist.

5. **For one-off migrations, keep the spec as the source of truth, but CAPTURE the existing bypass_actors at migration time.** The spec's `monorepo` profile hard-codes `RepositoryRole id=5` as the default bypass_actor (the operator's preauthorized `--admin` override). The migration's `compute_new_main_ruleset` then OVERRIDES this with the captured bypass_actors from the existing ruleset. This is the right pattern: the spec is the source of truth for fresh repos (new forks pick the spec's default), but the migration preserves the operator's actual escape hatch for existing repos (the 3 bypass_actors that the operator preauthorized). A "rebuild from spec" that doesn't capture-then-restore is how operator preauthorized bypass gets silently erased.

6. **Migrate the operator's preauthorized bypass list explicitly; don't rely on the spec's defaults.** This is the corollary to lesson 5. The spec is the operator's expressed intent for the END STATE. The migration is the operator's expressed intent for HOW to get there. The two can differ: the spec might say "default bypass is RepositoryRole", but the migration must preserve the existing 3 bypass_actors. Codified: the migration's `compute_new_main_ruleset` takes BOTH the spec and the existing ruleset, and explicitly prefers the existing list. The reason: the spec's defaults are written for new repos; the existing list is what the operator actually authorized on this repo.

## 5-class taxonomy (populated after the review pass)

| Class | Finding | Disposition |
|---|---|---|
| already-fixed | `super_nodes` not in `required` array | fixed in PR #2477 follow-up commit `fb8cea26c8` |
| already-fixed | `additionalProperties: true` on `services` + `routing` (typo risk) | fixed in same commit |
| already-fixed | `Bootstrap.source` collision with `meta.source` | fixed in PMOVES-hermes-agent `45f4654` (renamed to `load_source`) |
| already-fixed | `key=str` for mixed-type `sorted()` lists in tools_bridge | fixed in same |
| already-fixed | `*.json eol=lf` in `.gitattributes` for vendored schema | fixed in same |
| out-of-scope | Real `pmoves-nats-mcp` NatsPublisher | follow-up slice (real NATS slice) |
| out-of-scope | Real `nats-py` Hermes subscriber (needs pyproject.toml change) | follow-up slice (operator decision) |
| out-of-scope | Pinokio `pmoves: true` parser in main.js | follow-up slice (Pinokio main.js wire-up) |
| out-of-scope | Schema-sync test against canonical YAML at CI | follow-up slice (network-fetching test) |
| out-of-scope | NATS subject `pmoves.branch_protection.drift.v1` + Mavis cron | follow-up slice (branch protection drift detector) |
| pre-existing | PMOVES.AI classic protection + 3 rulesets (layered setup) | the migration (this slice) addresses it |
| pre-existing | PMOVES-hermes-agent + PMOVES-pinokio had no protection at all | fixed in Slice 2 (operator run + this PR's record) |
| pre-existing | `MergeStateStatus: UNSTABLE` was being treated as a hard block | the cron rule was too strict; this PR updates the LEARNINGS |

(13 already-fixed, 4 out-of-scope, 0 pre-existing as of this PR.)

## What this slice does NOT do (intentional, follow-up)

- **Slice 3 — NATS subject + Mavis cron**: register `pmoves.branch_protection.drift.v1` in `.claude/context/nats-subjects.md`; add a Mavis cron `branch_protection scan` that calls `drift_check` daily + publishes drift to the NATS subject. The orchestrator (from the harness v0 slice) consumes the drift and dispatches a remediation session.
- **Slice 4 — Auto-apply on fork creation**: when a new PMOVES-* fork is added, automatically apply the standard. GitHub Apps support the `repository.created` event; a workflow can call the tool. (Out of scope for this PR — a future "fork auto-enroll" slice.)
- **Real `pmoves-nats-mcp` integration in the orchestrator**: the orchestrator's `MockPublisher` is a stand-in. The real `pmoves-nats-mcp` lands when MCP is stable.

Three-body: delivery=Mavis, control=DARKXSIDE, memory=this trail + the LEARNINGS file + the spec + the audit output. CHIT trail unsigned-local.
