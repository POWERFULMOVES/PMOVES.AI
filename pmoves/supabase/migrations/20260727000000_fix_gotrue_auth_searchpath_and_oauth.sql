-- Repair GoTrue auth on nodes where the auth schema was seeded with a forked/newer
-- migration set. Symptoms fixed:
--   1. GoTrue connects as the generic `pmoves` role, whose search_path is empty, so
--      its unqualified `users`/`identities` queries resolve in `public` and 500
--      ("relation does not exist", 42P01) — all auth broken.
--   2. `auth.oauth_clients` was seeded in the newer OAuth2.1 shape (`client_type`,
--      `token_endpoint_auth_method`, NO `client_id`), so GoTrue v2.191's migration
--      `20250731_add_oauth_clients_table` fatals on `CREATE INDEX ... (client_id)`
--      and crash-loops.
--
-- Idempotent and safe on healthy deployments:
--   * The oauth-table reset ONLY fires when `oauth_clients` exists WITHOUT `client_id`
--     (the broken forked shape). On a healthy node it's a no-op (client_id present,
--     or the table not created yet). These OAuth2-SERVER client tables are unused by
--     password / external-provider (Google, GitHub) login, and are empty by
--     definition in this broken state, so dropping them loses nothing — GoTrue
--     recreates `oauth_clients` in its own expected shape on next start.
--   * The search_path grant is a durable, harmless default (auth as a fallback after
--     public). The proper long-term fix is repointing GoTrue to `supabase_auth_admin`
--     (which ships search_path=auth); this unblocks login without that role's
--     password reset. See pmoves/docs/handoffs/gotrue-auth-schema-repair-2026-07-25.md.

DO $$
BEGIN
  IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'auth' AND table_name = 'oauth_clients'
     )
     AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'auth' AND table_name = 'oauth_clients'
          AND column_name = 'client_id'
     )
  THEN
    DROP TABLE IF EXISTS auth.oauth_clients CASCADE;
    DROP TABLE IF EXISTS auth.custom_oauth_providers CASCADE;
    DROP TABLE IF EXISTS auth.oauth_authorizations CASCADE;
    DROP TABLE IF EXISTS auth.oauth_client_states CASCADE;
    RAISE NOTICE 'GoTrue repair: dropped forked oauth tables (no client_id) — GoTrue recreates oauth_clients on restart';
  ELSE
    RAISE NOTICE 'GoTrue repair: oauth_clients healthy or absent — no reset needed';
  END IF;
END $$;

-- Ensure the role GoTrue connects as can resolve unqualified auth.* relations.
ALTER ROLE pmoves IN DATABASE pmoves SET search_path TO "$user", public, auth;
