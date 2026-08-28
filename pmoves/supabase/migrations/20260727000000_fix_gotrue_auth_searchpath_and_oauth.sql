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
DECLARE
  _oauth_row_count INTEGER;
  _target_role TEXT;
  _target_db TEXT;
BEGIN
  -- Determine the active role and database dynamically (Codex P1: avoid hard-coding).
  -- Default to 'pmoves' for compose, but fall back to 'postgres' for CLI path.
  SELECT COALESCE(
    (SELECT rolname FROM pg_roles WHERE rolname = 'pmoves'),
    (SELECT rolname FROM pg_roles WHERE rolname = 'postgres')
  ) INTO _target_role;

  _target_db := current_database();

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
    -- Codex P1: check ALL oauth tables for data before dropping.
    SELECT COALESCE(SUM(cnt), 0) INTO _oauth_row_count FROM (
      SELECT count(*) AS cnt FROM auth.oauth_clients
      UNION ALL
      SELECT count(*) AS cnt FROM auth.custom_oauth_providers WHERE EXISTS (
        SELECT 1 FROM information_schema.tables WHERE table_schema = 'auth' AND table_name = 'custom_oauth_providers'
      )
      UNION ALL
      SELECT count(*) AS cnt FROM auth.oauth_authorizations WHERE EXISTS (
        SELECT 1 FROM information_schema.tables WHERE table_schema = 'auth' AND table_name = 'oauth_authorizations'
      )
      UNION ALL
      SELECT count(*) AS cnt FROM auth.oauth_client_states WHERE EXISTS (
        SELECT 1 FROM information_schema.tables WHERE table_schema = 'auth' AND table_name = 'oauth_client_states'
      )
    ) AS totals;

    IF _oauth_row_count > 0 THEN
      RAISE EXCEPTION 'GoTrue repair REFUSED: oauth tables contain % rows. Back up or migrate data before re-running.', _oauth_row_count
        USING HINT = 'These tables have data — dropping them would be destructive. Export rows, then re-run.';
    END IF;

    DROP TABLE IF EXISTS auth.oauth_clients CASCADE;
    DROP TABLE IF EXISTS auth.custom_oauth_providers CASCADE;
    DROP TABLE IF EXISTS auth.oauth_authorizations CASCADE;
    DROP TABLE IF EXISTS auth.oauth_client_states CASCADE;
    RAISE NOTICE 'GoTrue repair: dropped forked oauth tables (empty, no client_id) — GoTrue recreates oauth_clients on restart';
  ELSE
    RAISE NOTICE 'GoTrue repair: oauth_clients healthy or absent — no reset needed';
  END IF;

  -- Set search_path on the dynamically-resolved role (Codex P1 fix).
  IF _target_role IS NOT NULL THEN
    EXECUTE format('ALTER ROLE %I IN DATABASE %I SET search_path TO "$user", public, auth', _target_role, _target_db);
    RAISE NOTICE 'GoTrue repair: set search_path on role % in database %', _target_role, _target_db;
  ELSE
    RAISE NOTICE 'GoTrue repair: no target role found (neither pmoves nor postgres) — skipping search_path grant';
  END IF;
END $$;
