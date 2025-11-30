-- PMOVES v5.12 schema upgrade: assets, KB, packs, personas, evaluation gates
-- Idempotent: each CREATE uses IF NOT EXISTS or guards existing columns/indexes.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE SCHEMA IF NOT EXISTS pmoves_core;
CREATE SCHEMA IF NOT EXISTS pmoves_kb;

-- Core assets table
CREATE TABLE IF NOT EXISTS pmoves_core.assets (
  asset_id       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  uri            text NOT NULL UNIQUE,
  type           text NOT NULL,
  mime           text,
  title          text,
  source         text,
  license        text,
  checksum       text,
  size_bytes     bigint,
  language       text,
  transcript_uri text,
  thumbnail_uri  text,
  created_at     timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_assets_type ON pmoves_core.assets(type);
CREATE INDEX IF NOT EXISTS idx_assets_created ON pmoves_core.assets(created_at DESC);

-- Documents + sections + chunks (knowledge base)
CREATE TABLE IF NOT EXISTS pmoves_kb.documents (
  doc_id     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  asset_id   uuid REFERENCES pmoves_core.assets(asset_id) ON DELETE CASCADE,
  title      text,
  meta       jsonb DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS pmoves_kb.sections (
  section_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  doc_id     uuid REFERENCES pmoves_kb.documents(doc_id) ON DELETE CASCADE,
  idx        integer NOT NULL,
  heading    text,
  meta       jsonb DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_sections_doc_idx ON pmoves_kb.sections(doc_id, idx);

CREATE TABLE IF NOT EXISTS pmoves_kb.chunks (
  chunk_id   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  doc_id     uuid REFERENCES pmoves_kb.documents(doc_id) ON DELETE CASCADE,
  section_id uuid REFERENCES pmoves_kb.sections(section_id) ON DELETE SET NULL,
  pack_id    uuid,
  text       text NOT NULL,
  tokens     integer,
  embedding  vector(1536),
  idx        integer NOT NULL,
  window_size integer,
  overlap    integer,
  md         jsonb DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_chunks_doc_idx ON pmoves_kb.chunks(doc_id, idx);
CREATE INDEX IF NOT EXISTS idx_chunks_pack ON pmoves_kb.chunks(pack_id);
DO $$
BEGIN
  EXECUTE 'CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON pmoves_kb.chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)';
EXCEPTION
  WHEN OTHERS THEN
    RAISE NOTICE 'Skipping idx_chunks_embedding creation: %', SQLERRM;
END$$;

-- Grounding packs + membership
CREATE TABLE IF NOT EXISTS pmoves_core.grounding_packs (
  pack_id     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name        text NOT NULL,
  version     text NOT NULL DEFAULT '1.0',
  owner       text NOT NULL,
  description text,
  policy      jsonb DEFAULT '{}'::jsonb,
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_pack_name_version ON pmoves_core.grounding_packs(name, version);

CREATE TABLE IF NOT EXISTS pmoves_core.pack_members (
  pack_id    uuid REFERENCES pmoves_core.grounding_packs(pack_id) ON DELETE CASCADE,
  asset_id   uuid REFERENCES pmoves_core.assets(asset_id) ON DELETE CASCADE,
  selectors  jsonb DEFAULT '{}'::jsonb,
  weight     real DEFAULT 1.0,
  notes      text,
  PRIMARY KEY (pack_id, asset_id)
);

-- Personas + evaluation gates
CREATE TABLE IF NOT EXISTS pmoves_core.personas (
  persona_id    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name          text NOT NULL,
  version       text NOT NULL DEFAULT '1.0',
  description   text,
  runtime       jsonb NOT NULL DEFAULT '{}'::jsonb,
  default_packs text[] NOT NULL DEFAULT '{}',
  boosts        jsonb NOT NULL DEFAULT '{}'::jsonb,
  filters       jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_persona_name_version ON pmoves_core.personas(name, version);

CREATE TABLE IF NOT EXISTS pmoves_core.persona_eval_gates (
  persona_id uuid REFERENCES pmoves_core.personas(persona_id) ON DELETE CASCADE,
  dataset_id text NOT NULL,
  metric     text NOT NULL,
  threshold  real NOT NULL,
  last_run   timestamptz,
  pass       boolean,
  PRIMARY KEY (persona_id, dataset_id, metric)
);

-- Helpful trigram index for chunk text (optional but cheap)
CREATE INDEX IF NOT EXISTS idx_chunks_text_trgm ON pmoves_kb.chunks USING gin (text gin_trgm_ops);
