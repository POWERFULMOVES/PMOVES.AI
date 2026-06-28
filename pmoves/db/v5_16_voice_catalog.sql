-- v5_16 Voice Catalog — unified multi-engine voice-profile registry (Voice Agents S1).
-- Spec: docs/superpowers/specs/2026-06-26-voice-agents-design.md §3 (contract),
--       §4 (registry decision), §8 (provenance fields), §10 Q9 (RLS owner+grant).
--
-- This is the SOURCE OF TRUTH + routing layer for flute-gateway voice selection
-- across ALL engines (omnivoice/vibevoice/voicebox/ultimate_tts). One row = one
-- resolvable voice. Engines keep their native profile storage; audio lives on the
-- shared JuiceFS/MinIO catalog (ref_audio_path). Idempotent; pmoves_core schema.
--
-- NOT cast_voice_profiles (that table is device/group-scoped, kept as-is).

CREATE SCHEMA IF NOT EXISTS pmoves_core;

CREATE TABLE IF NOT EXISTS pmoves_core.voice_profiles (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Identity
    name               TEXT NOT NULL UNIQUE,                 -- slug, agent-facing selector
    display_name       TEXT,
    description        TEXT,
    tags               JSONB NOT NULL DEFAULT '[]'::jsonb,   -- e.g. ["multilingual","en","mentor"]
    -- Routing (engine-sourced design surface lives under engine_specific)
    engine             TEXT NOT NULL,                        -- omnivoice|vibevoice|voicebox|ultimate_tts
    engine_specific    JSONB NOT NULL DEFAULT '{}'::jsonb,   -- per-engine params (ref_audio/instruct, profile_id, ...)
    -- Media (shared cross-node catalog: JuiceFS target, MinIO interim)
    ref_audio_path     TEXT,                                 -- e.g. juicefs://pmoves-voices/<name>.wav
    sample_path        TEXT,
    sample_rate_hz     INTEGER NOT NULL DEFAULT 24000,
    audio_duration_sec REAL,
    -- Provenance / rights (full record in voice_cloning_provenance, S5; inline mirror here)
    provenance         TEXT,
    rights_basis       TEXT,                                 -- owned|licensed|consented|public_domain|character_owned
    cloned_from        JSONB,
    clone_method       TEXT,
    -- Multitenancy / lifecycle (Q9 RBAC via RLS)
    created_by         UUID,                                 -- auth.uid() owner; NULL = system/service-seeded
    is_public          BOOLEAN NOT NULL DEFAULT false,       -- any authenticated user may read/select
    is_active          BOOLEAN NOT NULL DEFAULT true,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at         TIMESTAMPTZ,
    CONSTRAINT voice_profiles_name_slug  CHECK (name ~ '^[a-zA-Z0-9_-]{3,64}$'),
    CONSTRAINT voice_profiles_engine_chk CHECK (engine IN ('omnivoice','vibevoice','voicebox','ultimate_tts')),
    CONSTRAINT voice_profiles_rights_chk CHECK (
        rights_basis IS NULL OR rights_basis IN
        ('owned','licensed','consented','public_domain','character_owned'))
);

CREATE INDEX IF NOT EXISTS voice_profiles_engine_idx ON pmoves_core.voice_profiles (engine);
CREATE INDEX IF NOT EXISTS voice_profiles_owner_idx  ON pmoves_core.voice_profiles (created_by);
CREATE INDEX IF NOT EXISTS voice_profiles_tags_gin   ON pmoves_core.voice_profiles USING GIN (tags);

-- Sharing grants (Q9: "who may use/clone Alice's voice") ---------------------
CREATE TABLE IF NOT EXISTS pmoves_core.voice_profile_grants (
    voice_profile_id UUID NOT NULL REFERENCES pmoves_core.voice_profiles(id) ON DELETE CASCADE,
    grantee          UUID NOT NULL,                          -- auth.uid()
    can_clone        BOOLEAN NOT NULL DEFAULT false,         -- false = use-only; true = may clone-from
    granted_by       UUID,
    granted_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (voice_profile_id, grantee)
);

-- updated_at touch trigger ----------------------------------------------------
CREATE OR REPLACE FUNCTION pmoves_core.touch_voice_profiles_updated_at()
RETURNS trigger AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_voice_profiles_touch ON pmoves_core.voice_profiles;
CREATE TRIGGER trg_voice_profiles_touch
    BEFORE UPDATE ON pmoves_core.voice_profiles
    FOR EACH ROW EXECUTE FUNCTION pmoves_core.touch_voice_profiles_updated_at();

-- Row Level Security (Q9) -----------------------------------------------------
-- jwt sub (user id) helper: NULLIF guards an empty/absent claim from a uuid cast error.
ALTER TABLE pmoves_core.voice_profiles       ENABLE ROW LEVEL SECURITY;
ALTER TABLE pmoves_core.voice_profile_grants ENABLE ROW LEVEL SECURITY;

-- Services (flute-gateway, creator-operator) use the service key → full bypass.
DROP POLICY IF EXISTS voice_profiles_service_bypass ON pmoves_core.voice_profiles;
CREATE POLICY voice_profiles_service_bypass ON pmoves_core.voice_profiles
    FOR ALL
    USING (current_setting('request.jwt.claim.role', true) = 'service_role');

-- Read: active+undeleted AND (public OR owner OR explicitly granted).
DROP POLICY IF EXISTS voice_profiles_read ON pmoves_core.voice_profiles;
CREATE POLICY voice_profiles_read ON pmoves_core.voice_profiles
    FOR SELECT
    USING (
        is_active AND deleted_at IS NULL AND (
            is_public
            OR created_by = NULLIF(current_setting('request.jwt.claim.sub', true), '')::uuid
            OR EXISTS (
                SELECT 1 FROM pmoves_core.voice_profile_grants g
                WHERE g.voice_profile_id = pmoves_core.voice_profiles.id
                  AND g.grantee = NULLIF(current_setting('request.jwt.claim.sub', true), '')::uuid
            )
        )
    );

-- Owner manages their own rows.
DROP POLICY IF EXISTS voice_profiles_owner_write ON pmoves_core.voice_profiles;
CREATE POLICY voice_profiles_owner_write ON pmoves_core.voice_profiles
    FOR ALL
    USING (created_by = NULLIF(current_setting('request.jwt.claim.sub', true), '')::uuid)
    WITH CHECK (created_by = NULLIF(current_setting('request.jwt.claim.sub', true), '')::uuid);

DROP POLICY IF EXISTS voice_profile_grants_service_bypass ON pmoves_core.voice_profile_grants;
CREATE POLICY voice_profile_grants_service_bypass ON pmoves_core.voice_profile_grants
    FOR ALL
    USING (current_setting('request.jwt.claim.role', true) = 'service_role');

-- Voice owner manages grants on their voices; grantee may read their own grant.
DROP POLICY IF EXISTS voice_profile_grants_owner ON pmoves_core.voice_profile_grants;
CREATE POLICY voice_profile_grants_owner ON pmoves_core.voice_profile_grants
    FOR ALL
    USING (
        EXISTS (
            SELECT 1 FROM pmoves_core.voice_profiles p
            WHERE p.id = voice_profile_grants.voice_profile_id
              AND p.created_by = NULLIF(current_setting('request.jwt.claim.sub', true), '')::uuid
        )
    );

DROP POLICY IF EXISTS voice_profile_grants_grantee_read ON pmoves_core.voice_profile_grants;
CREATE POLICY voice_profile_grants_grantee_read ON pmoves_core.voice_profile_grants
    FOR SELECT
    USING (grantee = NULLIF(current_setting('request.jwt.claim.sub', true), '')::uuid);

-- PostgREST grants (mirror v5_13_pmoves_core_rest_grants.sql) ------------------
DO $$
BEGIN
    EXECUTE 'GRANT USAGE ON SCHEMA pmoves_core TO anon, authenticated, service_role';
    -- Read for anon/authenticated (RLS still gates rows); write for authenticated + service_role.
    EXECUTE 'GRANT SELECT ON pmoves_core.voice_profiles TO anon, authenticated, service_role';
    EXECUTE 'GRANT INSERT, UPDATE, DELETE ON pmoves_core.voice_profiles TO authenticated, service_role';
    EXECUTE 'GRANT SELECT, INSERT, UPDATE, DELETE ON pmoves_core.voice_profile_grants TO authenticated, service_role';
END $$;

COMMENT ON TABLE pmoves_core.voice_profiles IS
    'Unified multi-engine voice registry (Voice Agents S1). Source of truth + routing for flute-gateway voice selection. See docs/superpowers/specs/2026-06-26-voice-agents-design.md.';
