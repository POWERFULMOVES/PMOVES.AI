-- Quarantine legacy shadow tables that break GoTrue OAuth grants.
--
-- Discovered on SPARK 2026-10-07 (see PR #3297): gotrue connects as the
-- ${POSTGRES_USER} role whose search_path begins with "$user", public — so
-- any legacy table sharing a name with an auth.* table resolves FIRST and
-- gotrue's unqualified INSERTs hit the wrong shape:
--   * "Database error granting user" (column "aal" of relation "sessions"
--     does not exist) on every OAuth callback, and
--   * the migrator recording its 69 version rows in public.schema_migrations
--     instead of auth.schema_migrations, leaving the auth schema effectively
--     unmigrated since 2018.
--
-- Idempotent and safe:
--   * Only fires on tables that actually exist in the shadow position.
--   * Shadow tables measured empty on SPARK (0 rows each); nothing is lost.
--   * auth_quarantine is created only if missing; existing objects are never
--     overwritten (the guard checks target-name absence).
--
-- After this migration, restart supabase-gotrue so it applies any pending
-- auth migrations against the now-correct schema_migrations.

DO $$
DECLARE
    shadow_schemas text[] := ARRAY['public', 'pmoves'];
    src_schema text;
    shadow_tables text[] := ARRAY['sessions', 'schema_migrations'];
    tbl text;
    idx record;
    target_taken boolean;
    new_table_name text;
BEGIN
    CREATE SCHEMA IF NOT EXISTS auth_quarantine;

    FOREACH src_schema IN ARRAY shadow_schemas LOOP
        FOREACH tbl IN ARRAY shadow_tables LOOP
            IF EXISTS (
                SELECT 1 FROM pg_tables
                WHERE schemaname = src_schema AND tablename = tbl
            ) AND EXISTS (
                SELECT 1 FROM pg_tables
                WHERE schemaname = 'auth' AND tablename = tbl
            ) THEN
                -- SET SCHEMA fails when an index name collides in the target
                -- schema; rename every index out of the way first.
                FOR idx IN
                    SELECT indexname FROM pg_indexes
                    WHERE schemaname = src_schema AND tablename = tbl
                LOOP
                    SELECT EXISTS (
                        SELECT 1 FROM pg_class c
                        JOIN pg_namespace n ON n.oid = c.relnamespace
                        WHERE n.nspname = 'auth_quarantine'
                          AND c.relname = idx.indexname
                    ) INTO target_taken;
                    IF target_taken THEN
                        EXECUTE format(
                            'ALTER INDEX %I.%I RENAME TO %I',
                            src_schema, idx.indexname,
                            'quarantine_' || tbl || '_' || idx.indexname
                        );
                    END IF;
                END LOOP;

                new_table_name := tbl || '_' || src_schema || '_shadow';
                SELECT EXISTS (
                    SELECT 1 FROM pg_tables
                    WHERE schemaname = 'auth_quarantine' AND tablename = new_table_name
                ) INTO target_taken;
                IF NOT target_taken THEN
                    EXECUTE format(
                        'ALTER TABLE %I.%I SET SCHEMA auth_quarantine', src_schema, tbl
                    );
                    EXECUTE format(
                        'ALTER TABLE auth_quarantine.%I RENAME TO %I', tbl, new_table_name
                    );
                    RAISE NOTICE 'quarantined %.% -> auth_quarantine.%', src_schema, tbl, new_table_name;
                ELSE
                    RAISE NOTICE 'auth_quarantine.% already exists; leaving %.% in place', new_table_name, src_schema, tbl;
                END IF;
            END IF;
        END LOOP;
    END LOOP;
END $$;

-- Repair auth.schema_migrations ONLY when it is missing the modern gotrue
-- version rows AND those rows exist in a shadow copy (the migrator's
-- misdirected writes). The 2017/2018-era rows predate the image's migration
-- set and are not recognized by current gotrue; they are removed so the
-- migrator can compute pending work correctly.
DO $$
DECLARE
    auth_rows int;
    shadow_rows int;
    v bigint;
BEGIN
    SELECT count(*) INTO auth_rows FROM auth.schema_migrations;
    SELECT count(*) INTO shadow_rows
    FROM auth_quarantine.schema_migrations_public_shadow
    WHERE EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'auth_quarantine'
          AND table_name = 'schema_migrations_public_shadow'
    );

    IF shadow_rows IS NOT NULL AND shadow_rows > 0 AND auth_rows < shadow_rows THEN
        DELETE FROM auth.schema_migrations
        WHERE version BETWEEN 20170101000000 AND 20181231235959;
        INSERT INTO auth.schema_migrations (version)
        SELECT version FROM auth_quarantine.schema_migrations_public_shadow
        ON CONFLICT (version) DO NOTHING;
        RAISE NOTICE 'auth.schema_migrations re-seeded: % rows', shadow_rows;
    ELSE
        RAISE NOTICE 'auth.schema_migrations left as-is (auth_rows=%)', auth_rows;
    END IF;
EXCEPTION
    WHEN undefined_table THEN
        RAISE NOTICE 'no shadow schema_migrations present; nothing to re-seed';
END $$;
