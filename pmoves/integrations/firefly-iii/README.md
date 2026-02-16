# Firefly III (PMOVES-Wealth) Integration Overlay

This integration keeps PMOVES-Wealth workflows and PMOVES integration contract wiring in one place.

## Core flows

Store Firefly synchronization and enrichment workflows in `n8n/flows/`. When the integrations
compose stack is up, the watcher container automatically imports any updated JSON files into n8n so
the flows stay in sync without manual uploads.

## PMOVES hook surface

- Event hook: `pmoves-announcer` compatible subject definitions in `events/subjects.yaml`.
- Model hook: `tensorzero-gateway` + `model-registry` references in `models/mappings/`.
- GPU hook: `gpu-orchestrator` event compatibility via `mesh.gpu.model.*` subjects.
- Validation can-openers: `tools/validate-submodule.sh`, `tools/submodule-sitrep.sh`, `tools/validate-integration.sh`.
