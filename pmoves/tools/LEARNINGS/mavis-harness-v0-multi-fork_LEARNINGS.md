# Mavis harness v0 - multi-fork consumer follow-ups (LEARNINGS)

The companion LEARNINGS file to the AGNOTE follow-up row + the
3-PR review pass row. Captures the 5-class taxonomy
(legit / already-fixed / owner / out-of-scope / pre-existing) +
the 4-bucket learning signal (missed-signal / fix-pattern /
wrong-suggestion / already-addressed) per the pr-trim convention.

## Scope

Two DRAFT PRs (companion to PMOVES.AI PR #2477) + the
PMOVES.AI side:

- **PMOVES.AI PR #2477** (writer) - load_bootstrap + orchestrator + bpm_cron
- **POWERFULMOVES/PMOVES-hermes-agent PR #4** (agent) - pmoves_bootstrap/ package
- **POWERFULMOVES/PMOVES-pinokio PR #1** (app launcher) - pmoves_loader/ + example app

## 3-PR review pass (2026-08-08)

The operator's flag "prs need review by pr review agent team"
triggered the `pmoves-pair-review` skill + 3 parallel `verifier`
agent tasks. All 3 reviews: APPROVE-WITH-NITS. 14 observations
surfaced total, 13 pre-merge cleanup candidates (~50 lines across
the 3 PRs) + 1 observation per the operator's "approve to admin
merge" directive.

### 5-class taxonomy (populated after the review pass)

| PR | Class | Finding | Disposition |
|---|---|---|---|
| #2477 | legit (contract-correctness) | `super_nodes` not in the top-level `required` array despite the description saying "MUST"; a CGP without the field would pass validation | **already-fixed** in commit `fb8cea26c8` - added to required + added `test_missing_super_nodes_rejected` |
| #2477 | legit (defense-in-depth) | `additionalProperties: true` at top + on `meta`/`services`/`routing`/`tools` silently accepts typo'd keys (e.g. `pmoves-bnats-mcp`) | **already-fixed** in commit `fb8cea26c8` - tightened to `false` on `services` + `routing` + added `test_typo_service_name_rejected` |
| #2477 | legit (semantic-naming) | `spec` key means "protocol version" in CGP v1.0 but "profile identifier" in the new schema (same envelope, different semantics) | **out-of-scope** (multi-fork follow-up: the 2 schemas have different purposes; document the divergence in a follow-up) |
| #2477 | legit (reasoning) | `Orchestrator.dispatch()` computes `deadline` but never uses it; `_receive_result()` raises `NotImplementedError` - a real `NatsPublisher` subscriber will hit the footgun | **out-of-scope** (real `NatsPublisher` impl is a follow-up slice) |
| #2477 | nit | AGNOTE `mavis-harness-v0` CLAIM says "7 commits" but the branch has 8 (off-by-one vs PR body) | **already-fixed** in commit `fb8cea26c8` (the AGNOTE follow-up row is the 8th; the original "7 commits" reference was the PR #2477 pre-AGNOTE state) |
| #1 | legit (reasoning) | `readFromPath` failure fall-through - explicit `opts.path` to a missing file silently uses the default | **already-fixed** in commit `5a5e24c` - the catch now re-throws on `opts.path`/`opts.source`; added `test_C1b` + `test_C1c` |
| #1 | legit (semantic-naming) | `pmoves: true` / `pmoves_services` in `pinokio.yml` are no-op in this PR; pinokio.yml comment overstates the flag's effect | **out-of-scope** (main.js wire-up is a follow-up slice; the flag becomes load-bearing when main.js reads it) |
| #1 | legit (contract-correctness) | Test-count drift in file header (22 vs 24) + groups count (7 vs 6+1) | **already-fixed** in commit `5a5e24c` - updated to 24 / 7 (A-F + Internal helpers) |
| #1 | legit (defense-in-depth) | Comma-joined env var is lossy if a tool name contains `,`; no character-set constraint | **out-of-scope** (the CGP schema's `tools.items.type: string` already enforces string; the comma-join is a lossy detail that's a follow-up if any tool name actually contains a comma - none of the 10 in the example do) |
| #1 | legit (defense-in-depth) | Stub sets `PMOVES_BOOTSTRAP_RUSTDESK_DEVICES=""` (set, not unset) when rustdesk.devices is empty; downstream `split(',')` produces `[""]` | **already-fixed** in commit `5a5e24c` - guard changed to `length > 0`; same fix applied to `CLOUDFLARE_ZONES` |
| #1 | nit | Stub bootstrap uses hard-coded `created_at: '1970-01-01T00:00:00+00:00'` so SHA-256(canonical_json) collides across processes | **out-of-scope** (depends on whether a downstream consumer ever derives session IDs from the stub - the example doesn't, so it's a theoretical concern) |
| #4 | legit (reasoning) | `_validate_cgp` is a hand-rolled subset of vendored JSON Schema; docstring claim "validated against the vendored JSON Schema" is misleading; a CGP with `constraints: ["make-coffee"]` is silently accepted; a CGP with `tools: ["gh", {"inject": "evil"}, 42]` crashes the bridge with TypeError | **partially-fixed** in commit `45f4654` - added the 2-line guard in `register_pmoves_tools` to skip non-string `tool_id`; the constraint-side validation gap is **out-of-scope** (jsonschema is in scope, but the structural fallback would need a real schema validator to catch `["make-coffee"]` - acceptable trade-off documented in the loader README) |
| #4 | legit (contract-correctness) | Vendored YAML example is not byte-identical to canonical; vendored file is documented as a "canary fixture" but no schema-sync test exists | **out-of-scope** (schema-sync test is a follow-up; it requires a network fetch from the canonical at test time, which is a CI design decision) |
| #4 | legit (semantic-naming) | `Bootstrap.source` (load-source) and `Bootstrap.meta.source` (producer) share a name with different meanings | **already-fixed** in commit `45f4654` - renamed to `Bootstrap.load_source`; updated 5 call sites in the test file |
| #4 | legit (defense-in-depth) | `register_pmoves_tools` should defend against non-string `tool_id` | **already-fixed** in commit `45f4654` - 2-line guard; new test `test_G7_non_string_tool_id_does_not_crash_bridge` |
| #4 | nit (line endings) | Vendored `v1.schema.json` is CRLF (Windows checkout artifact); canonical is LF; SHA-256 matches after normalization | **already-fixed** in commit `45f4654` - added `pmoves_bootstrap/cgp_schema/*.json text eol=lf` to `.gitattributes` |
| #4 | cleanup | Three dead imports in `loader.py:29-33` (`re`, `sys`, `Iterable`); test count drift in docstrings (31 vs 33, 8 vs 9) | **already-fixed** in commit `45f4654` |

### 4-bucket learning signal

- **missed-signal (the ones the producer missed):**
  - PMOVES.AI side: the schema's `super_nodes` description said "MUST" but the validator didn't enforce it - the producer read the description as informative rather than normative. The fix is to treat schema `description` fields as normative unless marked "advisory" (a meta-rule for schema authors).
  - PMOVES-pinokio side: the test file header had a hand-counted "22 tests" that drifted to 24 - the producer added tests without updating the header. The fix is to either generate the count from a script (CI) or accept the drift and document the discrepancy in the README.
  - PMOVES-hermes-agent side: `Bootstrap.source` collided with `meta.source` but neither was named distinctly - the producer was focused on the structural correctness, not the semantic distinguishability. The fix is to use domain-specific names: `load_source` for where the CGP came from, leave `source` for the producer.

- **fix-pattern (the ones the reviewer should look for in future):**
  - "is the schema's `description` field enforced by the validator?" - the schema author writes descriptions, the validator author writes checks; the gap is in the intersection.
  - "is the optional/required distinction reflected in the code's null-handling?" - the structural-check fallback treated the missing field as OK; the `required` array didn't catch it.
  - "do attribute names collide across nested structures?" - `source` exists at both the Bootstrap level and inside `meta`; both have different meanings.

- **wrong-suggestion (the ones the reviewer got wrong):**
  - None this round. The verifier stayed in the 4-class observation taxonomy and didn't propose design changes.

- **already-addressed (the ones the producer caught before the reviewer):**
  - The fork consumer PRs both correctly vendored the schema (SHA-256 byte-identical to canonical after the CRLF strip). The producer of the consumer PRs ran the same byte-compare the reviewer would have run.

## Pattern update: lessons for the pmoves-pair-review skill

1. **Byte-compare vendored schemas.** When a PR vendors a schema (file copy), the reviewer should byte-compare it against the canonical source via `gh api repos/<org>/<repo>/contents/<path>` and SHA-256 hash. The Pinokio fork and the Hermes fork both survived this check (byte-identical), which is the highest-confidence signal that the fork is in sync.

2. **Force the producer to update the schema's `required` array when the description says "MUST".** Schema descriptions that read as normative ("must", "required", "always") should be enforced by the `required` array; descriptions that read as advisory ("advisory", "optional", "if present") can stay out. The reviewer should cross-check: for every "MUST" in a description, is the field in `required`?

3. **Tighten `additionalProperties: false` on the well-defined object types only.** Top-level + the open-extension objects (`meta`, `tools`, `mcps`, `routing` as a list of future agents) should stay `additionalProperties: true` for forward-compat. The well-defined leaf objects (`services.tailscale`, `services.rustdesk`, etc.) should be `additionalProperties: false` to catch typos.

4. **Byte-compare with CRLF normalization.** On Windows checkouts, the vendored copy of a JSON file often picks up CRLF. The SHA-256 won't match between CRLF and LF copies, even though the content is identical. The fix: add `text eol=lf` to `.gitattributes` for vendored JSON files. The reviewer should normalize before comparing.

5. **The `key=str` trick for mixed-type sorted lists.** When a loader skips malformed entries to a list, the list might end up with mixed types (str + int + None). `sorted()` on mixed types raises TypeError. Use `sorted(list, key=str)` to sort by string representation. The Hermes bridge's `LOG.info(skipped)` was crashing on this; the fix was 1 character.

## What this slice does NOT do (intentional, follow-up)

- **Real `pmoves-nats-mcp` NatsPublisher** - the `Orchestrator._receive_result()` NotImplementedError + the unused `deadline` are real footguns for the production NATS path. Follow-up slice.
- **Schema-sync test for vendored YAML** - the fork YAML example is not byte-checked at CI time. Follow-up: a test that fetches the canonical from the PMOVES.AI repo and asserts equality.
- **`spec` field semantics alignment** - the v1.0 spec and the bootstrap schema use the same key with different meanings. Follow-up: document the divergence or unify.
- **Pinokio main.js wire-up** - the `pmoves: true` flag is currently a no-op; the loader is invoked manually from `install.js`/`start.js`. Follow-up: hook into the actual pinokio app launch.
- **Real `nats-py` Hermes subscriber** - the v0 subscriber is a stub. Follow-up: add nats-py to Hermes's core deps (the deps list explicitly warns against this; needs an explicit operator decision) and wire the real subscription loop.

## Three-body

delivery=Mavis (this, the 3 review pass + the cleanup commits + the AGNOTE rows + the LEARNINGS), control=DARKXSIDE (operator reviews the 3 PRs + decides the follow-up priority), memory=this trail + the 2 LEARNINGS files + the 3 GitHub review comments.

## CHIT trail unsigned-local

No CHIT_PASSPHRASE loaded in this Mavis session per the standing operator convention.
