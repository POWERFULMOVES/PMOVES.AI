-- Revoke PUBLIC and anon EXECUTE on SECURITY DEFINER functions in `public`.
--
-- Why this exists as a migration rather than a one-off: the grants were never
-- authored. `20260325110000_publisher_publish_state.sql` and both 20260326*
-- migrations contain ZERO GRANT statements. anon/authenticated/service_role
-- EXECUTE comes from Supabase's stock default privileges on `public`, so a
-- volume reset or a fresh node re-grants it and the hardening silently
-- disappears. Applied by hand on B850 2026-08-23; this makes it reproducible.
--
-- What the grants actually meant:
--   claim_/complete_/fail_studio_board_publish are SECURITY DEFINER and owned
--   by supabase_admin (rolsuper), so they execute AS a superuser and bypass
--   RLS. Meanwhile the schema's own policies say:
--     publisher_audit_svc        service_role   USING true  WITH CHECK true
--     publisher_audit_auth_read  authenticated  read-only
--     publisher_audit_anon_deny  anon           USING false WITH CHECK false
--   and detections / segments / emotions / studio_board have RLS enabled with
--   NO anon policy at all. So anon is explicitly denied everywhere it is
--   named -- and held EXECUTE on three functions that write studio_board as a
--   superuser regardless.
--
-- Why no consumer breaks: the publisher (services/publisher + services/common/
-- supabase.py) does direct inserts into those RLS-protected tables, which an
-- anon-key client cannot do. It must be service_role, and service_role keeps
-- its explicit grant. authenticated keeps its own.
--
-- PUBLIC is revoked for the same reason one level up: every role inherits
-- PUBLIC, which is how the scoped juicefs_meta role -- a LOGIN role that
-- pg_hba now admits from the tailnet -- ended up holding superuser-execution
-- rights it was created specifically not to have.
--
-- Idempotent: REVOKE on an already-revoked grantee is a no-op.

DO $$
DECLARE
  f record;
  has_anon boolean := EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon');
BEGIN
  FOR f IN
    SELECT p.oid::regprocedure AS sig
    FROM pg_proc p
    JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname = 'public' AND p.prosecdef
  LOOP
    -- PUBLIC is a pseudo-role and always revocable.
    EXECUTE format('REVOKE EXECUTE ON FUNCTION %s FROM PUBLIC', f.sig);
    -- anon is created by scripts/supabase/bootstrap_db.sh, which is a DIFFERENT
    -- entrypoint from supabase-bootstrap and not ordered against it. REVOKE on a
    -- non-existent role raises, so guard it: on a database where anon does not
    -- exist yet there is nothing to revoke, and the PUBLIC revoke above already
    -- removes what anon would otherwise inherit on creation.
    IF has_anon THEN
      EXECUTE format('REVOKE EXECUTE ON FUNCTION %s FROM anon', f.sig);
    END IF;
  END LOOP;
END $$;

-- Assert the intended end state rather than trusting the loop.
--
-- Only name roles that EXIST. has_function_privilege() raises
-- `role "x" does not exist`, and on a fresh database this migration runs BEFORE
-- the seed that creates juicefs_meta: supabase-bootstrap does
-- `apply_dir migration supabase/migrations` and only then
-- `apply_dir seed supabase/initdb`, where 00_3_juicefs_meta_role.sql lives.
-- Naming it unguarded would fail the migration, leave it unrecorded in
-- pmoves_bootstrap_history, and skip the hardening -- on exactly the rebuild
-- path this file exists to secure.
DO $$
DECLARE
  n int;
  r text;
BEGIN
  FOREACH r IN ARRAY ARRAY['anon','juicefs_meta'] LOOP
    CONTINUE WHEN NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r);
    SELECT count(*) INTO n
      FROM pg_proc p JOIN pg_namespace ns ON ns.oid = p.pronamespace
     WHERE ns.nspname = 'public' AND p.prosecdef
       AND has_function_privilege(r, p.oid, 'EXECUTE');
    IF n <> 0 THEN
      RAISE EXCEPTION 'revoke incomplete: % still holds EXECUTE on % secdef function(s)', r, n;
    END IF;
  END LOOP;

  -- PUBLIC always exists, so this half is unconditional. An empty grantee in
  -- proacl (`=X/owner`) IS the PUBLIC grant.
  SELECT count(*) INTO n
    FROM pg_proc p JOIN pg_namespace ns ON ns.oid = p.pronamespace
   WHERE ns.nspname = 'public' AND p.prosecdef
     AND EXISTS (SELECT 1 FROM unnest(coalesce(p.proacl, ARRAY[]::aclitem[])) a
                  WHERE a::text LIKE '=%');
  IF n <> 0 THEN
    RAISE EXCEPTION 'revoke incomplete: PUBLIC still holds EXECUTE on % secdef function(s)', n;
  END IF;

  -- And do not over-revoke: the roles the publisher actually uses must keep it.
  FOREACH r IN ARRAY ARRAY['service_role','authenticated'] LOOP
    CONTINUE WHEN NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r);
    IF EXISTS (
      SELECT 1 FROM pg_proc p JOIN pg_namespace ns ON ns.oid = p.pronamespace
       WHERE ns.nspname = 'public' AND p.prosecdef
         AND NOT has_function_privilege(r, p.oid, 'EXECUTE')
    ) THEN
      RAISE EXCEPTION 'over-revoked: % lost EXECUTE on a secdef function it needs', r;
    END IF;
  END LOOP;
END $$;
