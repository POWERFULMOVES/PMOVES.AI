# TAC_MODEL_INFRA_PERSONA_PROD_READINESS
_Last updated: 2026-03-01_

## Mission
Bring model infrastructure and persona grounding to production readiness with deterministic, merge-safe sequencing across Supabase model registry, TensorZero mapping, GPU model inventory, and persona runtime resolution.

Constraint:
- Do not touch `PMOVES-transcribe-and-fetch` in this lane.

## Current State Snapshot (Repo Reality)
- `pmoves/supabase/initdb/12_model_registry_seed.sql` is already expanded with:
  - Anthropic provider + Claude model entries
  - local Ollama model coverage including `qwen3:*`, `codellama:7b`, `deepseek-coder:6.7b`
  - TTS provider + TTS model entries
  - broad `service_model_mappings` sections
- `pmoves/supabase/initdb/17_persona_seed.sql` exists and contains seeded personas, but is currently not yet merged.
- Missing from this lane:
  - persona-model resolution view migration
  - model readiness script + Make target wiring
  - deterministic verification evidence bundle attached to PR comments/trail

## Tactical Branches (Enhanced)

### Branch B/D (P1/P2): Registry + GPU Inventory Reconciliation
Owner: implementation lane owner

Scope:
- finalize `12_model_registry_seed.sql` as single source of seeded model/provider truth
- enforce VRAM parity against `pmoves/config/gpu-models.yaml` for GPU-tracked models
- keep cloud-only models documented as intentionally absent from GPU YAML where applicable

Output:
- one atomic commit: `feat(models): reconcile registry providers/models with gpu inventory`

### Branch A (P1): Persona Seed Integration
Owner: implementation lane owner

Scope:
- keep `pmoves/supabase/initdb/17_persona_seed.sql` as canonical seeded persona load
- ensure idempotent conflict handling and model preference names match registry keys

Output:
- one atomic commit: `feat(personas): add initdb persona seed set`

### Branch C (P2): Service-Model Mapping Coverage
Owner: implementation lane owner

Scope:
- verify mappings align to active services and model IDs present in registry seed
- remove stale mappings that point to non-existent models

Output:
- one atomic commit: `feat(models): expand and validate service model mappings`

### Branch F (P2): Persona-Model Resolution View
Owner: implementation lane owner

Scope:
- add migration:
  - `pmoves/supabase/migrations/20260301_persona_model_resolution.sql`
- create view `pmoves_core.persona_model_resolution`
- grant read policy for service/runtime roles

Output:
- one atomic commit: `feat(personas): add persona-model resolution view`

### Branch E (P2): Startup Readiness Check
Owner: implementation lane owner

Scope:
- add `pmoves/tools/model_readiness_check.py`
- add Make target `model-readiness`
- add hook into `verify-all` (non-destructive, fail-fast reporting)

Output:
- one atomic commit: `feat(ops): add model readiness checks and make target`

## Execution Order
1. Branch B/D
2. Branch A
3. Branch C
4. Branch F
5. Branch E

Rationale:
- Registry/model IDs must be stable before persona and mapping resolution.
- View and readiness checks must run against finalized seed surface.

## Deterministic Verification
Run in order:
1. `make -C pmoves supabase-bootstrap`
2. `make -C pmoves model-readiness`
3. `make -C pmoves verify-all`
4. SQL spot checks:
   - `SELECT count(*) FROM pmoves_core.personas;`
   - `SELECT count(*) FROM pmoves_core.models;`
   - `SELECT persona_name, model_preference, model_name, provider_name FROM pmoves_core.persona_model_resolution;`
   - `SELECT count(*) FROM pmoves_core.service_model_mappings;`

## Merge and Handoff Rules
- Runtime and DB-affecting changes follow Integrations -> Hardened rail strategy.
- Every branch completion requires:
  - Graphiti trail entry (`Done / Left Behind / For Next Agent`)
  - AGNOTE claim/review/release update
  - PR monitor pass (`make -C pmoves pr-monitor-strict`)
  - CHIT flow strict gate (`make -C pmoves chit-flow-pr-monitor-strict`)

## Ready-for-PR Checklist
- [ ] Atomic commit boundaries preserved (one commit per branch objective)
- [ ] No transcribe-and-fetch changes in diff
- [ ] All new SQL is idempotent
- [ ] Make target docs updated if commands change
- [ ] Verification evidence included in PR comments
