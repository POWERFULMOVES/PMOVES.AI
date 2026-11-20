# PMOVES Integrations

This directory holds PMOVES-side overlays for integrated services/submodules.

## Current integrations

Every directory actually present under `pmoves/integrations/` is listed here. The
ratchet `pmoves/tests/tools/test_integration_reconciliation_ratchet.py` fails if a
directory exists on disk that is not named below.

- `_template/` – the scaffold every new integration is copied from (see "Contract-first onboarding" below)
- `agent0-plugins/` – local staging lane for PMOVES plugin-index submissions to `agent0ai/a0-plugins` (`catalog/<plugin-name>/plugin.yaml` drafts)
- `archon/` – git submodule (PMOVES-Archon) mounted here for local integration builds
- `firefly-iii/` – Firefly III / PMOVES-Wealth integration overlay (PMOVES-Wealth artifacts currently remain in this folder name)
- `github-runners/` – GitHub runner lane policy (`compose/lane_hosts.json`, `compose/runner_phase_policy.json`)
- `health-wger/` – Wger health integration overlay
- `pr-kits/` – reusable PR packaging assets (compose snippets, CI fragments, summary docs); not a runtime overlay
- `tools/` – integration validation can-openers (`validate-integration.sh`, `validate-submodule.sh`, `submodule-sitrep.sh`)

## Contract-first onboarding

Before adding a new integration, copy the scaffold:

```bash
cp -R pmoves/integrations/_template/pmoves-integrations pmoves/integrations/<new-integration>
```

Then fill in:

- compose wiring (`compose/`)
- model mappings (`models/`)
- n8n flows (`n8n/flows/`)
- event subjects (`events/subjects.yaml`)
- CHIT/GitHub secret labels (`secrets/labels.yaml`)
- auth/bootstrap script (`auth/bootstrap.sh`)

Reference: `pmoves/docs/SUBMODULE_INTEGRATION_CONTRACT.md`

## SDK-facing hooks

Every integration should expose the same PMOVES hook surface:

- `pmoves-announcer` (or temporary `publisher-discord` bridge) for announcements/events
- `tensorzero-gateway` + `model-registry` for model routing
- `gpu-orchestrator` events for deployment-aware model selection
- submodule validation can-openers:
  - `make -C pmoves submodule-integrity` for deterministic non-recursive gating
  - `make -C pmoves submodule-sitrep` for onboarding audit snapshots
  - `pmoves/integrations/tools/validate-integration.sh <path>` for contract checks (announcer/model/gpu hooks)

## Integration Validation Kit

Use these core PMOVES tools when onboarding or promoting a new repo:

- `pmoves/tools/submodule_integrity.py`
  - Gate unmapped gitlinks, drift (`+`), and conflicted (`U`) states.
- `pmoves/tools/submodule_sitrep.py`
  - Produce a decision-oriented alignment report for production reviews.
- `pmoves/tools/integration_contract_check.py`
  - Validate overlay contract requirements for new repos (layout + required subjects/hooks).
- Template wrappers live in `pmoves/integrations/_template/pmoves-integrations/tools/`.
