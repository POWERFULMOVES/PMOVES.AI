-- sqlfluff: disable=all

-- Enable required extensions if not already present.
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Stores active/inactive parameter packs produced by the EvoSwarm controller.
CREATE TABLE IF NOT EXISTS geometry_parameter_packs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    namespace text NOT NULL,
    modality text NOT NULL,
    pack_type text NOT NULL DEFAULT 'cg_builder',
    status text NOT NULL DEFAULT 'draft',
    population_id text,
    generation integer,
    fitness numeric,
    energy numeric,
    params jsonb NOT NULL,
    notes text,
    created_at timestamptz NOT NULL DEFAULT timezone('UTC', now()),
    updated_at timestamptz NOT NULL DEFAULT timezone('UTC', now())
);

CREATE INDEX IF NOT EXISTS geometry_parameter_packs_namespace_idx
    ON geometry_parameter_packs (namespace, modality, pack_type, status);

CREATE INDEX IF NOT EXISTS geometry_parameter_packs_created_at_idx
    ON geometry_parameter_packs (created_at DESC);

GRANT SELECT ON geometry_parameter_packs TO anon;
GRANT SELECT, INSERT, UPDATE, DELETE ON geometry_parameter_packs TO authenticated;
GRANT ALL ON geometry_parameter_packs TO service_role;

-- Stores metadata for each evolutionary run / population.
CREATE TABLE IF NOT EXISTS geometry_swarm_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    population_id text NOT NULL,
    generation integer NOT NULL DEFAULT 0,
    controller_version text,
    config jsonb,
    best_pack_id uuid REFERENCES geometry_parameter_packs(id),
    metrics jsonb,
    created_at timestamptz NOT NULL DEFAULT timezone('UTC', now())
);

CREATE INDEX IF NOT EXISTS geometry_swarm_runs_population_idx
    ON geometry_swarm_runs (population_id, generation DESC);

GRANT SELECT ON geometry_swarm_runs TO anon;
GRANT SELECT, INSERT, UPDATE, DELETE ON geometry_swarm_runs TO authenticated;
GRANT ALL ON geometry_swarm_runs TO service_role;

-- Optional table for detailed evaluation metrics per genome.
CREATE TABLE IF NOT EXISTS geometry_swarm_evaluations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    pack_id uuid REFERENCES geometry_parameter_packs(id) ON DELETE CASCADE,
    evaluation_ts timestamptz NOT NULL DEFAULT timezone('UTC', now()),
    metrics jsonb NOT NULL,
    calibration jsonb,
    energy jsonb,
    notes text
);

CREATE INDEX IF NOT EXISTS geometry_swarm_evaluations_pack_idx
    ON geometry_swarm_evaluations (pack_id, evaluation_ts DESC);

GRANT SELECT ON geometry_swarm_evaluations TO anon;
GRANT SELECT, INSERT, UPDATE, DELETE ON geometry_swarm_evaluations TO authenticated;
GRANT ALL ON geometry_swarm_evaluations TO service_role;

-- Trigger to keep updated_at fresh on geometry_parameter_packs.
CREATE OR REPLACE FUNCTION geometry_parameter_packs_touch()
RETURNS trigger AS $$
BEGIN
    NEW.updated_at := timezone('UTC', now());
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_geometry_parameter_packs_touch ON geometry_parameter_packs;
CREATE TRIGGER trg_geometry_parameter_packs_touch
    BEFORE UPDATE ON geometry_parameter_packs
    FOR EACH ROW EXECUTE FUNCTION geometry_parameter_packs_touch();
