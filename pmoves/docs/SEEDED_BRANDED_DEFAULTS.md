# Seeded & Branded Defaults

This note summarizes the default logins, URLs, and branded settings that
`make first-run` applies across the PMOVES stack. It is the canonical reference
for initial credentials; rotate everything after first bring-up and update
`pmoves/env.shared` accordingly.

## Core Data Plane

- **Supabase CLI**
  - Schema and demo tables applied via `supabase/initdb/*.sql` and
    `supabase/migrations/*.sql`.
  - Supabase Studio at `http://127.0.0.1:65433`.
  - Boot operator created by `make supabase-boot-user`:
    - Email / password / JWT written to `pmoves/env.shared` and `pmoves/.env.local`:
      - `SUPABASE_BOOT_USER_EMAIL`
      - `SUPABASE_BOOT_USER_PASSWORD`
      - `SUPABASE_BOOT_USER_JWT`

- **Neo4j**
  - CHIT mindmap fixture from `/neo4j/cypher/010_chit_geometry_fixture.cypher`.
  - Seeded personas and aliases used by the geometry/CHIT demos.

- **Qdrant / Meilisearch**
  - Hi‑RAG demo corpus seeded via
    `pmoves/services/hi-rag-gateway-v2/scripts/seed_local.py`.

## External Integrations (Branded)

These services read their branding and initial credentials from `pmoves/env.shared`.
The exact values are commented in `pmoves/env.shared.example`; replace them with
your own before or after `make first-run`.

- **Wger**
  - PMOVES Health Portal at `http://localhost:8000`.
  - Branded via `WGER_BRAND_*` env vars:
    - `WGER_BRAND_SITE_NAME`
    - `WGER_BRAND_GYM_NAME`
    - `WGER_BRAND_GYM_CITY`
    - `WGER_BRAND_ADMIN_FIRST_NAME` / `WGER_BRAND_ADMIN_LAST_NAME`
    - `WGER_BRAND_ADMIN_EMAIL`
    - `WGER_BRAND_ADMIN_USERNAME`
  - Admin password is initially the upstream default until you change it in the
    UI or override via env; see `pmoves/docs/FIREFLY_WGER_INTEGRATIONS_STATUS.md`
    and upstream Wger docs for rotation notes.

- **Firefly III**
  - Finance portal at `http://localhost:8082`.
  - Tokens/CLI access driven by:
    - `FIREFLY_ACCESS_TOKEN`
    - `FIREFLY_CMD_LN_TOKEN`
    - `FIREFLY_PA_TOKEN_NAME`

- **Jellyfin / Jellyfin AI**
  - Core Jellyfin UI at `http://localhost:8096`.
  - AI overlay UI at `http://localhost:9096` with gateway at `http://localhost:8300`
    when `make -C pmoves up-jellyfin-ai` is used.
  - PMOVES env:
    - `JELLYFIN_URL`, `JELLYFIN_PUBLIC_BASE_URL`, `JELLYFIN_PUBLISHED_URL`
    - `JELLYFIN_API_KEY`, `JELLYFIN_USER_ID`
  - Confirm the admin user and API key in the Jellyfin UI and keep these env
    values in sync when you rotate.

- **Invidious**
  - UI at `http://127.0.0.1:3005` (when `make -C pmoves up-invidious` is used).
  - Defaults follow the upstream image:
    - Admin user: `kemal`
    - Password: the default set by the container on first boot (rotate immediately; see upstream Invidious docs).
  - PMOVES env:
    - `INVIDIOUS_BASE_URL`, `INVIDIOUS_COMPANION_URL`, `INVIDIOUS_COMPANION_PUBLIC_URL`
    - Database credentials seeded with:
      - `INVIDIOUS_PG_DB`
      - `INVIDIOUS_PG_USER`
      - `INVIDIOUS_PG_PASSWORD`
    - HMAC/companion keys:
      - `INVIDIOUS_HMAC_KEY`
      - `INVIDIOUS_COMPANION_KEY`
  - When you rotate keys or credentials, update `pmoves/env.shared` and rerun
    `make env-setup` before restarting the Invidious stack.

- **Open Notebook**
  - UI at `http://localhost:8503` (Streamlit + SurrealDB).
  - Initial branded login:
    - `OPEN_NOTEBOOK_PASSWORD` — UI password.
    - `OPEN_NOTEBOOK_API_TOKEN` — bearer token for API access.
  - In the PMOVES bundle these are expected to be identical so that agents,
    CLI helpers, and the UI all share the same secret; keep them in lockstep
    when rotating.

## Agents & Orchestration

- **Agent Zero / Archon**
  - `make up-agents` / `make up-agents-ui` start:
    - Agent Zero (supervisor + UI): `http://localhost:8080` / `http://localhost:8081`.
    - Archon API: `http://localhost:8091/healthz`.
    - Archon UI: `http://localhost:3737`.
  - Both services rely on Supabase keys from `pmoves/env.shared`:
    - `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` (service role).
    - `SUPA_REST_URL` for REST queries (`/rest/v1`).
  - See `pmoves/docs/services/agent-zero/README.md` and
    `pmoves/docs/services/archon/README.md` for detailed env contracts.

## After Rotating Credentials

Whenever you rotate any of the branded credentials above:

1. Update `pmoves/env.shared` with the new values.
2. Run:

   ```bash
   make env-setup
   make env-check
   ```

3. Restart the affected services (e.g., `make -C pmoves up-external`,
   `make -C pmoves up-agents`).
4. If CI or remote deployments rely on the same keys, update the corresponding
   GitHub/vault secrets and use `pmoves/tools/secrets_sync.py` to validate.
