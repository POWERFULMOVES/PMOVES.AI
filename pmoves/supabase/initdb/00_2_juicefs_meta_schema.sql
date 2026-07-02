-- =============================================================================
-- juicefs_meta schema — JuiceFS Postgres metadata engine (Phase 3)
-- =============================================================================
-- Operator decision 2026-06-28: JuiceFS uses POSTGRES metadata on supabase-db
-- (revisit Redis-vs-Postgres for the multi-node backend in Phase 4).
--
-- JuiceFS connects with:
--   JUICEFS_META_URL=postgres://<user>:<pass>@supabase-db:5432/postgres?search_path=juicefs_meta&sslmode=disable
-- and creates its metadata tables in this schema. The schema must exist before
-- `juicefs format` runs.
--
-- Dedicated new seed filename (not an edit to an existing seed) so
-- `make supabase-bootstrap` applies it on BOTH fresh and already-bootstrapped
-- databases — see the pmoves_kb seed (00_1) for the same rationale.

create schema if not exists juicefs_meta;
