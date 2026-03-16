# TAC_MODEL_INFRA_PERSONA_PROD_READINESS
_Last updated: 2026-03-15_

## Mission
Bring model infrastructure and persona grounding to production readiness with deterministic, merge-safe sequencing across Supabase model registry, TensorZero mapping, GPU model inventory, and persona runtime resolution.

Constraint:
- Do not touch `PMOVES-transcribe-and-fetch` in this lane.

## Current State Snapshot (Repo Reality)

**All 5 tactical branches are COMPLETE on `main`.**

- `pmoves/supabase/initdb/12_model_registry_seed.sql` (1,511 lines) — expanded with:
  - Anthropic provider + Claude model entries (claude-sonnet-4-5, claude-opus-4-5, claude-haiku-4-5)
  - local Ollama model coverage including `qwen3:*`, `codellama:7b`, `deepseek-coder:6.7b`
  - TTS provider + 6 TTS engine entries
  - 30+ `service_model_mappings` across all service tiers
  - All entries idempotent (ON CONFLICT handling)
- `pmoves/supabase/initdb/17_persona_seed.sql` (1,598 lines) — 8 personas seeded:
  - Developer, Creator, Analyst, Researcher, Tester, Coordinator, Security, Archivist
  - Model preferences match registry keys, ON CONFLICT (name, version) DO UPDATE
- `pmoves/supabase/migrations/20260301002000_persona_model_resolution.sql` — merged:
  - `pmoves_core.persona_model_resolution` view (persona → model → provider join)
  - `pmoves_core.active_persona_summary` bonus view
  - RLS-aware, PostgREST grants for anon + authenticated roles
- `pmoves/tools/model_readiness_check.py` (652 lines) — comprehensive checks:
  - 10 validation checks (providers, models, mappings, personas, Ollama, TensorZero)
  - Docker exec fallback for DB access
  - Environment variable control (MODEL_READINESS_* flags)
- `pmoves/Makefile` — `model-readiness` target wired, integrated into `verify-all`

## Tactical Branches — Status

### Branch B/D (P1/P2): Registry + GPU Inventory Reconciliation — COMPLETE ✅

Scope:
- finalize `12_model_registry_seed.sql` as single source of seeded model/provider truth
- enforce VRAM parity against `pmoves/config/gpu-models.yaml` for GPU-tracked models
- keep cloud-only models documented as intentionally absent from GPU YAML where applicable

Evidence: `12_model_registry_seed.sql` at 1,511 lines with full provider/model coverage.
GPU YAML at 203 lines with VRAM reconciliation for RTX 5090/4090/3090 Ti/Jetson.

### Branch A (P1): Persona Seed Integration — COMPLETE ✅

Scope:
- keep `pmoves/supabase/initdb/17_persona_seed.sql` as canonical seeded persona load
- ensure idempotent conflict handling and model preference names match registry keys

Evidence: 8 personas with ON CONFLICT, model preferences aligned to registry keys.

### Branch C (P2): Service-Model Mapping Coverage — COMPLETE ✅

Scope:
- verify mappings align to active services and model IDs present in registry seed
- remove stale mappings that point to non-existent models

Evidence: 30+ mappings embedded in `12_model_registry_seed.sql`, covering all active services.

### Branch F (P2): Persona-Model Resolution View — COMPLETE ✅

Scope:
- migration: `pmoves/supabase/migrations/20260301002000_persona_model_resolution.sql`
- create view `pmoves_core.persona_model_resolution`
- grant read policy for service/runtime roles

Evidence: Migration merged, view definition includes provider resolution and RLS.

### Branch E (P2): Startup Readiness Check — COMPLETE ✅

Scope:
- `pmoves/tools/model_readiness_check.py` (652 lines, 10 checks)
- Make target `model-readiness` at `pmoves/Makefile:1877`
- Integrated into `verify-all` (non-destructive, fail-fast)

Evidence: `make -C pmoves model-readiness` executes readiness validation.

### Branch G (NEW): Agent Zero Bootstrap Integration

Scope:
- Add Agent Zero to `bootstrap/registry.json` with 5 variables
- Auto-generate `MCP_CLIENT_SECRET` in `brand_defaults.py`
- Seed model routing defaults (`A0_SET_*`) via TensorZero

Status: PR #960 (`feat/agent-zero-branded-defaults`)

## Execution Order
1. ~~Branch B/D~~ ✅
2. ~~Branch A~~ ✅
3. ~~Branch C~~ ✅
4. ~~Branch F~~ ✅
5. ~~Branch E~~ ✅
6. Branch G — PR #960

## Deterministic Verification
Run in order:
1. `make -C pmoves supabase-bootstrap`
2. `make -C pmoves verify-all` (includes `model-readiness`)
3. SQL spot checks:
   - `SELECT count(*) FROM pmoves_core.personas;` — expect ≥8
   - `SELECT count(*) FROM pmoves_core.models;` — expect ≥35
   - `SELECT persona_name, model_preference, model_name, provider_name FROM pmoves_core.persona_model_resolution;`
   - `SELECT count(*) FROM pmoves_core.service_model_mappings;` — expect ≥15

## Merge and Handoff Rules
- Runtime and DB-affecting changes follow Integrations -> Hardened rail strategy.
- Every branch completion requires:
  - Graphiti trail entry (`Done / Left Behind / For Next Agent`)
  - AGNOTE claim/review/release update
  - PR monitor pass (`make -C pmoves pr-monitor-strict`)
  - CHIT flow strict gate (`make -C pmoves chit-flow-pr-monitor-strict`)

## Ready-for-PR Checklist
- [x] Atomic commit boundaries preserved (one commit per branch objective)
- [x] No transcribe-and-fetch changes in diff
- [x] All new SQL is idempotent
- [x] Make target docs updated if commands change
- [ ] Verification evidence included in PR comments (pending runtime validation)
