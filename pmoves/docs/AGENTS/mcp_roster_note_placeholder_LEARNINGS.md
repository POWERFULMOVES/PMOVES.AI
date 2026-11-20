# MCP fleet roster — note placeholder — LEARNINGS

**Lane:** the tracked FLEET roster degraded the NATS bridge permanently, because its own documentation quoted a placeholder from inside an `env` block
**Branch:** `fix/mcp-roster-note-placeholder-degrade`
**Operator:** DARKXSIDE · **Author:** Mavis (`mvs_ce8c1e6e34434db1ba42d3b822ecbd15`)
**Companion CLAIM row:** `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` (`2026-11-19T15:46:10Z`, TTL 72h → `2026-11-22T15:46:10Z`)
**Related lanes:** `pmoves/docs/AGENTS/mcp_inventory_endpoint_ratchet_LEARNINGS.md` (the inventory→roster contract), `pmoves/docs/AGENTS/test_gap_ratchet_LEARNINGS.md` (lesson #12 — the mutation-kill must INVOKE the assertion), `pmoves/docs/AGENTS/minimax_mcp_roster_provisioning_LEARNINGS.md` (the sibling roster lane)

---

## Operator direction (verbatim)

> "we need to address it has many integrations and we need to ensure they are all present"

The integration inventory work surfaced this as the one entry in the fleet roster that was degraded by something the operator could not configure. It is recorded here because the class is wider than the instance.

---

## The finding

`.claude/mcp.json` is the **FLEET** roster. `deploy/provision/claude-pmoves.sh` reads it from `origin/main` on **every node**, runs it through `pmoves/tools/mcp_roster_normalize.py`, and hands the result to Claude Code.

The `pmoves-nats-fleet` entry carried its documentation as a key **inside the `env` block**:

```json
"env": {
  "NATS_URL": "${NATS_URL}",
  "NATS_CREDS": "${NATS_CREDS:-}",
  "_NATS_CREDS_NOTE": "v0.2 (spec §7b): ... _nats_creds() rejects an empty value AND an
                      unresolved \"${...}\" placeholder (a bare \"${NATS_CREDS}\" survives
                      literally when the var is absent ...) ..."
}
```

The note **quotes the literal text `${...}`**. The normalizer's P4 pass expands `${VAR}` in every `env` value and P5 records what would not expand. `expand()` parses `${...}` as a variable reference whose name is `...`, which fails the `_IDENT` check (`^[A-Za-z_][A-Za-z0-9_]*$`), so it is recorded as a **malformed** reference — under its literal text.

**MEASURED, with the LIVE normalizer, both operator environments:**

| Environment | `degraded['pmoves-nats-fleet']` |
|---|---|
| `NATS_CREDS` set (the `.creds` materialised) | `['${...}']` |
| `NATS_CREDS` unset (the common case) | `['${...}', 'NATS_CREDS']` |

Every **other** degraded entry in that roster names a **real** environment variable the operator can set — `HOSTINGER_API_KEY`, `TAILSCALE_API_KEY`, `CLOUDFLARE_API_TOKEN`, `CIPHER_API_TOKEN`, `COMPOSIO_MCP_GATEWAY_KEY`, … `pmoves-nats-fleet` was the only one degraded by **prose**. No configuration could ever clear it.

The cross-node NATS bridge is the SPARK cascade dispatch path (`claw.task.assign.v1`), so the signal path looked broken on every node in every session.

**SCOPE, MEASURED ACROSS THE WHOLE ROSTER** (not just the nats entry):

| Scan | Result |
|---|---|
| Malformed references in any `url`/`headers`/`env` value | **exactly 1** — `pmoves-nats-fleet.env._NATS_CREDS_NOTE` |
| `_`-prefixed keys inside an `env` block | **exactly 1** — the same key |
| Servers carrying a server-level `_`-prefixed doc key | **14** (`_note`, `_purpose`, `_setup`, `_disabled`) |

So the entry was the only one in the file that put documentation where configuration belongs.

**THE HOUSE ALREADY SAID SO.** `deploy/provision/claude-pmoves.sh:668`, in the comment explaining why that script's own raw-roster gate excludes `_`-prefixed lines:

> FALSE POSITIVE, prose. `.claude/mcp.json`'s `_note` quotes the docs verbatim — "uses the unexpanded `${VAR}` text as-is". Claude Code reads `mcpServers`; `_`-prefixed keys are documentation. A node that had expanded every real reference still could not pass.

The launcher had already solved the same problem for its own text-scan by **excluding `_`-prefixed keys**. The roster had one entry that had not been moved to the convention the launcher assumes.

---

## 4-bucket · 5-class taxonomy

### Bucket 1 — Defects

| # | Class | Observation (rule) | Evidence / Why | Apply when |
|---|-------|---------------------|----------------|------------|
| 1.1 | **prose-in-a-config-field** | **Documentation placed in a field the tooling parses is not documentation — it is configuration that happens to be a string.** The note quoted `${...}`; the normalizer parsed it as a reference; the reference was malformed; the server was degraded forever. The defect was not the prose, it was the **placement**. | `_NATS_CREDS_NOTE` sat in `env`; `mcp_roster_normalize.normalize()` scans `url`/`headers`/`env` (`_DROP_FIELDS` + `_WARN_FIELDS`). 14 sibling entries already carry their docs at server level. | Any config field that a parser scans, where documentation is also stored. |
| 1.2 | **malformed-reference-is-unsatisfiable-by-construction** | **A reference to a real variable may be unresolved and that is CORRECT — it is a missing credential and the verdict is right. A MALFORMED reference can never resolve: there is no environment variable named `...`.** So malformedness, not unresolvedness, is the invariant worth asserting: it is permanent by construction and needs no environment matrix to decide. | `expand()` records an unresolved-but-well-formed reference under its **NAME** and a malformed one under its **LITERAL TEXT**. With an empty environ, a recorded miss that still looks like a reference is malformed. | Any variable-expansion scheme with a syntax error mode. |
| 1.3 | **the-finding-that-no-configuration-can-clear** | **When a verdict names something the operator cannot set, the verdict is about the DECLARATION, not the environment.** `pmoves-nats-fleet` appeared in the same degraded list as ten servers whose credentials were simply absent. Sorting the degraded list by *what the operator could do about it* is what separated the real finding from the noise. | Degraded list, creds set: `pmoves-nats-fleet: ['${...}']` beside `hostinger-mcp: ['HOSTINGER_API_KEY']`, `tailscale: ['TAILSCALE_API_KEY', 'TAILSCALE_TAILNET']`, … Every other entry names a settable variable; one did not. | Any tool that reports "missing" findings to an operator. |
| 1.4 | **a-doc-string-injected-into-the-process-environment** | **A documentation key inside `env` is also a 700-character string injected into the MCP server's real environment.** The defect had a second, quieter face: the note was being handed to the process as if it were configuration. | The note is 730+ characters of prose about the CORE-account transport-trust gate, the payload-provenance gate and the `_nats_creds()` fallback rule, and it was in the `env` map the launcher passes to `uv`. | Any roster whose `env` map is passed to a process. |
| 1.5 | **the-generator-is-not-the-roster** | **`.claude/mcp.json` is generated from the inventory AND MERGED over the tracked file, so the tracked file legitimately carries keys the generator does not describe.** Treating the tracked file as a pure generator output is how a hand-add gets mistaken for drift — in either direction. | MEASURED: the merge drops **0** tracked servers and changes **0** described fields; the tracked file carries 10 hand-added servers (`cloudflare`, `comfy`, `docker`, `hostinger-mcp`, …) the inventory does not describe, and 14 hand-added doc keys. `test_claude_mcp_roster_matches_inventory.py` already encodes the correct contract ("a tracked entry may legitimately carry hand-added keys the inventory does not describe"). | Any "the generated file drifted" claim about a merged artifact. |
| 1.6 | **an-unbalanced-reference-is-as-unsatisfiable-as-a-malformed-one** | **A reference that opens and never closes (`${BROKEN`) can never resolve either — there is no environment variable for it. Classifying "malformed" by the presence of a CLOSING BRACE leaves a hole in the class the gate exists to close.** Codex finding `4631230891` on this lane's ratchet: the filter required `}`. | MEASURED with the live `expand()`: `expand("${BROKEN", {}, m)` → `m == ['${BROKEN']` — the normalizer records the literal text it could not close and degrades the server. The old filter discarded it, so the ratchet passed while the server was degraded. The discriminator is **"does the recorded miss still look like a reference?"** (starts with `${`), not "is it closed?". | Any reference scanner that separates "unset" from "unsatisfiable". |
| 1.7 | **an-absent-entry-is-invisible-to-a-field-by-field-comparison** | **A server the generator describes and the roster does not carry has no field to compare — so a comparison that iterates the generated entries and skips the ones it cannot find reports no drift at all.** The missing server is the more dangerous direction, because it is not a wrong value, it is a whole absent service. Codex finding `4631230905`: the branch `continue`d. | MEASURED: the generator emits **14** servers for `claude`/`fleet`; the tracked roster carries **21**; the difference in THIS direction is exactly **3** (`e2b-danger-room`, `flute-voice`, `flute-voice-mcp`), and the other 10 roster servers are hand-added (the opposite direction). A comparison over the generated entries alone cannot see a fourth absence. | Any drift check between a generated artefact and its source. |
| 1.8 | **a-lane's-fix-can-invalidate-an-already-merged-lane's-published-table** | **A fix that changes a shared artefact changes what a gate reports about it — and a table published by an EARLIER, already-merged lane can become FALSE without anyone touching it.** The row was correct when it was written and wrong the moment this lane landed. | MEASURED with the LIVE normalizer: before this lane's move, `pmoves-nats-fleet` / `NATS_CREDS` in `env` was DEGRADED (the prose quoted a bare `${NATS_CREDS}` AND a malformed `${...}`, so the server degraded on every launch even with every var set); after it, `NATS_CREDS` is CLEAN and only `NATS_URL` flags the server. The `Windows host quirks` section of `.claude/BOOTSTRAP.md` (PR #3485, ALREADY MERGED) published the DEGRADED row, and THAT lane's ratchet failed against this lane's tree. | Any lane that changes a shared artefact another lane's documentation describes. |

### Bucket 2 — Decisions

| # | Class | Observation (rule) | Why | Alternative considered | Cost of alternative |
|---|-------|---------------------|-----|------------------------|---------------------|
| 2.1 | **move-the-note-do-not-rewrite-it** | Lift the note to a server-level `_`-prefixed key, text preserved byte-for-byte. | The note's text documents the placeholder semantics — including the literal `${...}` form. Rewriting it would destroy the documentation it exists to provide. | Rewrite the placeholder as non-brace prose inside `env` | The finding disappears, but a 730-character doc string stays in a config field, is still injected into the process environment, and the note stops quoting the exact literal it describes. A workaround. |
| 2.2 | **move-the-note-do-not-delete-it** | The note stays, at the right level. | It is the only record of the CORE-account transport-trust gate, the payload-provenance gate and the `_nats_creds()` fallback rule. | Delete the note | Silently loses operational documentation to make a gate green. The ratchet asserts the note survives, precisely so this cannot pass unnoticed. |
| 2.3 | **do-not-touch-the-inventory** | The note is NOT added to `pmoves/config/mcp_inventory.json`. | MEASURED: `ServerSpec` has no `_note` field and `_collect_servers` does not read one. The inventory's own `e2b-danger-room._note` renders to an entry with keys `[args, command, description, env]` — **no note**. An inventory-level note would simply not reach the roster, so adding it there would be a claim with no effect. | Add the note to the inventory as the "source of truth" | A row in the source that renders nowhere: it would read as provenance while changing nothing, and the next reader would believe the roster is derived. |
| 2.4 | **do-not-touch-`NATS_CREDS`-either** | `NATS_CREDS` is NOT added to the inventory. | MEASURED: `.kimi/mcp.json`'s `pmoves-nats-fleet` carries env `[NATS_URL]` only — `NATS_CREDS` is a **claude-roster-local** hand-add. And it is **not the defect**: `${NATS_CREDS:-}` has a default, so it expands to empty and records no miss. | Add `NATS_CREDS` to the inventory for symmetry | Changes five other clients' rosters to fix nothing. Scope without a defect. |
| 2.5 | **assert-the-class-not-the-instance** | The ratchet asserts "no malformed reference in any config value" and "no `_`-prefixed key inside an `env` block" — roster-wide, not "the nats entry must not degrade". | Both rules are currently satisfied by exactly one entry, and both would catch a future instance in a different server. An instance-specific assertion would only ever fire once. | Assert `pmoves-nats-fleet` specifically | The next occurrence lands in a different server and the gate stays green. |
| 2.6 | **the-behavioural-test-uses-the-live-normalizer** | The degrade test calls `mcp_roster_normalize.normalize()` — the component that produces the verdict — rather than re-deriving the verdict. | A re-implementation of P4/P5 in the test would be a second opinion about the tool's own rules, and would drift from them. | Re-implement the expansion in the test | The test could agree with a broken normalizer. The whole point is to observe the real verdict. |
| 2.7 | **correct-the-published-truth-do-not-relax-the-merged-lane's-gate** | When a MERGED lane's ratchet fails because another lane changed the shared artefact, the fix is the PUBLISHED STATEMENT, not the gate. The row that became false was removed, the note explaining it was rewritten to what the gate does now, and the footnote's row count was corrected 9 → 8. | The merged lane's gate was RIGHT: it compared a published claim against the LIVE gate, and the claim had become false. Relaxing it would keep a false claim in an always-loaded doc. MEASURED: the bootstrap ratchet 12 passed, the harness **10 of 10 proven kills**, including **M10 — the REVERT of this correction**, which puts the removed row back and requires `test_the_roster_table_matches_the_live_roster_and_the_live_gate` to die naming it. | Relax the merged lane's precondition (e.g. accept a DEFAULTED reference for a row that claims a finding) | The gate can no longer say "this published row is false", and the next drift of the same shape lands in the same blind spot. |

### Bucket 3 — Operations

| # | Class | Observation (rule) | Measured | Repeatability |
|---|-------|---------------------|----------|---------------|
| 3.1 | **a-malformed-reference-is-identified-by-an-empty-environment** | Run `expand(value, {}, missing)` with an EMPTY environment: a well-formed unresolved reference is recorded under its NAME (`NATS_CREDS`), a malformed one under its LITERAL TEXT (`${...}`). The discriminator is the braces. | `expand("${NATS_CREDS}", {}, m)` → `m == ['NATS_CREDS']`; `expand("${...}", {}, m)` → `m == ['${...}']`. | Any reference scanner that must separate "unset" from "unsatisfiable". |
| 3.2 | **the-textual-move-preserves-the-note-byte-for-byte** | The fix was applied by moving the **line** (found by its key, never retyped) rather than by round-tripping the file through `json.dumps`, which would have reflowed every array in it. | Diff = `2 insertions(+), 2 deletions(-)`; the note value is byte-identical before and after (asserted in the applier). | Any edit to a JSON file whose formatting is load-bearing. |
| 3.3 | **the-roster-is-a-generated-merge-target** | `write_client_config(..., merge=True)` overlays the generated fields and keeps the tracked file's own keys. That is the mechanism the fix depends on. | Merge result: **0** tracked servers dropped, **0** described fields changed, 3 servers added (`e2b-danger-room`, `flute-voice`, `flute-voice-mcp` — see follow-up 1). | Any change to a merged config. |
| 3.4 | **the-ratchet-must-be-proven-against-the-unfixed-roster** | A ratchet that has never been seen failing is not known to fail. | The ratchet was run against the **unfixed** roster first: **6 failed, 1 passed** — the malformed-reference rule, the placement rule, the degrade rule (×2 environments), the documentation-survives rule and the merge-preserves rule all failed; only the generator-agreement rule passed, and it had to keep passing after the fix. | Every ratchet, before the fix is claimed. |
| 3.5 | **posix-mode-assertions-fail-on-windows** | Three tests in `pmoves/tests/test_mcp_roster_normalize.py` assert `0o600` file modes. Windows cannot produce them. | `assert 438 == 384` (`0o666` vs `0o600`). **Proven pre-existing**: the identical three failures occur with the roster reverted to `origin/main` (`git stash`), so they are not caused by this change. They pass on Linux CI, which runs CPython 3.11. | Any POSIX-permission assertion run on this Windows host. |
| 3.6 | **measure-the-merge-before-touching-a-generated-file** | Before editing a generated artifact, measure what the generator actually produces and what the merge actually changes. | The **pure render** would have dropped **10** tracked servers and added 3 — a destructive change. The **merge** drops 0 and changes 0. Reading only the render would have produced the wrong decision. | Any "regenerate this config" instruction. |
| 3.7 | **the-discriminator-is-"does-it-still-look-like-a-reference"** | Classify a recorded miss by its SHAPE, not by a completeness test: a miss that still starts with `${` is a reference-shaped literal and can never resolve; a miss that is a bare name is a real variable the operator has not set. | MEASURED with the live `expand()`: `${NATS_CREDS}` → `['NATS_CREDS']` (a bare name — correctly NOT malformed); `${...}` → `['${...}']`; `${BROKEN` → `['${BROKEN']`. The ratchet filters on `m.startswith("${")`, so all three are classified by the same rule, and a well-formed unresolved reference is never a false positive. | Any reference scanner that must separate "unset" from "unsatisfiable". |

### Bucket 4 — Cross-references

| # | Class | What | Link | Why it matters |
|---|-------|------|------|----------------|
| 4.1 | **the-launcher-states-the-convention** | "`_`-prefixed keys are documentation" — and the launcher's raw-roster gate excludes them for exactly this reason. | `deploy/provision/claude-pmoves.sh:668` | The house convention was already written down. The roster had one entry that had not been moved to it. |
| 4.2 | **lesson-12-lineage** | "A mutation-kill that restates the assertion instead of invoking it proves nothing." | `pmoves/docs/AGENTS/test_gap_ratchet_LEARNINGS.md` lesson #12 | Directly applied — the harness calls the ratchet's own test functions and asserts the SPECIFIC message. |
| 4.3 | **sibling-harness-shape** | Mutate a real artefact copy → repoint the ratchet's module constants → call the ratchet's own functions → assert the specific message. | `pmoves/tests/tools/test_mcp_inventory_endpoint_mutation_kill.py` | Two harnesses, one shape, so the next agent recognises the idiom. |
| 4.4 | **the-inventory-is-the-source-of-truth-for-ENDPOINTS** | `mcp_inventory.json` + `mcp_config_generator.py` are the contract; the client configs are DERIVED from them — but the tracked roster is a MERGE target, not a pure output. | `pmoves/config/mcp_inventory.json`, `pmoves/tools/mcp_config_generator.py` (`ServerSpec.supports_client`, `_collect_servers`, `_deep_merge`) | Which artefact to fix is decided by asking: is the DERIVATION right, the SOURCE, or the hand-add? Here the hand-add was misplaced. |
| 4.5 | **the-contract-for-a-merged-roster** | "A tracked entry may legitimately carry hand-added keys the inventory does not describe; every field the inventory DOES describe must match." | `pmoves/tests/test_claude_mcp_roster_matches_inventory.py` | The ratchet generalises it roster-wide, comparing `env` per KEY so a legitimate hand-added key does not read as drift. |
| 4.6 | **operator-queue-provenance** | The lane was raised in the operator's 2026-11-19 five-part request, in the "ensure they are all present" part. | AGNOTE row (this lane) + `pmoves/docs/AGENTS/mcp_inventory_endpoint_ratchet_LEARNINGS.md` | One queue, several lanes, each with its own provenance so the trail stays per-lane. |
| 4.7 | **review-round-provenance** | Codex's two inline findings on PR #3488 named the exact defect, the exact branch and the exact consequence — both were correct, and both are now closed at source with a kill. | PR #3488 review threads `4631230891` (unbalanced reference) and `4631230905` (absent generated server); the review round is recorded in the "Review round" section below. | A review finding is a measurement someone else already made; closing it needs a kill, not a prose edit. |

---

## Test inventory

| File | Tests | What it pins |
|---|---|---|
| `pmoves/tests/tools/test_mcp_roster_note_placeholder_ratchet.py` (new) | 7 | **1** no `url`/`headers`/`env` value may carry a malformed reference (roster-wide, detected with the tool's own `expand()` against an empty environment; **classifies every recorded miss that starts with `${`**, so unbalanced references are included) · **2** no `_`-prefixed key inside any `env` block (roster-wide) · **3** `pmoves-nats-fleet` must not appear in the LIVE normalizer's degraded list, in BOTH operator environments (creds set / creds unset) · **4** the documentation must still be present at server level, non-empty, and still naming `NATS_CREDS`, the transport-trust gate and the payload-provenance gate · **5** every field the generator describes must still match the tracked roster, `env` compared per KEY, **and a generated server that is ABSENT from the roster is recorded as drift in its own right, with the three measured exceptions held to BOTH directions** · **6** a merge regeneration must preserve the server-level documentation · **7** the generator-agreement rule is the one that had to keep passing across the fix |
| `pmoves/tests/tools/test_mcp_roster_note_placeholder_mutation_kill.py` (new) | 9 | The PROVENANCE harness. **M1** the note moved back into `env` with `${...}` intact (the ORIGINAL defect, restored) → kills the malformed-reference rule · **M2** the note moved into `env` with a WELL-FORMED `${NATS_CREDS}` → kills the placement rule **and proves the malformed-reference rule still PASSES**, so the two rules are independent rather than one rule wearing two names · **M3** the note deleted → kills the documentation-survives rule and the merge-preserves rule · **M4** the inventory changed under the roster → kills the generator-agreement rule · **M5** an UNBALANCED reference (`${BROKEN`) lands in a config value → kills the malformed-reference rule (review finding `4631230891`) · **M6** the inventory gains a server the roster does not carry → kills the generator-agreement rule (review finding `4631230905`) · **M7** a server recorded as deliberately absent BECOMES rostered → kills the generator-agreement rule, so the absence record cannot go stale |

Total: **16 new tests across 2 new files.**

---

## SDK provenance

- **Ratchet:** `pmoves/tests/tools/test_mcp_roster_note_placeholder_ratchet.py` — `ROSTER_PATH`, `INVENTORY_PATH`, `TARGET_SERVER`, `DOC_KEY`, `DOCUMENTED_VAR`, `SCANNED_FIELDS`, `GENERATED_NOT_ROSTERED`, `_scannable_values()`, `_malformed_references()`
- **Harness:** `pmoves/tests/tools/test_mcp_roster_note_placeholder_mutation_kill.py` — `RATCHET_MODULE`, `DOC_KEY`, `TARGET_SERVER`, `MALFORMED`, `WELL_FORMED`, `UNBALANCED`, `ABSENT_PROBE_KEY`, `RECORDED_ABSENT_SERVER`, `_load_ratchet()`, `_mutated_roster()`, `_mutated_roster_raw()`, `_move_note_into_env()`
- **SDK files exercised:**
  - `pmoves/tools/mcp_roster_normalize.py:153-206` — `expand()`: malformed reference recorded under its literal text (`:181-185`), unresolved-but-well-formed recorded under its NAME (`:199-201`)
  - `pmoves/tools/mcp_roster_normalize.py:64-66` — `_DROP_FIELDS` / `_WARN_FIELDS` (the scanned set the ratchet reads from the tool, never restates)
  - `pmoves/tools/mcp_roster_normalize.py:261-344` — `normalize()`: P4 expansion of `url`/`headers`/`env`, P5 verdict
  - `pmoves/tools/mcp_roster_normalize.py:68` — `_IDENT = ^[A-Za-z_][A-Za-z0-9_]*$` (the check `...` fails)
  - `pmoves/tools/mcp_config_generator.py:66-86` — `ServerSpec` (no `_note` field) and `supports_client`
  - `pmoves/tools/mcp_config_generator.py:167-213` — `_collect_servers()` (does not read an inventory `_note`)
  - `pmoves/tools/mcp_config_generator.py:520-536` — `_deep_merge()` (keeps the tracked file's own keys — the mechanism the fix relies on)
  - `deploy/provision/claude-pmoves.sh:668` — the house statement that `_`-prefixed keys are documentation
  - `.claude/mcp.json` — the fleet roster itself (2 insertions, 2 deletions)
- **CI gate:** `merge-gate.yml::python-tests` runs `pmoves/tools/pytest_ratchet.py`, which discovers `pmoves/tests/**` without a paths filter — both new files land in the ratchet automatically.

---

## Test status

- `pmoves/tests/tools/test_mcp_roster_note_placeholder_ratchet.py` → **7 passed**
- `pmoves/tests/tools/test_mcp_roster_note_placeholder_mutation_kill.py` → **9 passed** (6 at the first review round, +3 for the review findings)
- Combined → **16 passed**
- Against the **unfixed** roster, the ratchet was **6 failed, 1 passed** — the failures are the defect, measured before the fix.
- The three new kills were each proven to fire with their OWN specific message (M5 → "can never resolve" **and** names `${BROKEN`; M6 → "MISSING a server the inventory declares" **and** names the probe; M7 → "has gone stale" **and** names the server). A negative control on each expected-message string returned `False`.
- `pmoves/tests/test_mcp_roster_normalize.py` → 3 failures, **proven pre-existing** (identical failures with the roster reverted to `origin/main`): POSIX file-mode assertions that cannot hold on Windows. Passes on Linux CI.
- `pmoves/tests/test_claude_mcp_roster_matches_inventory.py`, `pmoves/tests/test_claude_pmoves_roster_fallback.py`, `pmoves/tests/test_minimax_mcp_roster_provisioning.py` → **green** (unchanged by this lane).

---

## Review round

Two Codex inline findings landed on PR #3488. **Both were correct, and both were closed at source with a kill** — neither was answered with prose.

| Finding | What it said | Disposition | Kill |
|---|---|---|---|
| `4631230891` (P2) | The malformed-reference filter discarded an **unbalanced** reference (`${BROKEN`) because it required a closing brace — so the ratchet passed while the normalizer still degraded the server. | **FIXED at source.** `_malformed_references()` now filters on `m.startswith("${")`. MEASURED against the live `expand()`: `${NATS_CREDS}` → `['NATS_CREDS']` (a bare name, correctly not malformed), `${...}` → `['${...}']`, `${BROKEN` → `['${BROKEN']`. The real roster carries **0** malformed references under the widened filter, so the fix adds no false positive. | **M5** — the roster is mutated with `${BROKEN` in an `env` value and the malformed-reference test must FAIL, naming the literal. |
| `4631230905` (P2) | The generator-agreement test `continue`d when a generated server was absent from the roster, so a whole missing server was invisible — a field-by-field comparison has nothing to compare when the entry is not there. | **FIXED at source.** The absence is recorded as drift in its own right, and the three measured exceptions are held to **BOTH** directions: a new absence fails, and a recorded absence that becomes rostered also fails, so the record cannot go stale. | **M6** — the inventory gains a server the roster lacks and the generator-agreement test must FAIL, naming the server. **M7** — a recorded-absent server is rostered verbatim from the generator (so field drift stays silent) and the stale-record branch must FAIL, naming the server. |

**Why the absence record needed writing down.** MEASURED with the live generator at client `claude`, endpoint `fleet`: the inventory declares **19** server entries, the generator emits **14** for this client, and the tracked roster carries **21**. Of the 14 generated, exactly **3** are not rostered — `e2b-danger-room`, `flute-voice`, `flute-voice-mcp` — and each has a measured reason (see follow-up 1). The roster's other **10** servers are hand-added and are not described by the inventory at all; that is the opposite direction and is not an absence. Both directions are now measured and both are asserted.

---

## Hand-written exclusions

This lane touches **one** existing file: `.claude/mcp.json`, and only by **moving** one key out of one `env` block to the server level. The note's text is byte-identical; the server's `command`, `args`, `env` values and `description` are unchanged; the roster's server count is unchanged.

`pmoves/config/mcp_inventory.json` is **byte-identical to `origin/main`** — deliberately (decisions 2.3 and 2.4). No executable config, workflow, compose file or gitlink is touched.

---

## Open follow-ups

1. **Three servers the generator declares for `claude` are absent from the fleet roster.** MEASURED: a merge regeneration would add `e2b-danger-room`, `flute-voice` and `flute-voice-mcp` — `git log -S` proves **none of the three was ever in `.claude/mcp.json`**, so this is a roster that was never regenerated, not one that lost them. `e2b-danger-room` explicitly lists `"claude"` in its `clients`; the two `flute-voice` entries have **no** `clients` key, and `supports_client` returns `True` when `clients is None` (`mcp_config_generator.py:83-86`). **They are not added here, for a measured reason:** `e2b-danger-room` is a stdio server whose command is `node ./pmoves-e2b-mcp-server/packages/js/build/index.js` — the path is a gitlink (`pmoves-e2b-mcp-server`, mode 160000) whose `packages/js/build/` is produced by an `npm run build` that **no** file in `pmoves/mk`, `deploy/` or `pmoves/tools` performs, so the entry would launch and fail on every node. `flute-voice`/`flute-voice-mcp` resolve to `http://${TS_Z890}:8055/…` on the fleet endpoint, so they depend on `TS_Z890` resolution and on `FLUTE_API_KEY` (present in `pmoves/env.shared.example:506`). Adding them is a **separate lane** with its own fail-closed analysis; the house convention for a dead wire is to keep it visible with the measured reason (cf. the `_disabled` entries and the `cipher:` entry in `pmoves/config/mcp-gateway/catalog.yaml`). **This record is now ENFORCED, not just written down:** the three reasons live in `GENERATED_NOT_ROSTERED` in the ratchet, and a fourth absence — or one of the three becoming rostered — fails the gate (kills M6 and M7).
2. **The `_pmoves_roster_verdicts` block has no production reader.** The normalizer writes the degraded list into the roster; `pmoves/scripts/session_check.py` classifies separately. Wiring a reader is a follow-up lane — and it is the reason a prose-degrade can sit unnoticed for as long as it did.
3. **`pmoves/tools/build_gate.py` ignores `build_context`** (reported by the doc-reconciliation lane). Six `pmoves/images.yaml` entries declare it, so the gate resolves a different Dockerfile than the publisher builds.

---

## Cross-lane reconciliation (2026-11-20) — a merged lane's published table went false

**What happened.** This lane's fix changed the roster, and the roster is what the `Windows host quirks` section of `.claude/BOOTSTRAP.md` describes. That section was landed by **PR #3485, already merged**, and it published a roster table row:

```
| `pmoves-nats-fleet` | `NATS_CREDS` | `env` | DEGRADED |
```

That row was **true** when #3485 landed and **false** the moment this lane's note moved out of `env`. #3485's own ratchet — `pmoves/tests/tools/test_bootstrap_windows_host_quirks_ratchet.py` — failed against this lane's tree on PR #3488's CI:

```
pmoves-nats-fleet/NATS_CREDS: the env reference is DEFAULTED, so an unset value is
not a finding and there is nothing to WARN about
```

**That failure is the gate WORKING.** The gate compared a published claim against the live normalizer and found the claim false. A weakened gate would have hidden it.

**MEASURED, with the live normalizer:**

| roster shape | `NATS_URL` | `NATS_CREDS` | what the normalizer records |
|---|---|---|---|
| before this lane (the note inside `env`) | DEGRADED | **DEGRADED** | `degraded: ['${...}', 'NATS_CREDS', 'NATS_URL']` |
| after this lane (the note at server level) | DEGRADED | **CLEAN** | `NATS_CREDS` is `${NATS_CREDS:-}` — defaulted, so it renders its default and records no miss |

So the prose in `env` was doing TWO jobs the normalizer could not distinguish: it documented the placeholder semantics AND it manufactured a bare `${NATS_CREDS}` reference plus a malformed `${...}` reference. Removing the prose from the scanned field removed both findings — which is what the fix was FOR — and left the published row false.

**What was fixed, and what was NOT.**

* **FIXED:** the FALSE row was removed from the published table; the note that explained the prose-driven finding was rewritten to state what the gate does now (a defaulted reference is not a finding; the note is a server-level `_`-prefixed key outside the expanded fields); the footnote's row count was corrected 9 → 8.
* **NOT FIXED — deliberately:** the merged lane's ratchet was **not** relaxed, **no** precondition was widened, **no** baseline was taken, and **no** ratchet was deleted. The gate was right.

**Two new kills pin the correction** in `pmoves/tests/tools/test_bootstrap_windows_host_quirks_mutation_kill.py`:

| kill | mutation | named test that must die |
|---|---|---|
| **M9** | the footnote's row count drifts (`8` → `9`) | `test_the_footnote_states_how_many_rows_it_is_a_superset_of` |
| **M10** | the REMOVED row is put back — the **REVERT** of this correction | `test_the_roster_table_matches_the_live_roster_and_the_live_gate` |

M9 exists because the footnote's row count had **no** mutation kill before — the exact number this reconciliation moved was unguarded. MEASURED: **10 of 10 proven kills**, GREEN before and after every mutation, the tree restored byte-exactly.

**The rule.** When a lane's fix changes a shared artefact, EVERY lane whose documentation describes that artefact must be re-read — including the ones merged weeks earlier whose authors are not in the room. The gate that catches it belongs to the lane that PUBLISHED the claim, not to the lane that changed the input.
