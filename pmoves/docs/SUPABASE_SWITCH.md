**Supabase: Local (CLI) vs Self‑Hosted**

- **Upstream expectation**  
  PMOVES wraps the vanilla Supabase install (the same bundle we publish for Tailscale/Rustdesk/“plain” VPS drops) so contributors can stay aligned with production. The Supabase CLI flow is the reference path because it matches what we ship when deploying the full stack on a VPS (see `pmoves/docs/coolify/pg-dump-coolify-1760101793.dmp` for the exported baseline). Docker Compose is offered as a lightweight fallback when you only need a subset of services locally.

- Local parity via Supabase CLI (recommended for feature completeness)
  - Install: Windows `winget install supabase.supabase` (or `npm i -g supabase`)
  - Init once: `make supa-init`
  - Start: `make supa-start` (brings up full local Supabase)
  - Inspect: `make supa-status` (copy anon/service keys)
  - Point pmoves to CLI endpoints:
    - `make supa-use-local` → writes `.env.local` from `.env.supa.local.example`
    - Edit `.env.local` and paste keys from `make supa-status`
    - Ensure PostgREST uses the full path: `SUPA_REST_URL=http://localhost:54321/rest/v1` (and set `SUPABASE_REST_URL` to the same for tools/n8n)
  - Run pmoves: `make up` (default `SUPA_PROVIDER=cli` avoids Compose Postgres/PostgREST)
  - Stop CLI: `make supa-stop`

- Self‑hosted Supabase (remote)
  - Put your remote endpoints/keys in `.env.supa.remote` (a prefilled template is committed without secrets)
  - Switch: `make supa-use-remote` (copies `.env.supa.remote` → `.env.local`)
  - Run pmoves against remote: `make up`

- Compose‑based Supabase (lightweight alternative)
  - Use if you don’t need every Supabase component locally
  - Start: `SUPA_PROVIDER=compose make up` then `make supabase-up`
  - Stop: `make supabase-stop` or `make down`
  - Reset (if you had an older volume before the 2025‑10‑11 schema updates): `make supabase-clean` then rerun `make supabase-up`

Environment variables to verify
- `SUPA_REST_URL` (PostgREST)
- `GOTRUE_SITE_URL` (Auth/GoTrue)
- `GOTRUE_API_EXTERNAL_URL` (GoTrue external API base, defaults to `http://localhost:9999`)
- `SUPABASE_STORAGE_URL`, `SUPABASE_PUBLIC_STORAGE_BASE`
- `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`
- `SUPABASE_RLIMIT_NOFILE` (Realtime ulimit override, defaults to `1048576`)
- `SUPABASE_REALTIME_APP_NAME` (Realtime identifier, defaults to `realtime`)

Makefile shortcuts
- `up` — starts pmoves stack; in CLI mode, excludes Compose Postgres/PostgREST
- `down` — stops/removes pmoves stack (keeps CLI stack)
- `clean` — removes volumes/orphans for pmoves stack
- `supa-init|supa-start|supa-stop|supa-status` — Supabase CLI control
- `supa-use-local|supa-use-remote` — swap `.env.local` for local vs remote
- `up-cli|up-compose` — run pmoves with CLI or Compose Supabase provider

Notes
- We never commit secrets. Only endpoints are checked in. Keys go into `.env.local` locally.
- If ports collide, stop any older Supabase stacks (e.g., previous compose project names) before starting a new one.
