-- PMOVES v5.12 seed data for packs, personas, and geometry defaults
-- Safe to re-run; all inserts use ON CONFLICT safeguards.

-- Upsert representative architecture docs (adjust URIs for real assets)
INSERT INTO pmoves_core.assets (asset_id, uri, type, mime, title, source)
VALUES
  (gen_random_uuid(), 's3://assets/docs/PMOVES_ARC.md', 'pdf', 'text/markdown', 'PMOVES Architecture', 'upload'),
  (gen_random_uuid(), 's3://assets/docs/HI_RAG_RERANKER.md', 'pdf', 'text/markdown', 'Hi-RAG Reranker', 'upload'),
  (gen_random_uuid(), 's3://assets/docs/RETRIEVAL_EVAL_GUIDE.md', 'pdf', 'text/markdown', 'Retrieval Eval Guide', 'upload')
ON CONFLICT (uri) DO UPDATE
SET title = EXCLUDED.title,
    source = EXCLUDED.source;

-- Upsert the pmoves-architecture grounding pack
INSERT INTO pmoves_core.grounding_packs (pack_id, name, version, owner, description, policy)
VALUES (
  gen_random_uuid(), 'pmoves-architecture', '1.0', '@cataclysmstudios',
  'Core docs for PMOVES architecture, contracts, and services.',
  '{"allow_external_links": true}'::jsonb
)
ON CONFLICT (name, version) DO UPDATE
SET owner = EXCLUDED.owner,
    description = EXCLUDED.description,
    policy = EXCLUDED.policy;

-- Upsert pack members based on the assets above
WITH pack AS (
  SELECT pack_id FROM pmoves_core.grounding_packs
  WHERE name = 'pmoves-architecture' AND version = '1.0'
),
assets AS (
  SELECT asset_id, uri FROM pmoves_core.assets
  WHERE uri IN (
    's3://assets/docs/PMOVES_ARC.md',
    's3://assets/docs/HI_RAG_RERANKER.md',
    's3://assets/docs/RETRIEVAL_EVAL_GUIDE.md'
  )
)
INSERT INTO pmoves_core.pack_members (pack_id, asset_id, selectors, weight, notes)
SELECT
  pack.pack_id,
  assets.asset_id,
  CASE assets.uri
    WHEN 's3://assets/docs/PMOVES_ARC.md' THEN '{"pages":[1,2,3]}'::jsonb
    WHEN 's3://assets/docs/HI_RAG_RERANKER.md' THEN '{"sections":["Overview","API"]}'::jsonb
    WHEN 's3://assets/docs/RETRIEVAL_EVAL_GUIDE.md' THEN '{"sections":["Datasets","Metrics"]}'::jsonb
    ELSE '{}'::jsonb
  END AS selectors,
  CASE assets.uri
    WHEN 's3://assets/docs/HI_RAG_RERANKER.md' THEN 1.2
    ELSE 1.0
  END AS weight,
  NULL::text AS notes
FROM pack, assets
ON CONFLICT (pack_id, asset_id) DO UPDATE
SET selectors = EXCLUDED.selectors,
    weight    = EXCLUDED.weight;

-- Upsert Archon persona definition
INSERT INTO pmoves_core.personas (persona_id, name, version, description, runtime, default_packs, boosts, filters)
VALUES (
  gen_random_uuid(), 'Archon', '1.0', 'Controller/retriever for PMOVES',
  '{"model":"gpt-4o","tools":["hirag.query","kb.viewer","geometry.jump","geometry.decode_text"],"policies":{"freshness_months":18,"must_cite":true}}'::jsonb,
  ARRAY['pmoves-architecture@1.0','recent-delta@rolling'],
  '{"entities":["Hi-RAG","LangExtract","Neo4j","Qdrant"]}'::jsonb,
  '{"exclude_types":["raw-audio"]}'::jsonb
)
ON CONFLICT (name, version) DO UPDATE
SET description   = EXCLUDED.description,
    runtime       = EXCLUDED.runtime,
    default_packs = EXCLUDED.default_packs,
    boosts        = EXCLUDED.boosts,
    filters       = EXCLUDED.filters;

-- Gate Archon persona publish on retrieval quality
INSERT INTO pmoves_core.persona_eval_gates (persona_id, dataset_id, metric, threshold, pass)
SELECT p.persona_id, 'archon-smoke-10', 'top3_hit@k', 0.80, NULL
FROM pmoves_core.personas p
WHERE p.name = 'Archon' AND p.version = '1.0'
ON CONFLICT (persona_id, dataset_id, metric) DO UPDATE
SET threshold = EXCLUDED.threshold;

-- Optional sample render asset for publisher smoke checks
INSERT INTO pmoves_core.assets (uri, type, mime, title, source, thumbnail_uri)
VALUES (
  's3://outputs/2025/pmoves-sample.png',
  'image','image/png','PMOVES Sample Render','comfyui',
  's3://outputs/2025/pmoves-sample-thumb.jpg'
)
ON CONFLICT (uri) DO NOTHING;
