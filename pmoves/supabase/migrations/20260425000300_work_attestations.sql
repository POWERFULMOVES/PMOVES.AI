-- =============================================================================
-- Migration: work_attestations — signed contribution attestation records
-- Stage 8: Merkle-rooted work provenance with on-chain status tracking
-- Tracks: attestation_sig, merkle_root, chain_status lifecycle
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS pmoves_core;

CREATE TABLE IF NOT EXISTS pmoves_core.work_attestations (
    attestation_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    work_id          UUID NOT NULL,
    contributor_id   UUID NOT NULL,
    attestation_sig  TEXT NOT NULL,
    merkle_root      TEXT,
    chain_status     TEXT NOT NULL DEFAULT 'pending',
    attested_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT work_attestations_chain_status_chk
        CHECK (chain_status IN ('pending', 'confirmed', 'failed'))
);

-- Indexes for lookup patterns
CREATE INDEX IF NOT EXISTS idx_work_attestations_work_id
    ON pmoves_core.work_attestations (work_id);

CREATE INDEX IF NOT EXISTS idx_work_attestations_contributor_id
    ON pmoves_core.work_attestations (contributor_id);

-- Enable RLS
ALTER TABLE IF EXISTS pmoves_core.work_attestations ENABLE ROW LEVEL SECURITY;

-- Revoke anon; grant service_role full, authenticated read
DO $$ BEGIN
  EXECUTE 'REVOKE ALL ON pmoves_core.work_attestations FROM anon';
EXCEPTION WHEN OTHERS THEN
  RAISE NOTICE 'REVOKE from anon on work_attestations: %', SQLERRM;
END $$;

DO $$ BEGIN
  EXECUTE 'GRANT ALL ON pmoves_core.work_attestations TO service_role';
EXCEPTION WHEN OTHERS THEN
  RAISE NOTICE 'GRANT to service_role on work_attestations: %', SQLERRM;
END $$;

DO $$ BEGIN
  EXECUTE 'GRANT SELECT ON pmoves_core.work_attestations TO authenticated';
EXCEPTION WHEN OTHERS THEN
  RAISE NOTICE 'GRANT SELECT to authenticated on work_attestations: %', SQLERRM;
END $$;

-- Drop existing policies if re-running
DROP POLICY IF EXISTS "work_attestations_svc_all" ON pmoves_core.work_attestations;
DROP POLICY IF EXISTS "work_attestations_auth_read" ON pmoves_core.work_attestations;

CREATE POLICY "work_attestations_svc_all" ON pmoves_core.work_attestations
  FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "work_attestations_auth_read" ON pmoves_core.work_attestations
  FOR SELECT TO authenticated USING (true);
