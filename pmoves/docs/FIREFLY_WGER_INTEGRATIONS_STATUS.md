# Firefly & Wger Integration Status Review
_Last updated: 2025-10-14_

## Overview
- Compose profiles for Firefly III, Wger, and the flows watcher are now checked into `pmoves/compose/` alongside the n8n core stack (`docker-compose.core.yml`). Helper scripts live under `pmoves/scripts/` and the Makefile exposes `integrations-*` targets.
- Local secrets still ship with placeholder defaults—operators must override database passwords and app keys before enabling the stacks outside a dev environment.
- Automation helpers mount `pmoves/integrations/health-wger/n8n/flows/` and `pmoves/integrations/firefly-iii/n8n/flows/`; the repository includes README stubs and `.gitkeep` files so the watcher starts with empty directories instead of missing mounts.【F:pmoves/integrations/health-wger/n8n/flows/.gitkeep†L1-L1】【F:pmoves/integrations/firefly-iii/n8n/flows/.gitkeep†L1-L1】

## Firefly III profile
- `pmoves/compose/docker-compose.firefly.yml` defines a MariaDB-backed Firefly III stack exposed on `8080/tcp` with a dedicated volume for the database and a `firefly` compose profile for opt-in startup.【F:pmoves/compose/docker-compose.firefly.yml†L1-L32】
- Secrets require operator action: `FIREFLY_APP_KEY` ships with a placeholder (`base64:CHANGE_ME`), and database credentials fall back to weak defaults unless overridden.【F:pmoves/compose/docker-compose.firefly.yml†L16-L28】
- The integrations Make targets do not yet wire Firefly into downstream services; use the n8n flows to sync data into Supabase.

## Wger profile
- `pmoves/compose/docker-compose.wger.yml` provisions a Postgres 15 database plus the upstream `wger/wger` image behind the `wger` compose profile and binds the UI to `8000/tcp`.【F:pmoves/compose/docker-compose.wger.yml†L1-L27】
- Similar to Firefly, it defaults to development-grade credentials (`wgerpass`, `changeme`) that must be replaced, and there is no linkage into PMOVES event streams or Supabase sync jobs yet.

## n8n automation helpers
- The optional flows watcher sidecar mounts helper scripts plus two integration-specific flow directories, assumes a healthy `n8n` service, and runs `n8n-flows-watcher.sh` to auto-import JSON updates.【F:pmoves/compose/docker-compose.flows-watcher.yml†L4-L21】【F:pmoves/scripts/n8n-flows-watcher.sh†L1-L43】
- The repository now ships empty flow directories (`pmoves/integrations/health-wger/n8n/flows/`, `pmoves/integrations/firefly-iii/n8n/flows/`) with README guidance so teams can drop JSON exports without scaffolding the paths first.【F:pmoves/integrations/health-wger/README.md†L1-L5】【F:pmoves/integrations/firefly-iii/README.md†L1-L5】

## Open gaps & next steps
1. **Document the watcher workflow** – add a short guide on enabling the watcher profile and verifying imports (partially covered here; expand in `pmoves/docs/N8N_CHECKLIST.md`).
2. **Check in canonical n8n flow exports** or link to authoritative sources so the directories populate with working examples.
3. **Harden credentials** by documenting required overrides for secrets and recommending non-default passwords before enabling either integration in shared environments.
4. **Plan data synchronization** into PMOVES (webhooks, ETL jobs, or API bridges) so Firefly and Wger data becomes available to Agent Zero or downstream automations.
