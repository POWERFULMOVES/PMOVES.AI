-- Health and Finance integration tables (Wger + Firefly III)
-- Date: 2025-10-18

-- HEALTH
CREATE TABLE IF NOT EXISTS public.health_workouts (
  id                       bigserial PRIMARY KEY,
  namespace                text NOT NULL DEFAULT 'pmoves',
  source                   text NOT NULL CHECK (source IN ('wger')),
  external_id              text NOT NULL,
  observed_at              timestamptz NOT NULL,
  summary                  text NULL,
  metrics                  jsonb NOT NULL DEFAULT '{}'::jsonb,
  raw                      jsonb NOT NULL DEFAULT '{}'::jsonb,
  geometry_anchor_id       uuid NULL REFERENCES public.anchors(id) ON DELETE SET NULL,
  geometry_constellation_id uuid NULL REFERENCES public.constellations(id) ON DELETE SET NULL,
  created_at               timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_health_workouts_source_external
  ON public.health_workouts (source, external_id);
CREATE INDEX IF NOT EXISTS idx_health_workouts_ns_observed
  ON public.health_workouts (namespace, observed_at DESC);

CREATE TABLE IF NOT EXISTS public.health_nutrition (
  id                       bigserial PRIMARY KEY,
  namespace                text NOT NULL DEFAULT 'pmoves',
  source                   text NOT NULL CHECK (source IN ('wger')),
  external_id              text NOT NULL,
  observed_at              timestamptz NOT NULL,
  summary                  text NULL,
  metrics                  jsonb NOT NULL DEFAULT '{}'::jsonb,
  raw                      jsonb NOT NULL DEFAULT '{}'::jsonb,
  geometry_anchor_id       uuid NULL REFERENCES public.anchors(id) ON DELETE SET NULL,
  geometry_constellation_id uuid NULL REFERENCES public.constellations(id) ON DELETE SET NULL,
  created_at               timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_health_nutrition_source_external
  ON public.health_nutrition (source, external_id);
CREATE INDEX IF NOT EXISTS idx_health_nutrition_ns_observed
  ON public.health_nutrition (namespace, observed_at DESC);

CREATE TABLE IF NOT EXISTS public.health_weight (
  id                       bigserial PRIMARY KEY,
  namespace                text NOT NULL DEFAULT 'pmoves',
  source                   text NOT NULL CHECK (source IN ('wger')),
  external_id              text NOT NULL,
  observed_at              timestamptz NOT NULL,
  weight_kg                double precision NULL,
  metrics                  jsonb NOT NULL DEFAULT '{}'::jsonb,
  raw                      jsonb NOT NULL DEFAULT '{}'::jsonb,
  geometry_anchor_id       uuid NULL REFERENCES public.anchors(id) ON DELETE SET NULL,
  geometry_constellation_id uuid NULL REFERENCES public.constellations(id) ON DELETE SET NULL,
  created_at               timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_health_weight_source_external
  ON public.health_weight (source, external_id);
CREATE INDEX IF NOT EXISTS idx_health_weight_ns_observed
  ON public.health_weight (namespace, observed_at DESC);

-- FINANCE
CREATE TABLE IF NOT EXISTS public.finance_accounts (
  id            bigserial PRIMARY KEY,
  namespace     text NOT NULL DEFAULT 'pmoves',
  source        text NOT NULL CHECK (source IN ('firefly')),
  external_id   text NOT NULL,
  name          text NULL,
  kind          text NULL,
  currency      text NULL,
  raw           jsonb NOT NULL DEFAULT '{}'::jsonb,
  geometry_anchor_id uuid NULL REFERENCES public.anchors(id) ON DELETE SET NULL,
  geometry_constellation_id uuid NULL REFERENCES public.constellations(id) ON DELETE SET NULL,
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_finance_accounts_source_external
  ON public.finance_accounts (source, external_id);

CREATE TABLE IF NOT EXISTS public.finance_budgets (
  id            bigserial PRIMARY KEY,
  namespace     text NOT NULL DEFAULT 'pmoves',
  source        text NOT NULL CHECK (source IN ('firefly')),
  external_id   text NOT NULL,
  name          text NULL,
  amount        numeric NULL,
  currency      text NULL,
  period        text NULL,
  raw           jsonb NOT NULL DEFAULT '{}'::jsonb,
  geometry_anchor_id uuid NULL REFERENCES public.anchors(id) ON DELETE SET NULL,
  geometry_constellation_id uuid NULL REFERENCES public.constellations(id) ON DELETE SET NULL,
  created_at    timestamptz NOT NULL DEFAULT now()
);

-- fix typo for timestamzt if exists then alter (idempotent safety handled later)

CREATE UNIQUE INDEX IF NOT EXISTS uq_finance_budgets_source_external
  ON public.finance_budgets (source, external_id);

CREATE TABLE IF NOT EXISTS public.finance_transactions (
  id            bigserial PRIMARY KEY,
  namespace     text NOT NULL DEFAULT 'pmoves',
  source        text NOT NULL CHECK (source IN ('firefly')),
  external_id   text NOT NULL,
  occurred_at   timestamptz NOT NULL,
  amount        numeric NOT NULL,
  currency      text NOT NULL,
  description   text NULL,
  category      text NULL,
  counterparty  text NULL,
  raw           jsonb NOT NULL DEFAULT '{}'::jsonb,
  geometry_anchor_id uuid NULL REFERENCES public.anchors(id) ON DELETE SET NULL,
  geometry_constellation_id uuid NULL REFERENCES public.constellations(id) ON DELETE SET NULL,
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_finance_tx_source_external
  ON public.finance_transactions (source, external_id);
CREATE INDEX IF NOT EXISTS idx_finance_tx_ns_occurred
  ON public.finance_transactions (namespace, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_finance_tx_category
  ON public.finance_transactions (category);

-- RLS (dev: read-only to anon; writes via service role)
ALTER TABLE public.health_workouts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.health_nutrition ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.health_weight ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.finance_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.finance_budgets ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.finance_transactions ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  DROP POLICY IF EXISTS read_health_workouts_all ON public.health_workouts;
  CREATE POLICY read_health_workouts_all ON public.health_workouts FOR SELECT USING (true);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  DROP POLICY IF EXISTS read_health_nutrition_all ON public.health_nutrition;
  CREATE POLICY read_health_nutrition_all ON public.health_nutrition FOR SELECT USING (true);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  DROP POLICY IF EXISTS read_health_weight_all ON public.health_weight;
  CREATE POLICY read_health_weight_all ON public.health_weight FOR SELECT USING (true);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  DROP POLICY IF EXISTS read_finance_accounts_all ON public.finance_accounts;
  CREATE POLICY read_finance_accounts_all ON public.finance_accounts FOR SELECT USING (true);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  DROP POLICY IF EXISTS read_finance_budgets_all ON public.finance_budgets;
  CREATE POLICY read_finance_budgets_all ON public.finance_budgets FOR SELECT USING (true);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  DROP POLICY IF EXISTS read_finance_tx_all ON public.finance_transactions;
  CREATE POLICY read_finance_tx_all ON public.finance_transactions FOR SELECT USING (true);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- Correct accidental timestamzt typo if created
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='finance_budgets' AND column_name='created_at' AND data_type <> 'timestamp with time zone'
  ) THEN
    ALTER TABLE public.finance_budgets ALTER COLUMN created_at TYPE timestamptz USING created_at::timestamptz;
  END IF;
END $$;
