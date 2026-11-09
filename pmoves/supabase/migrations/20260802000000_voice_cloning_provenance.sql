-- v5_18 Voice Cloning Provenance Gate (Voice Agents S5).
-- Spec: docs/superpowers/specs/2026-06-26-voice-agents-design.md §8 (provenance model),
--       §9 S5 (provenance gate), §10 Q8 (CHIT provenance rides CGP meta).
--
-- The voice_profiles table has inline provenance mirror columns (provenance,
-- rights_basis, cloned_from, clone_method). This table is the FULL provenance
-- record — one voice can have multiple provenance sources (e.g., blended from
-- two speakers). The synthesis-time gate (flute-gateway) checks this table
-- before any cloned-voice synthesis is permitted.
--
-- Gate logic (enforced in Python by flute-gateway provenance_gate.py):
--   1. Missing provenance record → reject synthesis
--   2. is_active=false (revoked) → reject synthesis
--   3. CONSENTED requires consent_artifact_uri NOT NULL
--   4. LICENSED requires consent_artifact_uri NOT NULL (the license agreement)
--   5. CHARACTER_OWNED gated to active character context (NATS-authorized)
--   6. VOICE_CLONING_ENABLED env must be true (default false)

CREATE TABLE IF NOT EXISTS pmoves_core.voice_cloning_provenance (
    id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    voice_profile_id       UUID NOT NULL REFERENCES pmoves_core.voice_profiles(id) ON DELETE CASCADE,
    -- Source identification
    source_type            TEXT NOT NULL,
    source_url             TEXT,
    source_timestamp_start REAL,                                -- seconds offset in source media
    source_timestamp_end   REAL,
    source_title           TEXT,
    -- Rights model (§8)
    rights_basis           TEXT NOT NULL,
    consent_method         TEXT,                                -- recorded|verbal|written|platform_tos
    consent_date           DATE,
    consent_artifact_uri   TEXT,                                -- signed consent / license doc
    -- Attribution
    capturer_identity      TEXT,                                -- who captured/created the voice sample
    attribution_required   BOOLEAN NOT NULL DEFAULT true,
    attribution_url        TEXT,
    -- Lifecycle
    is_active              BOOLEAN NOT NULL DEFAULT true,       -- false = revoked/withdrawn
    revoked_at             TIMESTAMPTZ,
    revoked_reason         TEXT,
    notes                  TEXT,
    -- Audit
    created_by             UUID,                                -- auth.uid() owner
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Constraints
    CONSTRAINT vcprov_source_type_chk CHECK (source_type IN (
        'YOUTUBE', 'MOVIE', 'OWNED_RECORDING', 'SYNTHETIC', 'CHARACTER_OWNED')),
    CONSTRAINT vcprov_rights_chk CHECK (rights_basis IN (
        'OWNED', 'LICENSED', 'CONSENTED', 'PUBLIC_DOMAIN', 'CHARACTER_OWNED')),
    CONSTRAINT vcprov_consent_required_chk CHECK (
        (rights_basis NOT IN ('CONSENTED', 'LICENSED'))
        OR NULLIF(btrim(consent_artifact_uri), '') IS NOT NULL
    ),
    CONSTRAINT vcprov_ts_chk CHECK (
        source_timestamp_start IS NULL
        OR source_timestamp_end IS NULL
        OR source_timestamp_end >= source_timestamp_start
    ),
    CONSTRAINT vcprov_unique UNIQUE NULLS NOT DISTINCT (
        voice_profile_id, source_url, source_timestamp_start
    )
);

CREATE INDEX IF NOT EXISTS vcprov_profile_idx  ON pmoves_core.voice_cloning_provenance (voice_profile_id);
CREATE INDEX IF NOT EXISTS vcprov_active_idx   ON pmoves_core.voice_cloning_provenance (voice_profile_id) WHERE is_active;
CREATE INDEX IF NOT EXISTS vcprov_rights_idx   ON pmoves_core.voice_cloning_provenance (rights_basis);

-- Row Level Security (mirrors voice_profiles Q9 RBAC model)
ALTER TABLE pmoves_core.voice_cloning_provenance ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS vcprov_service_bypass ON pmoves_core.voice_cloning_provenance;
CREATE POLICY vcprov_service_bypass ON pmoves_core.voice_cloning_provenance
    FOR ALL TO service_role USING (true) WITH CHECK (true);

-- Read: consent/provenance is ALWAYS private — owner or explicit grantee only.
-- Public voices are still selectable in voice_profiles, but their provenance
-- records (consent_artifact_uri, capturer_identity, notes) are never exposed
-- to anon or other users. This prevents leaking signed consent documents.
DROP POLICY IF EXISTS vcprov_read ON pmoves_core.voice_cloning_provenance;
CREATE POLICY vcprov_read ON pmoves_core.voice_cloning_provenance
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM pmoves_core.voice_profiles vp
            WHERE vp.id = voice_cloning_provenance.voice_profile_id
              AND vp.is_active AND vp.deleted_at IS NULL AND (
                vp.created_by = auth.uid()
                OR EXISTS (
                    SELECT 1 FROM pmoves_core.voice_profile_grants g
                    WHERE g.voice_profile_id = vp.id AND g.grantee = auth.uid()
                )
            )
        )
    );

-- Write: only the voice_profiles owner
DROP POLICY IF EXISTS vcprov_owner_insert ON pmoves_core.voice_cloning_provenance;
CREATE POLICY vcprov_owner_insert ON pmoves_core.voice_cloning_provenance
    FOR INSERT WITH CHECK (
        EXISTS (
            SELECT 1 FROM pmoves_core.voice_profiles vp
            WHERE vp.id = voice_profile_id AND vp.created_by = auth.uid()
        )
    );

DROP POLICY IF EXISTS vcprov_owner_update ON pmoves_core.voice_cloning_provenance;
CREATE POLICY vcprov_owner_update ON pmoves_core.voice_cloning_provenance
    FOR UPDATE USING (
        EXISTS (
            SELECT 1 FROM pmoves_core.voice_profiles vp
            WHERE vp.id = voice_profile_id AND vp.created_by = auth.uid()
        )
    );

-- PostgREST grants
DO $$
BEGIN
    EXECUTE 'GRANT SELECT ON pmoves_core.voice_cloning_provenance TO authenticated, service_role';
    EXECUTE 'GRANT INSERT, UPDATE ON pmoves_core.voice_cloning_provenance TO authenticated';
    EXECUTE 'GRANT INSERT, UPDATE, DELETE ON pmoves_core.voice_cloning_provenance TO service_role';
END $$;

COMMENT ON TABLE pmoves_core.voice_cloning_provenance IS
    'Voice cloning provenance gate (Voice Agents S5). Full rights/consent/provenance record for voice cloning. The synthesis-time gate checks this table before any cloned-voice synthesis. See docs/superpowers/specs/2026-06-26-voice-agents-design.md §8.';
