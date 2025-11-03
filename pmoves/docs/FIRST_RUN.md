# First-Run Bootstrap Overview
_Last updated: 2025-11-03_

`make first-run` is the guided path for bringing a fresh PMOVES checkout online. It chains the critical environment, database, and container steps so operators land on a fully functional stack (Supabase CLI, mesh agents, external integrations, and seeded demo data) without manual orchestration.

## Execution Flow
1. **Environment registry sync** – calls `make bootstrap` which wraps `pmoves/scripts/bootstrap_env.py`. Missing secrets are prompted for (or generated) and written to:
   - `pmoves/env.shared` (branded defaults + shared secrets)
   - `.env.generated` / `env.shared.generated` (CHIT-driven bundles)
   - `pmoves/.env.local` (machine specific overrides)
2. **Supabase backend activation** – detects whether the Supabase CLI stack is running. If not, runs `make supa-start` (CLI mode). When `SUPA_PROVIDER=compose`, it starts the compose overlay instead.
3. **Core services** – `make up` starts the default compose profiles (Qdrant, Neo4j, MinIO, Meilisearch, presign, hi-rag gateways, langextract, extract-worker, render-webhook, pmoves-yt, Jellyfin bridge).
4. **Schema + demo data** – `make bootstrap-data` triggers:
   - `make supabase-bootstrap` → replays `supabase/initdb/*.sql`, `supabase/migrations/*.sql`, `db/v5_12_grounded_personas.sql`, `db/v5_12_seed.sql`
   - `make neo4j-bootstrap` → applies persona aliases and CHIT geometry fixtures
   - `make seed-data` → feeds the hi-rag demo corpus into Qdrant/Meili via `scripts/seed_local.py`
5. **Agent mesh** – `make up-agents` launches NATS, Agent Zero, Archon, mesh-agent, publisher-discord (with defaults sourced from `env.shared`).
6. **External integrations** – `make up-external` starts Wger, Firefly III, Open Notebook (external image), and Jellyfin using the branded credentials in `env.shared`.
7. **Verification harness** – `make smoke` runs the 12-step checklist (Qdrant, Meilisearch, presign, render-webhook, PostgREST, hi-rag query, Agent Zero health, geometry ingest, etc.) to confirm the stack is healthy end-to-end.

The command exits non-zero if any step fails, making it safe to re-run after fixing issues (idempotent operations such as seeds simply noop when state already matches).

## Seeded & Branded Defaults
- **Supabase CLI**: core schema, demo tables, and Supabase Studio at `http://127.0.0.1:65433`.
- **Neo4j**: CHIT mindmap fixture (`/neo4j/cypher/010_chit_geometry_fixture.cypher`) plus seeded personas/aliases.
- **Qdrant / Meilisearch**: hi-rag demo corpus (`pmoves/services/hi-rag-gateway-v2/scripts/seed_local.py`).
- **Wger**: branded PMOVES health portal with admin credentials from `env.shared` (UI at `http://localhost:8000`).
- **Firefly III**: finance automation defaults and API tokens (`http://localhost:8082`).
- **Jellyfin**: media bridge and default libraries (`http://localhost:8096` internal, overlay on `http://localhost:9096` when AI stack enabled).
- **Open Notebook**: Streamlit UI (`http://localhost:8503`) with password/token synced to bricks in `env.shared`.
- **Agent Zero / Archon**: live NATS connection and Supabase credentials enabling full mesh operations out of the box.

## After First Run
- **UI workspace** — `npm install && npm run dev` in `pmoves/ui`. The launcher automatically layers the same env files used by `make first-run`.
- **Evidence capture** — run additional smokes (e.g., `make smoke-wger`, `make jellyfin-verify`) and log results via `make evidence-log`.
- **Additional docs**:
  - [Local Development & Networking](LOCAL_DEV.md) — service ports, Supabase runtime modes, and Cloudflare tunnel guidance.
  - [Local Tooling Reference](LOCAL_TOOLING_REFERENCE.md) — make/CLI helpers, mini CLI commands, env scripts.
  - [External Integrations Bring-Up](../EXTERNAL_INTEGRATIONS_BRINGUP.md) — deeper dives on Wger, Firefly, Jellyfin, Open Notebook runbooks.
  - [PMOVES Docs Index](PMOVES.AI%20PLANS/README_DOCS_INDEX.md) — curated links by integration or roadmap item.

## Re-running portions
- `make bootstrap` – refresh secrets after rotating keys.
- `make bootstrap-data` – replay Supabase/Neo4j/Qdrant seeds.
- `make up`, `make up-agents`, `make up-external` – restart individual layers.
- `make smoke` – re-run the health harness after changes or upgrades.
- `python3 -m pmoves.tools.mini_cli bootstrap --accept-defaults` – non-interactive env refresh + provisioning bundle.

The first-run command is safe to repeat; it will only restart services or reapply seeds where necessary and provides clear output when manual follow-up is required.
