-- =============================================================================
-- Migration: RLS for adult_swim_records (sealed records schema)
-- Stage 3: Sealed record lifecycle with age-gated access control
-- Policies: owner-only read, age-verified write via JWT claim
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS pmoves_core;

CREATE TABLE IF NOT EXISTS pmoves_core.adult_swim_records (
    sealed_record_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id           UUID NOT NULL,
    payload_ref        TEXT,
    sealed_at          TIMESTAMPTZ,
    unsealed_at        TIMESTAMPTZ,
    age_required       INTEGER NOT NULL DEFAULT 18,
    CONSTRAINT adult_swim_records_age_chk CHECK (age_required >= 18)
);

-- Enable RLS
ALTER TABLE IF EXISTS pmoves_core.adult_swim_records ENABLE ROW LEVEL SECURITY;

-- Revoke anon access
DO $$ BEGIN
  EXECUTE 'REVOKE ALL ON pmoves_core.adult_swim_records FROM anon';
EXCEPTION WHEN OTHERS THEN
  RAISE NOTICE 'REVOKE from anon on adult_swim_records: %', SQLERRM;
END $$;

-- Grant service_role full access (bypasses RLS)
DO $$ BEGIN
  EXECUTE 'GRANT ALL ON pmoves_core.adult_swim_records TO service_role';
EXCEPTION WHEN OTHERS THEN
  RAISE NOTICE 'GRANT to service_role on adult_swim_records: %', SQLERRM;
END $$;

-- Drop existing policies if re-running
DROP POLICY IF EXISTS "adult_swim_anon_deny" ON pmoves_core.adult_swim_records;
DROP POLICY IF EXISTS "adult_swim_svc_all" ON pmoves_core.adult_swim_records;
DROP POLICY IF EXISTS "adult_swim_owner_read" ON pmoves_core.adult_swim_records;
DROP POLICY IF EXISTS "adult_swim_age_verified_write" ON pmoves_core.adult_swim_records;

-- Anon deny-all
CREATE POLICY "adult_swim_anon_deny" ON pmoves_core.adult_swim_records
  FOR ALL TO anon USING (false) WITH CHECK (false);

-- Service role full access
CREATE POLICY "adult_swim_svc_all" ON pmoves_core.adult_swim_records
  FOR ALL TO service_role USING (true) WITH CHECK (true);

-- Owner-only read
CREATE POLICY "adult_swim_owner_read" ON pmoves_core.adult_swim_records
  FOR SELECT TO authenticated
  USING (auth.uid() = owner_id);

-- Age-verified write (JWT claim user_age_verified = true)
CREATE POLICY "adult_swim_age_verified_write" ON pmoves_core.adult_swim_records
  FOR ALL TO authenticated
  USING (auth.uid() = owner_id AND auth.jwt() ->> 'user_age_verified' = 'true')
  WITH CHECK (auth.uid() = owner_id AND auth.jwt() ->> 'user_age_verified' = 'true');
