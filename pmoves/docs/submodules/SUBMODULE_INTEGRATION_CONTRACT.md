# Submodule Integration Contract
_Last updated: 2026-02-14_

This contract defines how PMOVES integrates new submodules without ad-hoc drift.

## Required Layout (inside each integrated submodule)

Create a `pmoves-integrations/` folder in the submodule root:

```
pmoves-integrations/
  README.md
  compose/
    docker-compose.pmoves-net.yml
  tools/
    validate-submodule.sh
    submodule-sitrep.sh
    validate-integration.sh
  models/
    profiles/
    mappings/
  n8n/
    flows/
  events/
    subjects.yaml
  secrets/
    labels.yaml
  auth/
    bootstrap.sh
  docs/
    OPERATIONS.md
```

## Rules

- `compose/` must attach services to `pmoves_app` (and compatibility aliases only when required).
- `tools/` must include integration can-openers for submodule integrity:
  - `validate-submodule.sh` (calls PMOVES non-recursive gate by default)
  - `submodule-sitrep.sh` (captures timestamped alignment snapshot for audit evidence)
  - `validate-integration.sh` (checks layout + announcer/model/GPU hook wiring contract)
- `models/mappings/` should reference Supabase model registry aliases/service mappings, not hardcoded model IDs in startup scripts.
- `n8n/flows/` must be sanitized exports (no user/project metadata).
- `events/subjects.yaml` should declare announcer + gpu/model subjects consumed or emitted by the integration.
- `secrets/labels.yaml` must map integration keys to CHIT labels and GitHub secret names.
- `auth/bootstrap.sh` should be idempotent and safe for reruns (no destructive defaults).

## PMOVES Repository Side

PMOVES keeps a matching integration tree:

- `pmoves/integrations/<integration-name>/...`
- `pmoves/integrations/_template/pmoves-integrations/...` (starter scaffold)

Use that template first, then map any submodule-specific deltas in `README.md`.

## PMOVES SDK Hook Points

Every new integration should expose these standard hooks so the PMOVES SDK can orchestrate consistently:

- **Event announcements:** `pmoves-announcer` compatible events (or `publisher-discord` bridge until announcer is promoted as a standalone service).
- **Model routing:** `tensorzero-gateway` + `model-registry` mappings (`pmoves_core.service_model_mappings`).
- **GPU lifecycle:** `gpu-orchestrator` events (`mesh.gpu.model.loaded.v1`, `mesh.gpu.model.unloaded.v1`) for deployment-aware model selection.
- **Secrets/auth:** CHIT label map + bootstrap script (`secrets/labels.yaml`, `auth/bootstrap.sh`).

## Model Ownership

- Runtime model routing: Supabase model registry (`pmoves_core.service_model_mappings`).
- Local/edge fallback: `pmoves/models/*.yaml` and provider folders under `pmoves/models/providers/`.
- Deployment snapshots: `make -C pmoves models-registry-snapshot`.
