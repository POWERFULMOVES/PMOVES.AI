-- juicefs_meta: a scoped role so JuiceFS stops authenticating as a superuser
-- ============================================================================
-- WHY
-- JuiceFS's metadata DSN currently authenticates as `supabase_admin`, which is
-- `rolsuper = t, rolcreaterole = t` — a full superuser. JuiceFS needs DML on
-- exactly one schema (`juicefs_meta`, 18 live tables on B850); it never needs to
-- create roles, read other schemas, or bypass RLS.
--
-- This matters because of what comes next. Cross-node mounts (4090 / 5090 /
-- jetson) require every node to reach the metadata engine — JuiceFS documents
-- this explicitly: "ensure that all nodes has access to the Metadata Engine".
-- Today that port is unreachable off-box, which is the only remaining blocker.
-- The moment it IS reachable, whatever role the DSN carries becomes a
-- network-exposed auth surface. Exposing a superuser surface is a materially
-- different risk from exposing a single-schema one.
--
-- Least privilege BEFORE reachability, not after.
--
-- ORDERING (deliberate, operator-approved): scoped role -> rotate -> expose.
-- Landing this first is strictly safer than landing it second: once JuiceFS
-- authenticates as `juicefs_meta`, the pending rotation of the previously-leaked
-- `supabase_admin` credential no longer touches the JuiceFS mount at all. It
-- shrinks the rotation's blast radius rather than widening it. The rotation
-- itself stays an operator action — ~27 consumers carry that password and must
-- be funneled + restarted in one window.
--
-- IDEMPOTENT: safe to re-run; creates nothing that already exists.
--
-- WHAT THIS DOES NOT DO
--   * Does not change the running mount. Repointing the DSN is a separate,
--     reviewable step (recreate the container with the new credential), so this
--     migration can land without touching a live filesystem.
--   * Does not grant CREATE on the schema. The volume is already formatted. If a
--     FUTURE volume is formatted against this role, grant CREATE for that
--     operation and revoke it after — do not leave it standing.
--   * Does not set a password. That arrives out-of-band via the CHIT pipeline; a
--     password in a committed migration would be exactly the class of leak this
--     lane exists to close.
--
-- Ref: pmoves/docs/handoffs/juicefs-meta-scoped-role-and-tailnet-exposure-2026-08-18.md
-- ============================================================================

-- NODE-CONDITIONAL BY DESIGN.
-- `make -C pmoves supa-migrate` applies every migration on WHATEVER node it runs,
-- but the JuiceFS metadata engine lives on exactly one host. Measured 2026-08-18:
--     B850 : schema juicefs_meta present, 18 tables   <- the metadata home
--     z890 : schema juicefs_meta ABSENT               <- gateway only
-- An unconditional `GRANT ... ON SCHEMA juicefs_meta` therefore aborts the whole
-- migration run on every node that is not the metadata home. Guarding on schema
-- existence keeps this migration a no-op there instead of a breakage, so it is
-- safe to land in the shared migrations directory.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'juicefs_meta') THEN
    RAISE NOTICE 'schema juicefs_meta not present on this node — skipping (not the metadata home)';
    RETURN;
  END IF;

  -- PRIVILEGE PRECONDITION — skip loudly rather than abort the whole run.
  -- `make -C pmoves supa-migrate` connects as `-U postgres`, but on the metadata
  -- home (B850) the hardened Supabase image leaves `postgres` NON-superuser
  -- (rolsuper = f) while every juicefs_meta object is owned by `supabase_admin`.
  -- Granting on objects you neither own nor superuser-override fails, and
  -- ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin fails outright with
  -- "permission denied to change default privileges". Because a DO block is one
  -- transaction, that error aborts THIS migration — and with ON_ERROR_STOP, the
  -- entire supa-migrate run with it. Detect it and skip instead, so one
  -- owner-scoped migration cannot take down everyone else's.
  IF NOT (
       pg_has_role(current_user, 'supabase_admin', 'USAGE')
       OR (SELECT rolsuper FROM pg_roles WHERE rolname = current_user)
     ) THEN
    RAISE NOTICE 'skipping: % cannot grant on supabase_admin-owned objects. Re-run this migration as supabase_admin on the metadata home.', current_user;
    RETURN;
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
--   * No privileges on public / auth / storage / any other schema
--   * No BYPASSRLS, SUPERUSER, CREATEROLE, CREATEDB, REPLICATION
--   * No database-level GRANT  -> cannot see other databases' objects
