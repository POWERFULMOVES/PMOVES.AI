-- =============================================================================
-- juicefs_meta role — scoped DML login for the JuiceFS Postgres metadata engine
-- =============================================================================
-- A SEED, not a migration, and that placement is the whole point.
--
-- `make -C pmoves supabase-bootstrap` applies `supabase/migrations` BEFORE
-- `supabase/initdb` (Makefile: `apply_dir migration ...; apply_dir seed ...`),
-- and the juicefs_meta SCHEMA is created by a seed — 00_2_juicefs_meta_schema.sql.
-- As a migration this role DDL therefore ran while its own schema did not exist
-- yet on a fresh database. It guarded on that, returned cleanly, and psql exited
-- 0 — which is exactly what apply_dir records as "applied":
--
--     if admin_psql < "$f"; then INSERT INTO public.pmoves_bootstrap_history ...
--
-- The filename was then in the ledger forever, so the role was never created on
-- any database bootstrapped from scratch. It worked only where the schema
-- already existed from an earlier seed run — i.e. on the machine it was
-- developed on, and not after a rebuild. For a control whose purpose is to
-- retire a superuser credential, that is the worst possible failure shape.
--
-- Sorting after 00_2_ (LC_ALL=C) means the schema is guaranteed present, so the
-- schema-existence guard is deleted rather than fixed — the dependency is
-- satisfied by construction.
--
-- Same rationale as 00_1_pmoves_kb_schema.sql and 00_2: a dedicated new seed
-- filename applies on BOTH fresh and already-bootstrapped databases.
--
-- Idempotent: the role is created only if absent, and GRANT is idempotent, so
-- re-running is a no-op and the ledger recording it is honest.
--
-- Ref: pmoves/docs/handoffs/juicefs-meta-scoped-role-and-tailnet-exposure-2026-08-18.md
-- =============================================================================

DO $$
BEGIN
  -- PRIVILEGE PRECONDITION. supabase-bootstrap applies seeds as supabase_admin,
  -- so this should be unreachable on the canonical path; kept as a cheap
  -- assertion because granting on objects owned by another role fails, and a
  -- DO block is one transaction — under ON_ERROR_STOP that would abort the whole
  -- bootstrap rather than just this file.
  IF NOT (
       pg_has_role(current_user, 'supabase_admin', 'USAGE')
       OR (SELECT rolsuper FROM pg_roles WHERE rolname = current_user)
     ) THEN
    RAISE EXCEPTION 'juicefs_meta role seed must run as supabase_admin or a superuser (current_user = %)', current_user;
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'juicefs_meta') THEN
    -- NOLOGIN until the operator sets a password via the secrets pipeline.
    -- A login-capable role with no password is a worse default than one that
    -- cannot log in yet.
    CREATE ROLE juicefs_meta NOLOGIN;
    RAISE NOTICE 'created role juicefs_meta (NOLOGIN until a password is set)';
  ELSE
    RAISE NOTICE 'role juicefs_meta already exists — leaving as-is';
  END IF;

  -- Reach the schema, but do not create in it.
  EXECUTE 'GRANT USAGE ON SCHEMA juicefs_meta TO juicefs_meta';

  -- DML on the metadata tables. JuiceFS reads, writes, updates and deletes rows;
  -- it does not need DDL on an already-formatted volume.
  EXECUTE 'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA juicefs_meta TO juicefs_meta';

  -- JuiceFS allocates inodes/chunks from sequences.
  EXECUTE 'GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA juicefs_meta TO juicefs_meta';

  -- Tables added later in this schema (e.g. by a future JuiceFS version's own
  -- migration) inherit the same grants, so this does not silently rot.
  -- FOR ROLE supabase_admin: default privileges are per-creating-role, and
  -- supabase_admin is what formats/upgrades the volume today.
  EXECUTE 'ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA juicefs_meta '
          'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO juicefs_meta';
  EXECUTE 'ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA juicefs_meta '
          'GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO juicefs_meta';

  RAISE NOTICE 'juicefs_meta role granted DML on schema juicefs_meta';
END
$$;
-- Explicitly NOT granted, and why:
--   * No CREATE on the schema  -> cannot add or drop tables
--   * This seed grants no privileges on public / auth / storage / any other
--     schema. NOT the same as the role HAVING none: PostgreSQL grants EXECUTE
--     on functions to PUBLIC by default and every role inherits PUBLIC, and
--     this database defines SECURITY DEFINER functions in public (e.g.
--     public.complete_studio_board_publish, initdb/18_publisher_publish_state.sql)
--     with no REVOKE ... FROM PUBLIC anywhere under pmoves/supabase/. While the
--     role is NOLOGIN this is inert. BEFORE granting LOGIN, revoke the PUBLIC
--     execute set or accept that a compromised JuiceFS credential can call those
--     RPCs. That is a database-wide policy decision, deliberately not made here.
--   * No BYPASSRLS, SUPERUSER, CREATEROLE, CREATEDB, REPLICATION
--   * No database-level GRANT  -> cannot see other databases' objects
