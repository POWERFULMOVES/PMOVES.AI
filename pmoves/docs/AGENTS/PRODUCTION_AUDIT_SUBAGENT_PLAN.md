# Production Audit Subagent Plan
_Last updated: 2026-02-14_

## Objective

Close production-audit blockers while preserving hardened defaults, cross-platform bring-up parity, and PMOVES integration contract quality.

## Current Sitrep

- Core contract/tooling lanes are in place:
  - `submodule-integrity` + SITREP generation
  - `integration-contract-check` (template + opted-in overlays)
  - secrets/tooling audits and CHIT funnel targets
- Primary blockers are now operational:
  - strict boot-order drift (dev/prod switches and service sequencing)
  - observability completeness (service-to-dashboard coverage, smoke alignment)
  - secrets/auth lifecycle (JWT, runtime hydration, onboarding clarity)
  - legacy integration folders not fully migrated to the new contract layout

## Immediate Queue (scout snapshot)

From current tree scan (`pmoves/integrations/*`):

- `health-wger`: contractized (compose/events/tools/models/secrets/auth/docs scaffold in place).
- `firefly-iii`: contractized (compose/events/tools/models/secrets/auth/docs scaffold in place).
- `archon`: contract scaffold prepared under submodule path `pmoves/integrations/archon/pmoves-integrations/`; requires upstream PMOVES-Archon commit/push to become CI-visible in this repo.
- `pr-kits`: no contractized overlay files yet.

This means CI contract enforcement currently validates template + opted-in overlays only, by design.

## Subagent Lanes

### Lane A — Secrets/Auth Hardening
- Scope:
  - Supabase JWT refresh + runtime secret hydration validation
  - CHIT manifest v1/v2 sync and portability workflow
  - onboarding defaults for real operator email/auth paths
- Inputs:
  - `pmoves/chit/secrets_manifest*.yaml`, `pmoves/tools/chit_manifest_sync.py`
  - `pmoves/tools/runtime_secrets_hydrate.py`, `pmoves/tools/auth_bootstrap_check.py`
- Exit criteria:
  - `make -C pmoves secrets-audit`
  - `make -C pmoves chit-manifest-check`
  - `make -C pmoves auth-check`

### Lane B — Bring-Up Order and Compose Runtime
- Scope:
  - enforce production-first boot sequence
  - remove dev-default ambiguity from smoke/bring-up paths
  - validate cross-platform env loading (Windows/WSL/Linux)
- Inputs:
  - `pmoves/Makefile`, `pmoves/mk/*.mk`
  - `pmoves/scripts/with-env.sh`, `pmoves/scripts/smoke*.{sh,ps1}`
  - compose stacks under `pmoves/compose/` and `pmoves/docker-compose*.yml`
- Exit criteria:
  - deterministic `make -C pmoves preflight`
  - deterministic `make -C pmoves up` / `make -C pmoves smoke`
  - no mixed-shell regressions in docs or scripts

### Lane C — Observability and Smoke Truth
- Scope:
  - map smoke checks to production services and dashboards
  - ensure logs/metrics panels exist for each critical service
  - separate dev-only probes from production smoke
- Inputs:
  - `pmoves/docs/services/monitoring/OBSERVABILITY_MAP.md`
  - monitoring compose + dashboards
  - smoke harness + reporting tools
- Exit criteria:
  - `make -C pmoves up-monitoring`
  - `make -C pmoves monitoring-report`
  - documented service->signal mapping for smoke assertions

### Lane D — Submodule/Integration Alignment
- Scope:
  - finish migration from legacy overlays to contractized integration layout
  - enforce new integration onboarding through can-openers and CI gates
  - clear alias/canonical mapping for promoted submodules
- Inputs:
  - `.gitmodules`, `pmoves/tools/submodule_integrity.py`
  - `pmoves/tools/integration_contract_check.py`
  - `pmoves/integrations/_template/pmoves-integrations/*`
- Exit criteria:
  - `make -C pmoves submodule-integrity`
  - `make -C pmoves integration-contract-check-baseline`
  - `python pmoves/tools/integration_contract_check.py pmoves/integrations/archon --strict-hooks` passes locally (nested `pmoves-integrations` support), then mirror changes upstream in PMOVES-Archon
  - no unmapped gitlinks in root mappings

### Lane E — Model Registry and Local Runtime Profiles
- Scope:
  - remove hardcoded models from runtime/docs where possible
  - align service mappings with Supabase registry + local fallback profiles
  - codify model swap workflow for constrained and GPU-heavy nodes
- Inputs:
  - `pmoves/docs/MODEL_SOURCE_OF_TRUTH.md`
  - `pmoves/tools/models/*`
  - `pmoves/models/providers/*`
- Exit criteria:
  - `make -C pmoves models-sync`
  - `make -C pmoves models-registry-snapshot`
  - docs no longer advertise hardcoded model IDs as defaults

### Lane F — Documentation Consolidation and Archive Safety
- Scope:
  - consolidate bootstrap/bring-up docs and preserve archival history
  - avoid destructive doc cleanup; archive with index references
  - align PMOVES plans docs with hardened branch reality
- Inputs:
  - `pmoves/docs/README_DOCS_INDEX.md`
  - `pmoves/docs/DOCS_CONSOLIDATION_ARCHIVAL_POLICY.md`
  - sprint planning docs (`ROADMAP.md`, `NEXT_STEPS.md`)
- Exit criteria:
  - single canonical bring-up runbook
  - archive index updated for moved/deprecated docs
  - no duplicate contradictory quick-start paths

## Recommended Execution Order

1. Lane A + Lane B (foundation)
2. Lane C (validation truth)
3. Lane D + Lane E (integration/model scale)
4. Lane F (consolidation after behavior stabilizes)

## Suggested Subagent Artifacts

- Lane A: `pmoves/docs/SECRETS_CREDENTIALS_AUDIT_YYYY-MM-DD.md`
- Lane B: `pmoves/docs/BOOT_ORDER_AUDIT_YYYY-MM-DD.md`
- Lane C: `pmoves/docs/services/monitoring/OBSERVABILITY_MAP.md` updates
- Lane D: `pmoves/docs/SUBMODULE_ALIGNMENT_SITREP_YYYY-MM-DD.md`
- Lane E: `pmoves/docs/MODEL_SOURCE_OF_TRUTH.md` deltas + snapshot evidence
- Lane F: `pmoves/docs/DOCS_CONSOLIDATION_LOG_YYYY-MM-DD.md`

## Suggested Subagent Branches

- `subagent/lane-a-secrets-auth`
  - Run: `make -C pmoves secrets-audit chit-manifest-check auth-check`
- `subagent/lane-b-bringup-runtime`
  - Run: `make -C pmoves preflight`, then bring-up/smoke sequence in `SMOKETESTS.md`
- `subagent/lane-c-observability`
  - Run: `make -C pmoves up-monitoring monitoring-report observability-audit`
- `subagent/lane-d-submodule-integration`
  - Run: `make -C pmoves submodule-integrity integration-contract-check-strict`
- `subagent/lane-e-model-registry`
  - Run: `make -C pmoves models-sync models-registry-snapshot`
- `subagent/lane-f-docs-consolidation`
  - Run: docs index + runbook consolidation pass, no runtime changes
