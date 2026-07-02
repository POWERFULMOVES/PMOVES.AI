# Spec: z890 Infra Blockers — PostgREST, Host Network, Bootstrap

## Objective
Close the three z890/infra-owned blockers from `reviews/HOST_ACCESS_AND_BLOCKERS_HANDOFF_2026-06-26.md`:

1. PostgREST `PGRST125` / `pmoves_kb` schema gap — ensure `pmoves_kb` is created and accessible, and PostgREST searches it by default.
2. Host network `pmoves_public` + port-bind defaults — add a non-internal bridge network for services that need host reachability, with safe `127.0.0.1` binds by default.
3. `make supabase-bootstrap` DB user bug — switch bootstrap psql commands from `postgres` user/database to the `pmoves` user/database.

## Assumptions
- The project uses `POSTGRES_USER=pmoves`, `POSTGRES_DB=pmoves` in `env.tier-supabase`.
- `#1899` already creates `pmoves_kb` in the Supabase initdb path; this spec adds a self-contained idempotent migration in `pmoves/supabase/migrations/` for replay on existing databases.
- Services needing external host access are Kong (proxy + admin), PostgREST (debug), and optionally Supabase Studio/GoTrue. We start with Kong and PostgREST.

## Files to change
- `pmoves/supabase/migrations/20260630000000_pmoves_kb_schema.sql`
- `pmoves/docker-compose.yml` — add `pmoves_public` network, attach Kong + postgrest, add `PGRST_DB_EXTRA_SEARCH_PATH`, tighten Kong bind.
- `pmoves/env.tier-supabase.example` — add `PGRST_DB_EXTRA_SEARCH_PATH`.
- `pmoves/Makefile` — change `supabase-bootstrap` and `supabase-bootstrap-no-start` to use `pmoves` user/db.

## Commands (verification)
- `python3 -m py_compile pmoves/tools/validate_migrations.py` (if exists)
- `docker compose -f pmoves/docker-compose.yml config` must validate.
- `make -C pmoves supabase-bootstrap` must apply migrations idempotently.

## Boundaries
- Always: keep migrations idempotent (`CREATE SCHEMA IF NOT EXISTS`, `GRANT`, default privileges).
- Ask first: changing JWT/CHIT settings or exposing services beyond `127.0.0.1`.
- Never: commit secrets, remove the internal `pmoves_*` networks, or bind Kong to `0.0.0.0` by default.

## Success criteria
- `PGRST_DB_EXTRA_SEARCH_PATH=pmoves_core,pmoves_kb,public` appears in PostgREST container env.
- `pmoves_kb` schema exists with grants for `anon`, `authenticated`, `service_role`.
- `docker compose config` shows a `pmoves_public` network and Kong/PostgREST attached to it.
- `make supabase-bootstrap` uses `psql -U pmoves -d pmoves` and idempotently skips already-applied migrations.

## Open questions
- Should `pmoves_public` also carry GoTrue/Realtime/Studio ports? Start with Kong + PostgREST only; expand later if needed.
- Does `supabase-db` need to remain on internal-only `pmoves_data`? Yes.
