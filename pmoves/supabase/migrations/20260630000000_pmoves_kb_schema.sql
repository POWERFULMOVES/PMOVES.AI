-- PMOVES knowledge-base schema creation and grants
-- Idempotent migration for fresh and existing databases.
-- The schema is also created by the Supabase initdb path (#1899); this
-- migration ensures the same state is replayed on already-initialized DBs.

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE SCHEMA IF NOT EXISTS pmoves_kb;

-- Allow core roles to use the schema and read objects once they exist.
GRANT USAGE ON SCHEMA pmoves_kb TO anon, authenticated, service_role;
GRANT CREATE ON SCHEMA pmoves_kb TO service_role;

-- Default privileges so future tables/functions grant read to app roles.
ALTER DEFAULT PRIVILEGES IN SCHEMA pmoves_kb
  GRANT SELECT ON TABLES TO anon, authenticated, service_role;

ALTER DEFAULT PRIVILEGES IN SCHEMA pmoves_kb
  GRANT SELECT, USAGE ON SEQUENCES TO anon, authenticated, service_role;

ALTER DEFAULT PRIVILEGES IN SCHEMA pmoves_kb
  GRANT EXECUTE ON FUNCTIONS TO anon, authenticated, service_role;

-- Service role can also mutate knowledge-base content.
ALTER DEFAULT PRIVILEGES IN SCHEMA pmoves_kb
  GRANT INSERT, UPDATE, DELETE ON TABLES TO service_role;

COMMENT ON SCHEMA pmoves_kb IS 'PMOVES knowledge-base schema used by HiRAG, grounded personas, and provenance consumers. Search path is configured via PGRST_DB_EXTRA_SEARCH_PATH.';
