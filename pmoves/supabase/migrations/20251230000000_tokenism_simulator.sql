-- PMOVES Tokenism Simulator Tables
-- Stores token economy simulation data for PMOVES.AI integration

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Main simulations table
CREATE TABLE IF NOT EXISTS pmoves_core.simulations (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  simulation_id TEXT NOT NULL UNIQUE,
  scenario TEXT NOT NULL CHECK (scenario IN ('optimistic', 'baseline', 'pessimistic', 'stress_test', 'custom')),

  -- Simulation parameters (JSONB for flexibility)
  parameters JSONB NOT NULL,

  -- Reference to contract type
  contract_type TEXT CHECK (contract_type IN ('gro_token', 'food_usd', 'group_purchase', 'gro_vault', 'coop_governor')),

  -- Summary statistics
  final_avg_wealth DECIMAL(18,2) NOT NULL,
  final_gini DECIMAL(10,4) NOT NULL CHECK (final_gini BETWEEN 0 AND 1),
  final_poverty_rate DECIMAL(10,4) NOT NULL CHECK (final_poverty_rate BETWEEN 0 AND 1),
  total_transactions INTEGER NOT NULL,
  total_volume DECIMAL(20,2) NOT NULL,

  -- Risk indicators
  wealth_volatility DECIMAL(18,2) DEFAULT 0,
  systemic_risk_score DECIMAL(5,4) CHECK (systemic_risk_score BETWEEN 0 AND 1),

  -- AI analysis (optional)
  analysis TEXT,
  risk_report TEXT,

  -- Timestamps
  created_at TIMESTAMPTZ DEFAULT NOW(),
  completed_at TIMESTAMPTZ,

  -- Ownership
  created_by UUID REFERENCES auth.users(id)
);

-- Weekly metrics table
CREATE TABLE IF NOT EXISTS pmoves_core.simulation_weekly_metrics (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  simulation_id UUID NOT NULL REFERENCES pmoves_core.simulations(id) ON DELETE CASCADE,

  week_number INTEGER NOT NULL CHECK (week_number >= 0),

  -- Wealth metrics
  avg_wealth DECIMAL(18,2) NOT NULL,
  median_wealth DECIMAL(18,2) NOT NULL,
  gini_coefficient DECIMAL(10,4) NOT NULL CHECK (gini_coefficient BETWEEN 0 AND 1),
  poverty_rate DECIMAL(10,4) NOT NULL CHECK (poverty_rate BETWEEN 0 AND 1),

  -- Transaction metrics
  total_transactions INTEGER NOT NULL,
  total_volume DECIMAL(20,2) NOT NULL,
  active_participants INTEGER NOT NULL,
  new_participants INTEGER DEFAULT 0,

  -- Token metrics
  staked_tokens DECIMAL(20,2) DEFAULT 0,
  circulating_supply DECIMAL(20,2) NOT NULL,

  created_at TIMESTAMPTZ DEFAULT NOW(),

  -- Ensure one metric entry per week per simulation
  UNIQUE(simulation_id, week_number)
);

-- Calibration data table
CREATE TABLE IF NOT EXISTS pmoves_core.simulation_calibration (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  calibration_id TEXT NOT NULL UNIQUE,
  simulation_id UUID NOT NULL REFERENCES pmoves_core.simulations(id) ON DELETE CASCADE,

  parameter_name TEXT NOT NULL,
  old_value DECIMAL(18,4) NOT NULL,
  new_value DECIMAL(18,4) NOT NULL,

  confidence_score DECIMAL(5,4) CHECK (confidence_score BETWEEN 0 AND 1),

  observed_value DECIMAL(18,4),
  target_error DECIMAL(10,6) DEFAULT 0,
  actual_error DECIMAL(10,6) DEFAULT 0,
  iterations INTEGER DEFAULT 1,

  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_simulations_scenario ON pmoves_core.simulations(scenario);
CREATE INDEX IF NOT EXISTS idx_simulations_contract_type ON pmoves_core.simulations(contract_type);
CREATE INDEX IF NOT EXISTS idx_simulations_created_at ON pmoves_core.simulations(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_simulations_systemic_risk ON pmoves_core.simulations(systemic_risk_score);

CREATE INDEX IF NOT EXISTS idx_weekly_metrics_simulation ON pmoves_core.simulation_weekly_metrics(simulation_id);
CREATE INDEX IF NOT EXISTS idx_weekly_metrics_week ON pmoves_core.simulation_weekly_metrics(week_number);

CREATE INDEX IF NOT EXISTS idx_calibration_simulation ON pmoves_core.simulation_calibration(simulation_id);
CREATE INDEX IF NOT EXISTS idx_calibration_parameter ON pmoves_core.simulation_calibration(parameter_name);

-- Create RLS policies
ALTER TABLE pmoves_core.simulations ENABLE ROW LEVEL SECURITY;
ALTER TABLE pmoves_core.simulation_weekly_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE pmoves_core.simulation_calibration ENABLE ROW LEVEL SECURITY;

-- Public can read simulations (for transparency)
-- Note: USING (true) is intentional for public read-only access
CREATE POLICY "Public read access to simulations"
  ON pmoves_core.simulations FOR SELECT
  TO public, anon
  USING (true);

-- Authenticated users can create their own simulations
CREATE POLICY "Authenticated insert simulations"
  ON pmoves_core.simulations FOR INSERT
  TO authenticated
  WITH CHECK (created_by = auth.uid());

-- Users can update their own simulations
CREATE POLICY "Users update own simulations"
  ON pmoves_core.simulations FOR UPDATE
  TO authenticated
  USING (created_by = auth.uid())
  WITH CHECK (created_by = auth.uid());

-- Public read access to weekly metrics (via simulation relationship)
CREATE POLICY "Public read access to weekly metrics"
  ON pmoves_core.simulation_weekly_metrics FOR SELECT
  TO public, anon
  USING (
    EXISTS (
      SELECT 1 FROM pmoves_core.simulations s
      WHERE s.id = simulation_weekly_metrics.simulation_id
    )
  );

-- Public read access to calibration data (via simulation relationship)
CREATE POLICY "Public read access to calibration"
  ON pmoves_core.simulation_calibration FOR SELECT
  TO public, anon
  USING (
    EXISTS (
      SELECT 1 FROM pmoves_core.simulations s
      WHERE s.id = simulation_calibration.simulation_id
    )
  );

-- Create view for simulation summary
CREATE OR REPLACE VIEW pmoves_core.simulation_summary AS
SELECT
  s.simulation_id,
  s.scenario,
  s.contract_type,
  s.final_avg_wealth,
  s.final_gini,
  s.final_poverty_rate,
  s.systemic_risk_score,
  s.parameters->>'duration_weeks' as duration_weeks,
  COUNT(wm.id) as metrics_count,
  s.created_at
FROM pmoves_core.simulations s
LEFT JOIN pmoves_core.simulation_weekly_metrics wm ON wm.simulation_id = s.id
GROUP BY s.id;

-- Grant access to view
GRANT SELECT ON pmoves_core.simulation_summary TO public, anon;

-- Create function to calculate simulation statistics
CREATE OR REPLACE FUNCTION pmoves_core.get_simulation_stats(simulation_uuid UUID)
RETURNS TABLE(
  week_number INTEGER,
  avg_wealth DECIMAL(18,2),
  gini_coefficient DECIMAL(10,4),
  poverty_rate DECIMAL(10,4)
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    wm.week_number,
    wm.avg_wealth,
    wm.gini_coefficient,
    wm.poverty_rate
  FROM pmoves_core.simulation_weekly_metrics wm
  WHERE wm.simulation_id = simulation_uuid
  ORDER BY wm.week_number;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Add helpful comments
COMMENT ON TABLE pmoves_core.simulations IS 'Stores token economy simulation results from PMOVES Tokenism Simulator';
COMMENT ON TABLE pmoves_core.simulation_weekly_metrics IS 'Weekly metrics for token economy simulations';
COMMENT ON TABLE pmoves_core.simulation_calibration IS 'Calibration data for aligning simulations with real-world observations';
COMMENT ON VIEW pmoves_core.simulation_summary IS 'Summary view of all simulations with key metrics';
