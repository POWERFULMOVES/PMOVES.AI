# Supabase (Full Stack) with PMOVES

PMOVES ships a minimal stub (Postgres + PostgREST) for fast dev. For full features (Auth/GoTrue, Realtime, Storage/avatars, Studio), use one of:

Option A — Supabase CLI (default via helper)
- Install: https://supabase.com/docs/guides/cli
- Start: `supabase start` (or use `./scripts/pmoves.ps1 up-fullsupabase` which calls the CLI if present)
- Get REST URL: usually `http://localhost:54321/rest/v1` and anon key from CLI output.
- Update PMOVES `.env`:
  - `SUPA_REST_URL=http://localhost:54321/rest/v1`
  - If enabling strict RLS: set headers in services (not necessary for local permissive dev).
- Start PMOVES: `./scripts/pmoves.ps1 up`

Option B — Compose (fallback)
- A companion compose file is provided: `docker-compose.supabase.yml`.
- Start full PMOVES + Supabase (only if CLI not installed):
  - `docker compose -f docker-compose.yml -f docker-compose.supabase.yml --profile data --profile workers up -d`
- Services (host ports):
  - GoTrue/Auth: 9999
  - Realtime: 4000
  - Storage API: 5000
  - Studio UI: 54323 (open http://localhost:54323)
- Env (see `.env.example`):
  - `SUPABASE_JWT_SECRET`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_REALTIME_SECRET`

Avatars (Storage)
- Create bucket `avatars` in Studio.
- Upload images and generate public URLs (set public policy for dev).
- PMOVES services can store avatar URLs in Supabase tables and serve to UIs.

Realtime
- Enable Realtime on tables (e.g., `studio_board`, `it_errors`) in Studio.
- Subscribe with a client to broadcast updates (out of scope here, example listeners can be added on request).

Notes
- The Compose setup is simplified for local use and not hardened for production. It omits some Supabase platform glue (edge runtime, meta services), pins versions, and uses a basic Storage file backend. It’s suitable for demos and local dev, but the Supabase CLI or official deployment guides are the stable paths long‑term.
- For self-hosted production, prefer Supabase’s official deployment guides or the Supabase CLI in “prod” mode.
