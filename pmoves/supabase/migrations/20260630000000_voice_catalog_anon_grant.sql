-- Corrective migration: grant anon SELECT on voice_profile_grants.
--
-- 20260628000000_voice_catalog.sql (v5_16 mirror, merged via #1909) granted anon
-- SELECT on pmoves_core.voice_profiles, but the voice_profiles_read RLS policy
-- references pmoves_core.voice_profile_grants in an EXISTS subquery — and that table
-- was granted only TO authenticated, service_role. PostgreSQL evaluates a policy
-- subquery's table privilege with the CALLER's grants, so anon reads of public
-- profiles fail with "permission denied for table voice_profile_grants"
-- (Codex P2 on #1909). RLS still returns 0 grant rows for anon (no policy matches a
-- NULL auth.uid()), so the EXISTS correctly evaluates false and is_public rows return.
--
-- The canonical source of truth (pmoves/db/v5_16_voice_catalog.sql) is fixed in the
-- same PR; this corrective reconciles any DB that already applied the 20260628 mirror.
-- Idempotent: GRANT is a no-op if already present; guarded on table existence.
DO $$
BEGIN
    IF to_regclass('pmoves_core.voice_profile_grants') IS NOT NULL THEN
        EXECUTE 'GRANT SELECT ON pmoves_core.voice_profile_grants TO anon';
    END IF;
END $$;
