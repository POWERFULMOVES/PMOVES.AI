-- Tighten model candidate and fitness RLS for environments that already ran
-- the initial model-fitness migration before the policy hardening landed.

ALTER TABLE pmoves_core.model_candidates ENABLE ROW LEVEL SECURITY;
ALTER TABLE pmoves_core.model_fitness_records ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON pmoves_core.model_candidates FROM anon;
REVOKE ALL ON pmoves_core.model_fitness_records FROM anon;
REVOKE ALL ON pmoves_core.model_candidates FROM authenticated;
REVOKE ALL ON pmoves_core.model_fitness_records FROM authenticated;
REVOKE ALL ON pmoves_core.model_candidates FROM service_role;
REVOKE ALL ON pmoves_core.model_fitness_records FROM service_role;

DROP POLICY IF EXISTS "Read model candidates" ON pmoves_core.model_candidates;
DROP POLICY IF EXISTS "Read model fitness" ON pmoves_core.model_fitness_records;
DROP POLICY IF EXISTS "Service write model candidates" ON pmoves_core.model_candidates;
DROP POLICY IF EXISTS "Service write model fitness" ON pmoves_core.model_fitness_records;
DROP POLICY IF EXISTS "Public read model candidates" ON pmoves_core.model_candidates;
DROP POLICY IF EXISTS "Public read model fitness" ON pmoves_core.model_fitness_records;

GRANT SELECT ON pmoves_core.model_candidates TO authenticated;
GRANT SELECT ON pmoves_core.model_fitness_records TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON pmoves_core.model_candidates TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON pmoves_core.model_fitness_records TO service_role;

CREATE POLICY "Read model candidates" ON pmoves_core.model_candidates
  FOR SELECT TO authenticated
  USING (auth.role() = 'authenticated');

CREATE POLICY "Read model fitness" ON pmoves_core.model_fitness_records
  FOR SELECT TO authenticated
  USING (auth.role() = 'authenticated');

CREATE POLICY "Service write model candidates" ON pmoves_core.model_candidates
  FOR ALL TO service_role
  USING (auth.role() = 'service_role')
  WITH CHECK (auth.role() = 'service_role');

CREATE POLICY "Service write model fitness" ON pmoves_core.model_fitness_records
  FOR ALL TO service_role
  USING (auth.role() = 'service_role')
  WITH CHECK (auth.role() = 'service_role');
