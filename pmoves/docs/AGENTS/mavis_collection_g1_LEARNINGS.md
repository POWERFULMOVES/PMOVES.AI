# Mavis Collection G.1 — LEARNINGS

> **GRAPHITI_MARK:** Mavis::MAVIS-COLLECTION-G1::LEARNINGS::2026-10-05
> **Author:** 5090-claude (Mavis on the 5090 / POWERFULMOVES)
> **Companion:** `pmoves/docs/architecture/MAVIS_COLLECTION_DESIGN.md`, `pmoves/docs/architecture/HYPERAGINTZ_MONIKER_DESIGN.md`, `pmoves/docs/AGENTS/claude_pmoves_mavis_launcher_LEARNINGS.md` (slice A)

Pair-review notes for the Mavis Collection G.1 slice (auth + manifest schema + 3-step probe gate). Following the operator's "Review lessons > review comments" practice (2026-07-15): these are pair-review observations, not just resolved threads. 4-bucket + 5-class taxonomy as in `branch-protection-v0_LEARNINGS.md`.

---

## 4 Buckets (the 4 kinds of observations)

### Bucket 1: missed-signal — patterns I should have caught before writing code

1. **Token Plan api_base mismatch between catalog and SDK.** `pmoves/config/provider_catalog.yaml:447` declares `api_base: "https://api.minimaxi.chat/v1"`. The `mmx` CLI works against `api.minimax.io`. A naive wire-up that trusts the catalog would route the Mavis SDK overlay through `api.minimaxi.chat` and chat calls would 404. mmx is the source of truth; the catalog gets corrected in G.2. Lesson: when integrating an SDK that has its own validated config (mmx auth + mmx smoke), prefer the SDK's working endpoint over an undocumented catalog entry. (Recorded in MAVIS_COLLECTION_DESIGN.md §TBD resolutions, item 7.)

2. **Token Plan key formats are NOT interchangeable with pay-as-you-go.** Operator dropped `sk-api-...` first (pay-as-you-go format); `mmx auth status` accepted it; every chat call returned `code 4: insufficient balance (1008)`. The fix: `mmx agent setup --help` documents the `sk-cp` vs `sk-api` distinction. Wire-up MUST verify via the 3-step probe gate (auth → quota → chat) — auth-success alone is misleading. Lesson: a credential that passes auth but fails quota is NOT wired-up. (Memory entry "MiniMax API key formats: sk-cp vs sk-api" captured 2026-10-05.)

3. **M2.7 model suit `last_verified: 2026-05-13` is 5 months stale.** Token Plan has evolved (M3 launched, multimodal now shared quota). The suit still describes M2.7's 1M context accurately but the surrounding ecosystem has shifted. Lesson: model suits need a periodic re-verification; this is a follow-up lane (not G.1's scope).

### Bucket 2: fix-pattern — the actual technique that worked

4. **3-step probe gate as the contract.** The resolver runs `mmx auth status` → `mmx quota show` → `mmx text chat ping`. Each step is independently mockable + independently assertable. A credential that fails step 1 is "not authenticated"; step 2 is "not subscribed"; step 3 is "billing-gate rejected". This decomposition makes "wired-up" a single boolean at the end + a list of human-readable failure modes. Lesson: credential validation gates should be explicit step functions, not single bool checks.

5. **Collection as runner, not forker.** The example manifest's `super_nodes.datasets[*].ref` points at `pmoves/config/datasets.yaml#pmoves-chit-text` — a YAML anchor reference, not a copy. Same for skills (PMOVES fork catalog), plugins (PMOVES fork registry), mindmap (gateway endpoint). The collection never holds canonical data; it holds pointers. Future operators get drift-proof configuration by construction. Lesson: when adding a local layer over a git-managed canonical, default to pointers; copy only when the local needs mutability.

6. **Schema version as quoted string.** `schema_version: "1.0"` not `schema_version: 1.0`. The validator regex `^[0-9]+\.[0-9]+$` only matches strings. First test run failed because YAML parsed `1.0` as float `1.0` and the comparison `1.0 == "1.0"` returned False. Lesson: when the schema constrains a field's string shape, declare the field's YAML type as string explicitly. (Now quoted in `manifest.schema.yaml`.)

### Bucket 3: wrong-suggestion — paths I considered and rejected

7. **Don't put the Token Plan key in `~/.mavis/collection/auth/minimax.json`.** Tempting because it makes the collection self-contained. Rejected because (a) `~/.mmx/config.json` is the canonical location mmx persists to and refreshes against, (b) maintaining a parallel copy invites sync bugs, (c) `mmx auth login` already updates the right file. The Collection's resolver just READS the mmx config — single source of truth. Lesson: pick the canonical store; the consumer is read-only.

8. **Don't add a JSON Schema 2020-12 full validator dependency.** The schema document references the JSON Schema meta-schema but the resolver implements its own subset validator (required fields, type checks, enum checks, regex). Reason — slice G.1 ships with zero external deps beyond PyYAML (already in PMOVES runtime). Adding jsonschema or fastjsonschema adds a dependency for ~150 lines of validation. Lesson: minimal dep surface for early-stage slices.

9. **Don't write the manifest to disk at install.** G.1 ships the resolver + schema + example, but does NOT install the manifest into `~/.mavis/collection/manifest.yaml` automatically. Reason — the install is operator-trust-only (the Collection directory is operator-scoped; only `mmx auth login` should land files in there). The resolver reads from a `--manifest` path arg, defaulting to `~/.mavis/collection/manifest.yaml`. Lesson: trust boundaries matter; the Collection is operator-scoped.

### Bucket 4: already-addressed — work this PR inherits without re-doing

10. **PR #3282 (slice A) provides the HyPeRAGInT form + Mavis launcher.** G.1 does NOT recreate these. The `hyperagint.yaml` form at `pmoves/configs/agents/forms/hyperagint.yaml:1` is inherited and cross-referenced from the example manifest's `identity.form_ref`. The `claude-pmoves-mavis.*` launcher family from slice A is the operator-facing entry point that the Collection sits behind. Lesson: always check the base branch (here: `feat/claude-pmoves-mavis-launcher` at `76ac1a0c8a`) for inherited artifacts before writing new ones.

11. **`pmoves/config/datasets.yaml` already lists 3 HF datasets.** G.3 will add collection-side pointers, not recreate. Same for `pmoves/services/gateway/gateway/api/mindmap.py` (mindmap endpoint) and the PMOVES skill/plugin catalogs. Lesson: the Collection is a runner; it points at canonical PMOVES surfaces, not duplicates.

12. **The 3-step probe is already in agent memory.** The probe gate is captured in `~/.minimax/agents/mavis/memory/MEMORY.md` (entry "MiniMax API key formats: sk-cp vs sk-api — NOT interchangeable", 2026-10-05). The resolver implements the same gate in code; the tests assert the gate's branches. Lesson: durable memory + test contract = the same gate defended in two layers.

---

## 5-Class Taxonomy (per-thread learning comment)

#### Class: legit — patterns to keep

- **Pointer-only collection manifest.** Section entries are `{ref, source, spec, design, endpoint, constellation_id, provider}` — all pointers, no copies. This is the right shape for a local layer over a git-managed canonical. KEEP.

- **3-step probe gate as a contract.** Auth + quota + chat steps are independently mockable + independently assertable. The wired_up boolean is the final summary; the per-step data is the diagnostic. KEEP.

- **CGP v1.0-derived schema.** The `pmoves.bootstrap/v1` profile carries spec + meta + identity + super_nodes — same shape as CGP v1.0's spec/meta/sig/super_nodes with sig replaced by identity (the bootstrap doesn't sign, it identifies). KEEP.

#### Class: already-fixed — patterns from prior slices that informed this one

- **slice A's LEARNINGS file convention.** Same 4-bucket + 5-class taxonomy + test coverage map. Same GRAPHITI_MARK header. Same SDK + doc provenance section at the end. APPLY.

- **slice A's regression-test pattern.** `MavisCollectionResolverTests.test_validate_subcommand_returns_0_on_valid_example` mirrors slice A's `MavisWrapperShapeTests.test_bash_wrapper_pins_backend_minimax_default` — the test asserts the entry point's behavior, not its internals. APPLY.

- **slice A's cross-ref test class.** `MavisCollectionIdentityCrossrefTests` mirrors slice A's `HyperagintFormTests.test_form_references_built_from_minimaxx_agint` — both assert that a derived artifact's lineage is explicit + validated. APPLY.

#### Class: owner — operator-only decisions, no agent-side fix

- **Whether to install the manifest to `~/.mavis/collection/manifest.yaml` at SDK first-boot.** Per the TBD-confirm gates, the install is operator-trust-only. Not auto-done in G.1.

- **Whether to add HuggingFace + Ollama Cloud auth slots now.** Operator hasn't dropped those credentials yet. The example manifest has them commented out as future slots. Not auto-done.

- **Whether G.2 should be on the same branch (recommended) or a separate branch.** Operator's "ok to proceed" accepted the 1-branch / 4-commit / 1-PR recommendation. Locked in for the rest of G.

#### Class: out-of-scope — work this PR does NOT touch

- **G.2 — provider_catalog extension + 4 model suits.** Out of scope for G.1; lands as commit 2 on the same branch.
- **G.3 — personas + datasets pointers.** Out of scope; commit 3.
- **G.4 — mindmap + skills + plugins + chit pointers.** Out of scope; commit 4.
- **Slice B — ACP registry link (`minimax-code: linked`).** Out of scope; separate PR off main.
- **Operator-install automation.** Out of scope; operator-trust-only.
- **Encryption at rest for `auth/`.** Out of scope; default plaintext + Windows ACLs; DPAPI wrap is a separate follow-up if/when operator requires it.

#### Class: pre-existing — patterns from before this slice that the work surfaces

- **The `claude-pmoves-mavis` launcher (slice A) operates without a Collection manifest.** Today the launcher just sets `PMOVES_CLAUDE_BACKEND=minimax` + execs. The Collection sits behind it; future slices can add `mavis_collection_resolve.py resolve` to the launcher's pre-flight. NOT-A-BUG, INHERITED.

- **The `provider_catalog.yaml:447` api_base mismatch (Bucket 1, item 1) is pre-existing.** G.2 corrects it; G.1 inherits and surfaces the issue in the design doc. NOT-A-BUG, PRE-EXISTING-MISMATCH.

- **The 5-month-stale M2.7 suit (Bucket 1, item 3) is pre-existing.** Out of scope for G.1; documented in design doc for follow-up. NOT-A-BUG, NEEDS-REFRESH.

---

## Test coverage map (4 buckets × 5 classes)

| Bucket / Class | Test class / method |
|---|---|
| Bucket 1 missed-signal | `MavisCollectionManifestSchemaTests.test_manifest_with_wrong_spec_fails` + `MavisCollectionAuthProbeTests.test_probe_fails_when_*` (5 probe failure modes) |
| Bucket 2 fix-pattern | `MavisCollectionManifestSchemaTests.test_example_manifest_parses_and_validates` + `MavisCollectionResolverTests.test_validate_subcommand_returns_0_on_valid_example` |
| Bucket 3 wrong-suggestion | `MavisCollectionResolverTests.test_validate_subcommand_returns_nonzero_on_missing_file` + `..._returns_nonzero_on_invalid_yaml` (regression against silent fallback) |
| Bucket 4 already-addressed | `MavisCollectionIdentityCrossrefTests.test_example_manifest_form_ref_resolves` + `test_example_manifest_inheritance_includes_claude_code` (asserts slice A inheritance is wired) |
| Class legit (KEEP) | `MavisCollectionExampleManifestTests.test_example_datasets_point_at_real_pmoves_surfaces` (pointer-only shape) |
| Class already-fixed (APPLY) | `MavisCollectionManifestSchemaTests.test_minimal_manifest_validates` (slice A's regression-test pattern) |
| Class out-of-scope | `MavisCollectionExampleManifestTests.test_example_covers_all_super_node_sections` (asserts G.2-G.4 surfaces are reserved, not implemented) |
| Class pre-existing | `MavisCollectionAuthProbeTests.test_probe_passes_when_all_three_steps_green` (asserts the pre-existing 3-step gate works in code, not just memory) |

24 tests / 5 classes / 4 buckets. All green on local pre-push verification.

---

## SDK + doc provenance (per DARKXSIDE practice, 2026-09-16)

- **SDK file:line (this PR adds):**
  - `pmoves/docs/architecture/MAVIS_COLLECTION_DESIGN.md:1` — design doc
  - `pmoves/configs/mavis_collection/manifest.schema.yaml:1` — schema (CGP v1.0-derived)
  - `pmoves/configs/mavis_collection/example.yaml:1` — example populated manifest
  - `pmoves/tools/mavis_collection_resolve.py:24` — resolver CLI (validate/resolve/probe subcommands)
  - `pmoves/tools/mavis_collection_resolve.py:128` — `three_step_probe()` implementation
  - `pmoves/tools/tests/test_mavis_collection_g1.py:1` — 24 tests / 5 classes
- **SDK file:line (this PR inherits, does not modify):**
  - `pmoves/configs/agents/forms/hyperagint.yaml:1` — HyPeRAGInT form (slice A)
  - `pmoves/config/provider_catalog.yaml:447` — `minimax:` provider entry (G.2 will correct api_base)
  - `pmoves/config/datasets.yaml:1` — 3 HF datasets (G.3 will point at these)
  - `pmoves/services/gateway/gateway/api/mindmap.py:1` — Neo4j-backed mindmap (G.4 will reference)
  - `~/.mmx/config.json` — Token Plan key persistence (mmx-managed; Collection reads-only)
- **AGNOTE row:** `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` — CLAIM row at `2026-10-05T08:30:00Z` + RELEASE row at slice commit time
- **LEARNINGS file:** this file (added in this PR)
- **Branch:** `feat/mavis-collection-scaffold-2026-10-05` (cut off `feat/claude-pmoves-mavis-launcher` @ `76ac1a0c8a`)
- **Base:** `feat/claude-pmoves-mavis-launcher` (slice A; PR #3282 OPEN)
- **PR:** TBD — opened against `PMOVES.AI-Edition-Hardened` (protected base per PR #2490) after local verification