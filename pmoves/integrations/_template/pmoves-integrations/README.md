# <integration-name> PMOVES Integration Overlay

Replace `<integration-name>` and keep this layout stable for all new PMOVES integrations.

## Checklist

- [ ] Compose service file updated in `compose/`
- [ ] Validation tools wired in `tools/` (`validate-submodule.sh`, `submodule-sitrep.sh`, `validate-integration.sh`)
- [ ] Model mappings aligned with Supabase model registry in `models/`
- [ ] n8n flows exported into `n8n/flows/`
- [ ] event subjects declared in `events/subjects.yaml`
- [ ] CHIT + GitHub secret labels mapped in `secrets/labels.yaml`
- [ ] Auth bootstrap script is idempotent (`auth/bootstrap.sh`)
- [ ] Ops runbook added (`docs/OPERATIONS.md`)
- [ ] Event hook mapped for `pmoves-announcer` (or temporary `publisher-discord` bridge)
- [ ] Model hook mapped for `tensorzero-gateway` + `model-registry`
- [ ] GPU hook mapped for `gpu-orchestrator` (`mesh.gpu.model.*`)
