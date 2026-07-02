-- PMOVES Wealth CGP export table
-- Stores signed Computational Geometry Packet (CGP) exports from tokenism simulations.

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE SCHEMA IF NOT EXISTS pmoves_core;

CREATE TABLE IF NOT EXISTS pmoves_core.wealth_cgp_exports (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id TEXT NOT NULL,
  label TEXT NOT NULL,

  -- Geometry / CHIT envelope metadata
  schema_version TEXT NOT NULL DEFAULT 'chit.cgp.v0.2',
  envelope_type TEXT NOT NULL DEFAULT 'geometry.wealth.v1',

  -- Core CGP state vector (delta, kappa, Hz, A, F)
  state_vector JSONB NOT NULL,

  -- Anchor coordinates
  anchor JSONB NOT NULL,

  -- Optional raw export payload for replay/audit
  payload JSONB,

  -- CHIT signature (base64) when signed mode is enabled
  signature TEXT,
  signed_at TIMESTAMPTZ,

  -- Provenance
  source_simulation_id TEXT,
  source_url TEXT,

  -- Timestamps
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_wealth_cgp_exports_run_id ON pmoves_core.wealth_cgp_exports(run_id);
CREATE INDEX IF NOT EXISTS idx_wealth_cgp_exports_label ON pmoves_core.wealth_cgp_exports(label);
CREATE INDEX IF NOT EXISTS idx_wealth_cgp_exports_created_at ON pmoves_core.wealth_cgp_exports(created_at DESC);

-- Trigger to keep updated_at current
CREATE OR REPLACE FUNCTION pmoves_core.touch_wealth_cgp_exports_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_wealth_cgp_exports_updated_at ON pmoves_core.wealth_cgp_exports;
CREATE TRIGGER trg_wealth_cgp_exports_updated_at
  BEFORE UPDATE ON pmoves_core.wealth_cgp_exports
  FOR EACH ROW
  EXECUTE FUNCTION pmoves_core.touch_wealth_cgp_exports_updated_at();

-- Row-level security
ALTER TABLE pmoves_core.wealth_cgp_exports ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Public read wealth cgp exports"
  ON pmoves_core.wealth_cgp_exports FOR SELECT
  TO public, anon
  USING (true);

-- Service role / authenticated can insert/update their own exports
CREATE POLICY "Service role insert wealth cgp exports"
  ON pmoves_core.wealth_cgp_exports FOR INSERT
  TO service_role
  WITH CHECK (true);

CREATE POLICY "Service role update wealth cgp exports"
  ON pmoves_core.wealth_cgp_exports FOR UPDATE
  TO service_role
  USING (true)
  WITH CHECK (true);

-- Helpful comments
COMMENT ON TABLE pmoves_core.wealth_cgp_exports IS 'Signed CGP wealth exports generated from tokenism simulator runs';
COMMENT ON COLUMN pmoves_core.wealth_cgp_exports.state_vector IS 'CGP state vector: delta, kappa, Hz, A, F';
COMMENT ON COLUMN pmoves_core.wealth_cgp_exports.anchor IS 'CGP anchor coordinates [x, y, z]';
