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
    -- Grounding: ties a voice to the grounded-persona / consciousness-shape substrate
    -- (v5_12/v5_14 personas, v5_15 consciousness). A voice is part of an agent's grounded
    -- identity (MOF/prosodic), not a bare clip — it may be grounded in a MIX of paradigm
    -- leaders/proponents, or map a social-media personality back to a consciousness shape.
    -- Shape (resolved by flute-gateway/consciousness at startup grounding). Keys map to
    -- the real substrate PKs: persona_ids → v5_12 pmoves_core.personas.persona_id (uuid);
    -- consciousness_theory_id → v5_15 pmoves_core.consciousness_theories.id (text):
    --   {"persona_ids":[...], "consciousness_theory_id":"...", "paradigm":"...",
    --    "proponents":[{"name":"...","weight":0.5,"ref_audio":"..."}], "blend":"weighted"}
    -- NOTE: paradigm/proponents have no backing table yet — the canonical grounding shape
    -- is pinned in the design spec §3 and validated in the S1b loader/validate path.
    grounding          JSONB NOT NULL DEFAULT '{}'::jsonb,
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
    -- JSON/media shape integrity (CodeRabbit): writers can't persist malformed
    -- payloads that break tag filtering or gateway routing.
    CONSTRAINT voice_profiles_tags_array_chk       CHECK (jsonb_typeof(tags) = 'array'),
    CONSTRAINT voice_profiles_engine_specific_chk  CHECK (jsonb_typeof(engine_specific) = 'object'),
    CONSTRAINT voice_profiles_grounding_object_chk CHECK (jsonb_typeof(grounding) = 'object'),
    CONSTRAINT voice_profiles_sample_rate_chk      CHECK (sample_rate_hz > 0),
    CONSTRAINT voice_profiles_audio_duration_chk   CHECK (audio_duration_sec IS NULL OR audio_duration_sec >= 0),
    CONSTRAINT voice_profiles_engine_chk CHECK (engine IN ('omnivoice','vibevoice','voicebox','ultimate_tts')),
    CONSTRAINT voice_profiles_rights_chk CHECK (
        rights_basis IS NULL OR rights_basis IN
        ('owned','licensed','consented','public_domain','character_owned'))
);

CREATE INDEX IF NOT EXISTS voice_profiles_engine_idx ON pmoves_core.voice_profiles (engine);
CREATE INDEX IF NOT EXISTS voice_profiles_owner_idx  ON pmoves_core.voice_profiles (created_by);
CREATE INDEX IF NOT EXISTS voice_profiles_tags_gin   ON pmoves_core.voice_profiles USING GIN (tags);

-- Sharing grants (Q9: "who may use/clone Alice's voice"). owner_id is DENORMALIZED
-- from voice_profiles.created_by so the grants RLS policy never reads back into
-- voice_profiles (breaks the recursive policy dependency); kept authoritative by a
-- SECURITY DEFINER trigger, not the inserter.
CREATE TABLE IF NOT EXISTS pmoves_core.voice_profile_grants (
    voice_profile_id UUID NOT NULL REFERENCES pmoves_core.voice_profiles(id) ON DELETE CASCADE,
    grantee          UUID NOT NULL,                          -- auth.uid()
    owner_id         UUID,                                   -- = voice_profiles.created_by (trigger-maintained)
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

-- created_by is IMMUTABLE (CodeRabbit): the denormalized voice_profile_grants.owner_id
-- is set from created_by at grant time, so silently changing created_by would desync
-- grant RLS. Ownership transfer is out of scope for S1 (would be a deliberate,
-- service-role re-grant flow). Reject any attempt to change it on UPDATE.
CREATE OR REPLACE FUNCTION pmoves_core.voice_profiles_created_by_immutable()
RETURNS trigger AS $$
BEGIN
    IF NEW.created_by IS DISTINCT FROM OLD.created_by THEN
        RAISE EXCEPTION 'voice_profiles.created_by is immutable (was %, got %)', OLD.created_by, NEW.created_by;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_voice_profiles_created_by_immutable ON pmoves_core.voice_profiles;
CREATE TRIGGER trg_voice_profiles_created_by_immutable
    BEFORE UPDATE OF created_by ON pmoves_core.voice_profiles
    FOR EACH ROW EXECUTE FUNCTION pmoves_core.voice_profiles_created_by_immutable();

-- Denormalize owner onto grants (SECURITY DEFINER → bypasses RLS, no recursion).
CREATE OR REPLACE FUNCTION pmoves_core.set_voice_grant_owner()
RETURNS trigger AS $$
BEGIN
    SELECT created_by INTO NEW.owner_id
        FROM pmoves_core.voice_profiles
        WHERE id = NEW.voice_profile_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = pmoves_core, pg_temp;

DROP TRIGGER IF EXISTS trg_voice_grant_owner ON pmoves_core.voice_profile_grants;
CREATE TRIGGER trg_voice_grant_owner
    BEFORE INSERT OR UPDATE OF voice_profile_id ON pmoves_core.voice_profile_grants
    FOR EACH ROW EXECUTE FUNCTION pmoves_core.set_voice_grant_owner();

-- Row Level Security (Q9) -----------------------------------------------------
-- jwt sub (user id) helper: NULLIF guards an empty/absent claim from a uuid cast error.
ALTER TABLE pmoves_core.voice_profiles       ENABLE ROW LEVEL SECURITY;
ALTER TABLE pmoves_core.voice_profile_grants ENABLE ROW LEVEL SECURITY;

-- Services (flute-gateway, creator-operator) use the service key → full bypass.
DROP POLICY IF EXISTS voice_profiles_service_bypass ON pmoves_core.voice_profiles;
CREATE POLICY voice_profiles_service_bypass ON pmoves_core.voice_profiles
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Read: active+undeleted AND (public OR owner OR explicitly granted).
DROP POLICY IF EXISTS voice_profiles_read ON pmoves_core.voice_profiles;
CREATE POLICY voice_profiles_read ON pmoves_core.voice_profiles
    FOR SELECT
    USING (
        is_active AND deleted_at IS NULL AND (
            is_public
            OR created_by = auth.uid()
            OR EXISTS (
                SELECT 1 FROM pmoves_core.voice_profile_grants g
                WHERE g.voice_profile_id = pmoves_core.voice_profiles.id
                  AND g.grantee = auth.uid()
            )
        )
    );

-- Owner manages their own rows — INSERT + UPDATE only (no hard DELETE; soft-delete
-- via deleted_at is the lifecycle contract — CodeRabbit). Hard DELETE is service_role
-- only (grants below), preserving retention/provenance + cascade safety.
DROP POLICY IF EXISTS voice_profiles_owner_write ON pmoves_core.voice_profiles;
DROP POLICY IF EXISTS voice_profiles_owner_insert ON pmoves_core.voice_profiles;
CREATE POLICY voice_profiles_owner_insert ON pmoves_core.voice_profiles
    FOR INSERT
    WITH CHECK (created_by = auth.uid());

DROP POLICY IF EXISTS voice_profiles_owner_update ON pmoves_core.voice_profiles;
CREATE POLICY voice_profiles_owner_update ON pmoves_core.voice_profiles
    FOR UPDATE
    USING (created_by = auth.uid())
    WITH CHECK (created_by = auth.uid());

DROP POLICY IF EXISTS voice_profile_grants_service_bypass ON pmoves_core.voice_profile_grants;
CREATE POLICY voice_profile_grants_service_bypass ON pmoves_core.voice_profile_grants
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Voice owner manages grants on their voices — checks the DENORMALIZED owner_id
-- (no subquery into voice_profiles → breaks the recursive RLS policy dependency).
DROP POLICY IF EXISTS voice_profile_grants_owner ON pmoves_core.voice_profile_grants;
CREATE POLICY voice_profile_grants_owner ON pmoves_core.voice_profile_grants
    FOR ALL
    USING (owner_id = auth.uid())
    WITH CHECK (owner_id = auth.uid());

-- Grantee may read their own grant row.
DROP POLICY IF EXISTS voice_profile_grants_grantee_read ON pmoves_core.voice_profile_grants;
CREATE POLICY voice_profile_grants_grantee_read ON pmoves_core.voice_profile_grants
    FOR SELECT
    USING (grantee = auth.uid());

-- PostgREST grants (mirror v5_13_pmoves_core_rest_grants.sql) ------------------
DO $$
BEGIN
    EXECUTE 'GRANT USAGE ON SCHEMA pmoves_core TO anon, authenticated, service_role';
    -- Read for anon/authenticated (RLS still gates rows); write for authenticated + service_role.
    EXECUTE 'GRANT SELECT ON pmoves_core.voice_profiles TO anon, authenticated, service_role';
    -- authenticated: INSERT/UPDATE only (soft-delete via deleted_at); hard DELETE is service_role.
    EXECUTE 'GRANT INSERT, UPDATE ON pmoves_core.voice_profiles TO authenticated';
    EXECUTE 'GRANT INSERT, UPDATE, DELETE ON pmoves_core.voice_profiles TO service_role';
    EXECUTE 'GRANT SELECT, INSERT, UPDATE, DELETE ON pmoves_core.voice_profile_grants TO authenticated, service_role';
END $$;

COMMENT ON TABLE pmoves_core.voice_profiles IS
    'Unified multi-engine voice registry (Voice Agents S1). Source of truth + routing for flute-gateway voice selection. See docs/superpowers/specs/2026-06-26-voice-agents-design.md.';
