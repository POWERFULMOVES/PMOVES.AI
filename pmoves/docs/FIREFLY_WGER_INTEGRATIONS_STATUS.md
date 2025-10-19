# Firefly & Wger Integration Status Review
_Last updated: 2025-10-14_

## Overview
- The `pmoves-integrations-pr-pack` contributes Compose profiles for Firefly III and Wger along with helper scripts, but the pack is not yet wired into the main PMOVES stack (`docker-compose.core.yml` referenced by the pack is absent in-repo).
- Both integrations depend on placeholder secrets and local-only defaults, so additional configuration is required before they can be promoted beyond exploratory use.
- Automation helpers expect n8n flow exports under `integrations/health-wger` and `integrations/firefly-iii`, yet those directories are not bundled in the repository, leaving the watcher and import scripts with no payloads to process.

## Firefly III profile
- `docker-compose.firefly.yml` defines a MariaDB-backed Firefly III stack exposed on `8080/tcp` with a dedicated volume for the database and a `firefly` compose profile for opt-in startup.【F:pmoves/pmoves-integrations-pr-pack/compose/docker-compose.firefly.yml†L1-L35】
- Secrets require operator action: `FIREFLY_APP_KEY` ships with a placeholder (`base64:CHANGE_ME`), and database credentials fall back to weak defaults unless overridden.【F:pmoves/pmoves-integrations-pr-pack/compose/docker-compose.firefly.yml†L16-L28】
- No PMOVES services currently reference the Firefly endpoints, so once the container is running it remains an isolated personal finance instance pending API or event-bridge work.

## Wger profile
- `docker-compose.wger.yml` provisions a Postgres 15 database plus the upstream `wger/wger` image behind the `wger` compose profile and binds the UI to `8000/tcp`.【F:pmoves/pmoves-integrations-pr-pack/compose/docker-compose.wger.yml†L1-L29】
- Similar to Firefly, it defaults to development-grade credentials (`wgerpass`, `changeme`) that must be replaced, and there is no linkage into PMOVES event streams or Supabase sync jobs yet.【F:pmoves/pmoves-integrations-pr-pack/compose/docker-compose.wger.yml†L15-L23】

## n8n automation helpers
- The optional flows watcher sidecar mounts helper scripts plus two integration-specific flow directories, assumes a healthy `n8n` service, and runs `n8n-flows-watcher.sh` to auto-import JSON updates.【F:pmoves/pmoves-integrations-pr-pack/compose/docker-compose.flows-watcher.yml†L4-L21】
- The import and watcher scripts target `/opt/flows/health-wger` and `/opt/flows/firefly-iii`, but the repository tree only contains `compose/` and `scripts/` under the pack—no `integrations/**` payload directories—so the watcher would start empty and the import script would no-op until those assets are provided.【F:pmoves/pmoves-integrations-pr-pack/scripts/n8n-import-flows.sh†L8-L32】【F:pmoves/pmoves-integrations-pr-pack/scripts/n8n-flows-watcher.sh†L8-L43】【5d93c6†L1-L3】

## Open gaps & next steps
1. **Bundle the core Compose base** referenced by the pack or update the Makefile instructions so operators know which file to pair with the Firefly/Wger profiles.【F:pmoves/pmoves-integrations-pr-pack/Makefile†L1-L21】
2. **Check in the n8n flow exports** (or document where to source them) so the watcher/import scripts have actionable content.
3. **Harden credentials** by documenting required overrides for secrets and recommending non-default passwords before enabling either integration in shared environments.
4. **Plan data synchronization** into PMOVES (webhooks, ETL jobs, or API bridges) so Firefly and Wger data becomes available to Agent Zero or downstream automations.
