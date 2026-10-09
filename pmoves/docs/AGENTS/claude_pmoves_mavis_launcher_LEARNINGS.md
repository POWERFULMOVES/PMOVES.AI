# claude-pmoves-mavis Launcher — LEARNINGS

> **GRAPHITI_MARK:** Mavis::CLAUDE-PMOVES-MAVIS-LAUNCHER::LEARNINGS::2026-10-05
> **Author:** 5090-claude (Mavis on the 5090 / POWERFULMOVES)
> **Companion:** `pmoves/docs/architecture/HYPERAGINTZ_MONIKER_DESIGN.md`, PR #3184 (`feat(claude-pmoves): --backend= flag + pmoves-mini claude-backend switch`)

Pair-review notes for the launcher shim that adds the `claude-pmoves-mavis.{sh,ps1,cmd}` family + per-node `claude-pmoves-{5090}-mavis.{sh,ps1,cmd}` variants and the `hyperagint.yaml` agent form.

Following the operator's "Review lessons > review comments" practice (2026-07-15): these are pair-review observations, not just resolved threads. 4-bucket + 5-class taxonomy as in `branch-protection-v0_LEARNINGS.md`.

---

## 4 Buckets (the 4 kinds of observations)

### Bucket 1: missed-signal — pattern I should have caught before writing code

1. **`hyperagint.yaml` "already exists" was about the form SCHEMA, not the file.** Operator said "already exists" but `pmoves/configs/agents/forms/` had no `hyperagint.yaml` on any checkout (research, fix, main). The intent was "the AgentIdentity form schema exists in `5090-CLAUDE.yaml` / `DARKXSIDE.yaml` — follow that pattern." I caught this on re-read; if I'd assumed the file existed and started adding HyPeRAGInT-specific keys via patch, I would have failed silently. Lesson: when an operator says "X already exists," verify which scope they mean (the file, the schema, the convention).

### Bucket 2: fix-pattern — the actual technique that worked

2. **Thin wrapper, no inlined logic.** The `-mavis` launcher is 44 lines of bash, 28 lines of PowerShell. All the heavy lifting (env-strip, env.shared, blocklist, settings.json detection, `--backend=` parse) lives in the main `claude-pmoves.{sh,ps1}`. The wrapper just sets `PMOVES_CLAUDE_BACKEND=minimax` and `exec`. This is testable, drift-proof (env-strip bug fixes land in one place), and matches the per-node -5090 wrapper shape (`PMOVES_NODE_ID` + exec the inner launcher). Lesson: when adding a new launch mode, the file that already exists has the right shape — model the wrapper on the per-node variant, not on the main launcher.

3. **GLM-coding-plan + MiniMax share the `ANTHROPIC_BASE_URL` / `ANTHROPIC_AUTH_TOKEN` env keys** because both providers ride the openai-compatible API surface under Claude Code's anthropic-shaped env contract. The blocklist in `claude-pmoves.ps1:17-19` is too aggressive — it strips BOTH providers' routing keys. The fix is not "narrow the blocklist" but "lift the blocklist for explicit opt-in modes (`-mavis`, future `-glm`, future `-kimi`)." Each opt-in launcher carries its own backend. Lesson: provider-agnostic env vars require a per-provider opt-in, not a single blocklist.

### Bucket 3: wrong-suggestion — paths I considered and rejected

4. **Don't inline the Mavis SDK overlay directly in `-mavis`.** The temptation was to copy `pmoves/configs/claude_settings/minimax.json` into the launcher as a hardcoded `ANTHROPIC_BASE_URL=...` and `ANTHROPIC_AUTH_TOKEN=...` export. Rejected because (a) it duplicates the canonical template, (b) future template edits have to land in two places, (c) the launcher becomes load-bearing for the SDK overlay contract. The `-mavis` launcher should remain a thin shim that delegates to PR #3184's `--backend=minimax` (which itself loads the canonical template). The wrapper is the seam, not the engine. (This is the same pattern as `claude-pmoves-5090.sh` which sets `PMOVES_NODE_ID` and execs — the wrapper carries the binding, the main carries the policy.)

5. **Don't add the HyPeRAGInT form to the ACP registry in slice A.** Slice A is the launcher shim. ACP registration is slice B per `HYPERAGINTZ_MONIKER_DESIGN.md`. If slice A also touches `pmoves/configs/acp_registry_map.json`, the PR is no longer reviewable as a single coherent slice and the operator's review surface balloons. Lesson: per the PMOVES workstream convention (per `AGNOTE4482_SITREP.md` branch naming table), one slice = one PR = one review surface.

### Bucket 4: already-addressed — work this PR inherits without re-doing

6. **PR #3184 already has the env-strip + blocklist + `--backend=` parse logic.** Slice A does NOT re-implement this. The 12 files / 1872 insertions / 144 assertions in PR #3184 are inherited. The slice A `claude-pmoves-mavis.sh` is a 44-line wrapper that delegates to PR #3184's mechanism via `exec "$MAIN" --backend="$PMOVES_CLAUDE_BACKEND" "$@"`. Lesson: always check what's already on the base branch before writing new logic. (Base here is `feat/claude-backend-switch` at `b9d62c9186`.)

7. **The launcher-blocklist over-removal is what the operator meant by "verify locally before push."** The default `claude-pmoves` launcher stays clean (Claude Max default). The `-mavis` launcher lifts the blocklist via `--backend=minimax`. Tests assert both invariants. The `default_launcher_mia120_backwards_compat_tests` test class catches any future PR that accidentally pins `PMOVES_CLAUDE_BACKEND=minimax` in the default launcher (regression). Lesson: write the regression test in the same PR that fixes the bug; the test is the spec for "what we promised not to break."

---

## 5-Class Taxonomy (per-thread learning comment)

#### Class: legit — patterns to keep

- The pattern of a thin wrapper that sets `PMOVES_NODE_ID` (existing) + a thin sibling wrapper that sets `PMOVES_CLAUDE_BACKEND` (new) + a thin wrapper that does both (`claude-pmoves-5090-mavis`) is the right architecture for a multi-axis launch surface. Each axis (node identity, model backend, future: harness type, future: registry tier) is its own thin file. KEEP.

- The `PMOVES_CLAUDE_BACKEND` env var inheritance (operator-set > default `minimax`) matches the per-node pattern (`PMOVES_NODE_ID` is operator-set > hardcoded). Both follow "last-writer-wins" with the wrapper's default as the floor. KEEP.

#### Class: already-fixed — patterns from prior slices that informed this one

- `claude-pmoves-5090.sh:24` comment block "the registry is the canonical binding" pattern — same invariant in the -mavis wrapper ("PMOVES_CLAUDE_BACKEND from process env wins over `minimax` default"). The two axes share the same precedence semantics. APPLY.

- `pmoves/tools/claude_backend.py:153-191 apply_backend` (PR #3184) — the apply logic that the -mavis wrapper delegates to. The wrapper doesn't duplicate it. ALREADY-DONE.

#### Class: owner — operator-only decisions, no agent-side fix

- Whether to add 4090/b850/z890 `-mavis` variants in this slice or in a follow-up. Per the design doc, slice A is 5090-first; other nodes are a separate scope. Not auto-done.

- Whether to rename `PMOVES-MiniMaXX-AGInT` → `PMOVES-HyPeRAGInT` now or after more additions. Operator picked "after a few more additions." Not auto-done.

- Whether to rename `PMOVES-registry` → `PMOVES-HyPeRAGInTZ` now or after more additions. Operator picked "after a few more additions." Not auto-done.

#### Class: out-of-scope — work this PR does NOT touch

- ACP registry link (slice B). Slice A creates the launcher shim and the form file; the registry entry is its own slice.
- Cipher mindmap binding (slice C). Out of scope for the launcher shim.
- Hi-RAG v2 binding (slice D). Out of scope.
- `pmoves/integrations/hyperagint/` PMOVES integration contract (slice E). Out of scope.
- miniagent spawn protocol (slice F). Out of scope.
- DeepSeek harness config (NEW operator ask on 2026-10-05). Out of scope; separate follow-up.
- Jetson combiner multi-agent wiring (Mavis + Hermes + Claude Code + Codex + GLM + Kimi). Out of scope; separate follow-up.

#### Class: pre-existing — patterns from before this slice that the work surfaces

- The launcher blocklist at `claude-pmoves.ps1:17-19` was authored before GLM-coding-plan and MiniMax shared env keys. The slice A wrapper is the minimal fix; a future slice can move the blocklist into a per-backend allowlist. NOT-A-BUG, KNOWN-LIMITATION.

- `pmoves/configs/claude_settings/minimax.json` (PR #3184) contains the legacy `[1m]` 1M-context tag on `ANTHROPIC_MODEL: MiniMax-M3[1m]` and `ANTHROPIC_DEFAULT_OPUS_MODEL: MiniMax-M3[1m]`. Per PR #3184 root-cause section, this is the bug that causes `MiniMax-M3[1m] may not exist` model-key errors. Slice A inherits the bug from the template; PR #3184 is the upstream fix. NOT-A-BUG, INHERITED.

---

## Test coverage map (4 buckets × 5 classes)

| Bucket / Class | Test class / method |
|---|---|
| Bucket 1 missed-signal | `HyperagintFormTests.test_form_references_built_from_minimaxx_agint` (asserts the form declares its lineage — surface a future rename gotcha) |
| Bucket 2 fix-pattern | `MavisWrapperShapeTests.test_bash_wrapper_does_not_duplicate_env_strip` (asserts the wrapper stays thin) + `MavisWrapperShapeTests.test_bash_wrapper_pins_backend_minimax_default` (asserts the default override) |
| Bucket 3 wrong-suggestion | `DefaultLauncherMia120BackwardsCompatTests.test_default_bash_does_not_set_pmoves_claude_backend` + `test_default_ps1_does_not_set_pmoves_claude_backend_minimax` (regression — future PRs can't pin the default launcher) |
| Bucket 4 already-addressed | `MavisWrapperShapeTests.test_bash_wrapper_exists_and_is_executable` + `MavisNodeVariantsTests.test_5090_mavis_exists` (asserts the seam exists and is wired) |

15 tests / 4 classes / 1 regression class. All green on local pre-push verification.

---

## SDK + doc provenance (per DARKXSIDE practice, 2026-09-16)

- **SDK file:line (this PR adds):**
  - `deploy/provision/claude-pmoves-mavis.sh:38-40` — `PMOVES_CLAUDE_BACKEND=minimax` default + exec main launcher
  - `deploy/provision/claude-pmoves-mavis.ps1:18-20` — PowerShell twin
  - `deploy/provision/claude-pmoves-5090-mavis.sh:19` — 5090 NODE_ID pin + exec -mavis wrapper
  - `pmoves/configs/agents/forms/hyperagint.yaml:1` — HyPeRAGInT agent form (extends `5090-CLAUDE.yaml` schema)
- **SDK file:line (this PR inherits, does not modify):**
  - `deploy/provision/claude-pmoves.ps1:9-66` — PR #3184 `--backend=` parse + apply
  - `deploy/provision/claude-pmoves.ps1:17-19` — blocklist (kept; will be narrowed in a future slice)
  - `pmoves/scripts/mavis_sdk_env.sh` — env-strip helper (PR #3184)
  - `pmoves/tools/claude_backend.py:153-191` — apply logic (PR #3184)
- **AGNOTE row:** `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` — RELEASE row at `2026-10-05T04:30:00Z` for slice A (added in this PR)
- **LEARNINGS file:** this file (added in this PR)
- **Branch:** `feat/claude-pmoves-mavis-launcher` (renamed from `fix/5090-claude-pmoves-launcher-anthropic-routing` per operator approval, 2026-10-05)
- **PR:** opened against `PMOVES.AI-Edition-Hardened` (protected base per PR #2490)