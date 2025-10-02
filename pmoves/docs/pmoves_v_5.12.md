# PMOVES v5.12 – Grounded Personas & Library (Gist + SQL)

A tight, copy‑pasteable upgrade plan that adds **grounding packs**, **personas**, and **publish‑gated creator pipeline** finishing touches. Includes SQL for Supabase/Postgres (pgvector), event contracts, and minimal API specs.

---
## TL;DR
- **New tables**: `assets`, `documents/sections/chunks`, `grounding_packs`, `pack_members`, `personas`, `persona_eval_gates`.
- **Retrieval**: pack‑scoped search, BM25+vector+graph blend, reranker **on by default**.
- **Creator pipeline**: presign → webhook → approval → index → publish (Discord + Jellyfin refresh).
- **Geometry bus**: keep emitting `geometry.cgp.v1`; gateway ShapeStore cache on.
- **Eval**: retrieval‑eval harness as a gate for persona publish.

---
## Make Targets (suggested)
```make
# compose profiles: data (dbs), workers (indexer,publisher), gateway, comfy, n8n
up:            ## Launch core stack
	docker compose --profile data --profile workers --profile gateway up -d
up-all:        ## Full stack incl. comfy + n8n
	docker compose --profile data --profile workers --profile gateway --profile comfy --profile n8n up -d
migrate:       ## Apply SQL below (psql or supabase/sql)
	psql $$DATABASE_URL -f db/v5_12_grounded_personas.sql
seed-packs:    ## Seed sample packs/personas
	psql $$DATABASE_URL -f db/v5_12_seed.sql
reranker-on:   ## Enable reranker in gateway
	export HIRAG_RERANK_ENABLED=true
```

---
## .env Additions (minimal)
```
# Reranker
HIRAG_RERANK_ENABLED=true

# Publisher
PUBLISHER_NOTIFY_DISCORD_WEBHOOK= https://discord.com/api/webhooks/...
PUBLISHER_REFRESH_ON_PUBLISH=true
JELLYFIN_API_URL=http://jellyfin:8096
JELLYFIN_API_KEY=...
JELLYFIN_LIBRARY_ID=...

# Geometry decode (optional)
CHIT_DECODE_TEXT=false
CHIT_DECODE_IMAGE=false
CHIT_DECODE_AUDIO=false
```

---
## SQL – Schema (Postgres + pgvector)
> Save as `db/v5_12_grounded_personas.sql`. Assumes schemas exist: `pmoves_core`, `pmoves_kb`.

```sql
-- Extensions
create extension if not exists vector;
create extension if not exists pg_trgm;

-- ===============
-- Core assets
-- ===============
create table if not exists pmoves_core.assets (
  asset_id       uuid primary key default gen_random_uuid(),
  uri            text not null,              -- s3://bucket/key or http(s)
  type           text not null,              -- video|audio|image|pdf|html|docx|code|other
  mime           text,
  title          text,
  source         text,                       -- youtube|upload|crawler|comfyui
  license        text,
  checksum       text,                       -- sha256
  size_bytes     bigint,
  language       text,
  transcript_uri text,                       -- optional external transcript
  thumbnail_uri  text,
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now()
);
create index if not exists idx_assets_type on pmoves_core.assets(type);
create index if not exists idx_assets_created on pmoves_core.assets(created_at desc);

-- ===============
-- Documents / Sections / Chunks
-- ===============
create table if not exists pmoves_kb.documents (
  doc_id     uuid primary key default gen_random_uuid(),
  asset_id   uuid references pmoves_core.assets(asset_id) on delete cascade,
  title      text,
  meta       jsonb default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists pmoves_kb.sections (
  section_id uuid primary key default gen_random_uuid(),
  doc_id     uuid references pmoves_kb.documents(doc_id) on delete cascade,
  idx        int not null,
  heading    text,
  meta       jsonb default '{}'::jsonb
);
create index if not exists idx_sections_doc_idx on pmoves_kb.sections(doc_id, idx);

-- Vector dim is example (change to your embed dim, e.g., 768/1024/1536/3584)
create table if not exists pmoves_kb.chunks (
  chunk_id   uuid primary key default gen_random_uuid(),
  doc_id     uuid references pmoves_kb.documents(doc_id) on delete cascade,
  section_id uuid references pmoves_kb.sections(section_id) on delete set null,
  pack_id    uuid,                               -- nullable; resolved at query time
  text       text not null,
  tokens     int,
  embedding  vector(1536),                        -- adjust dim
  idx        int not null,
  window     int,                                 -- chars or tokens
  overlap    int,
  md         jsonb default '{}'::jsonb,           -- page,timestamps,modality
  created_at timestamptz not null default now()
);
create index if not exists idx_chunks_doc_idx on pmoves_kb.chunks(doc_id, idx);
create index if not exists idx_chunks_pack on pmoves_kb.chunks(pack_id);
create index if not exists idx_chunks_embedding on pmoves_kb.chunks using ivfflat (embedding vector_cosine_ops) with (lists = 100);

-- ===============
-- Grounding Packs & Membership
-- ===============
create table if not exists pmoves_core.grounding_packs (
  pack_id     uuid primary key default gen_random_uuid(),
  name        text not null,
  version     text not null default '1.0',
  owner       text not null,                     -- @handle or team
  description text,
  policy      jsonb default '{}'::jsonb,
  created_at  timestamptz not null default now()
);
create unique index if not exists uq_pack_name_version on pmoves_core.grounding_packs(name, version);

create table if not exists pmoves_core.pack_members (
  pack_id    uuid references pmoves_core.grounding_packs(pack_id) on delete cascade,
  asset_id   uuid references pmoves_core.assets(asset_id) on delete cascade,
  selectors  jsonb default '{}'::jsonb,          -- pages,timecodes,regions
  weight     real default 1.0,
  notes      text,
  primary key (pack_id, asset_id)
);

-- ===============
-- Personas & Eval Gates
-- ===============
create table if not exists pmoves_core.personas (
  persona_id    uuid primary key default gen_random_uuid(),
  name          text not null,
  version       text not null default '1.0',
  description   text,
  runtime       jsonb not null default '{}'::jsonb,    -- tools, model, tone, constraints
  default_packs text[] not null default '{}',
  boosts        jsonb not null default '{}'::jsonb,    -- entities/topics boosts
  filters       jsonb not null default '{}'::jsonb,    -- type/date filters
  created_at    timestamptz not null default now()
);
create unique index if not exists uq_persona_name_version on pmoves_core.personas(name, version);

create table if not exists pmoves_core.persona_eval_gates (
  persona_id  uuid references pmoves_core.personas(persona_id) on delete cascade,
  dataset_id  text not null,
  metric      text not null,               -- e.g., top3_hit@k, MRR@10
  threshold   real not null,
  last_run    timestamptz,
  pass        boolean,
  primary key (persona_id, dataset_id, metric)
);

-- ===============
-- Geometry (bus minimal index)
-- ===============
create table if not exists pmoves_core.shape_index (
  shape_id    uuid primary key,            -- from CGP
  summary     text,
  anchor_meta jsonb default '{}'::jsonb,
  updated_at  timestamptz not null default now()
);
```

---
## SQL – Policies & Indexing (optional hardening)
```sql
-- Text search accel (optional Meili external; locally use trigram for LIKE)
create index if not exists idx_chunks_text_trgm on pmoves_kb.chunks using gin (text gin_trgm_ops);

-- Simple RLS sketch (tighten for production)
alter table pmoves_core.assets enable row level security;
create policy assets_ro on pmoves_core.assets for select using (true);

alter table pmoves_core.grounding_packs enable row level security;
create policy packs_ro on pmoves_core.grounding_packs for select using (true);

-- Add similar policies for other tables as needed and restrict write to service role.
```

---
## Event Contracts (NATS / HTTP semantics)

### kb.ingest.asset.created.v1
```json
{
  "event": "kb.ingest.asset.created.v1",
  "asset_id": "uuid",
  "uri": "s3://assets/…",
  "type": "video|audio|image|pdf|html|docx|code",
  "source": "youtube|upload|crawler|comfyui",
  "meta": {"title": "…", "language": "en"}
}
```
**Consumer**: Indexer → create `documents/sections/chunks`, embed, push to Meili/Qdrant; emit `kb.index.completed.v1`.

### kb.index.completed.v1
```json
{ "event": "kb.index.completed.v1", "asset_id": "uuid", "doc_id": "uuid" }
```
**Consumer**: Gateway cache warm; optional analytics.

### kb.pack.published.v1
```json
{ "event": "kb.pack.published.v1", "pack_id": "uuid", "name": "pmoves-architecture", "version": "1.0" }
```
**Consumer**: Gateway → prefer pack scope for persona queries.

### persona.published.v1
```json
{ "event": "persona.published.v1", "persona_id": "uuid", "name": "Archon", "version": "1.0" }
```
**Consumer**: Gateway/Agent runtime registry.

### geometry.cgp.v1
```json
{
  "event": "geometry.cgp.v1",
  "shape_id": "uuid",
  "anchors": [ {"id":"a1","vec":[…],"meta":{}} ],
  "constellations": [ {"id":"c1","anchor":"a1","summary":"…","spectrum":[…]} ],
  "points": [ {"id":"p1","constellation":"c1","modality":"video","ref":"s3://…#t=12.5"} ],
  "sign": {"alg":"HMAC-SHA256","sig":"…"}
}
```
**Consumer**: Gateway ShapeStore cache; UI `/geometry/` live update.

### content.published.v1 (creator pipeline)
```json
{
  "event": "content.published.v1",
  "studio_id": "uuid",
  "title": "…",
  "author": "…",
  "uri": "https://…",
  "thumbnail": "https://…",
  "tags": ["…"],
  "jellyfin_item_url": "https://…"  
}
```
**Producer**: Publisher. **Consumers**: Discord (webhook), Jellyfin refresher, audit.

---
## Minimal REST (Gateway) – Persona‑aware Query
```
POST /kb/query
{
  "q": "How does the Presign→Webhook flow work?",
  "persona": "Archon@1.0",
  "packs": ["pmoves-architecture@1.0"],
  "top_k": 12
}
-- returns reranked results + citations; falls back to global if pack recall is low
```

---
## Seed Examples (YAML Manifests)

### personas/archon@1.0.yaml
```yaml
name: Archon
version: "1.0"
intent: Controller/retriever for PMOVES
model: gpt-4o
tools: [hirag.query, kb.viewer, geometry.jump, geometry.decode_text]
policies:
  freshness_months: 18
  must_cite: true
default_packs: [pmoves-architecture@1.0, recent-delta@rolling]
boosts:
  entities: ["Hi-RAG","LangExtract","Neo4j","Qdrant"]
filters:
  exclude_types: ["raw-audio"]
```

### packs/pmoves-architecture@1.0.yaml
```yaml
name: pmoves-architecture
version: "1.0"
owner: "@cataclysmstudios"
description: Core docs for PMOVES architecture and services.
members:
  - asset: "s3://assets/docs/PMOVES_ARC.md"
    selectors: { pages: [1,2,3] }
    weight: 1.0
  - asset: "s3://assets/docs/HI_RAG_RERANKER.md"
    selectors: { sections: ["Overview","API"] }
    weight: 1.2
policy:
  allow_external_links: true
```

---
## Rollout Checklist
- [ ] Apply SQL migrations; verify indexes built (IVFFLAT requires analyze/vacuum).
- [ ] Set `.env` additions; restart gateway, workers.
- [ ] Enable reranker; confirm retrieval‑eval passes gates for Archon.
- [ ] Create 2–3 initial packs + 1 persona; publish.
- [ ] Finish Publisher: set Discord/Jellyfin vars; test end‑to‑end image publish.
- [ ] Geometry bus: ensure analysis workers emit `geometry.cgp.v1`; verify ShapeStore hops.
- [ ] Add pack linter (CI) for selectors/age/size limits.
```

---
## Notes
- Adjust `vector(1536)` to your embedding dimension (e.g., 3584 for HF E5‑Large).
- If using Meilisearch, continue pushing `chunks.text` with `chunk_id` as doc id; gateway performs fusion before rerank.
- Approvals UI can be a simple page calling Supabase REST to flip `status` in `studio_board` (not shown here).
```



---
## SQL – Seed Data (packs, members, personas)
> Save as `db/v5_12_seed.sql`. Safe to re-run; uses `ON CONFLICT` guards.

```sql
-- Helper: upsert asset rows for docs you already have in MinIO (adjust URIs/titles)
insert into pmoves_core.assets (asset_id, uri, type, mime, title, source)
values
  (gen_random_uuid(), 's3://assets/docs/PMOVES_ARC.md', 'pdf', 'text/markdown', 'PMOVES Architecture', 'upload'),
  (gen_random_uuid(), 's3://assets/docs/HI_RAG_RERANKER.md', 'pdf', 'text/markdown', 'Hi-RAG Reranker', 'upload'),
  (gen_random_uuid(), 's3://assets/docs/RETRIEVAL_EVAL_GUIDE.md', 'pdf', 'text/markdown', 'Retrieval Eval Guide', 'upload')
on conflict do nothing;

-- Lookup asset_ids for pack membership
with a as (
  select asset_id, uri from pmoves_core.assets
  where uri in (
    's3://assets/docs/PMOVES_ARC.md',
    's3://assets/docs/HI_RAG_RERANKER.md',
    's3://assets/docs/RETRIEVAL_EVAL_GUIDE.md'
  )
)
select * from a;  -- optional visibility during psql run

-- Create/Upsert: Grounding Pack pmoves-architecture@1.0
insert into pmoves_core.grounding_packs (pack_id, name, version, owner, description, policy)
values (
  gen_random_uuid(), 'pmoves-architecture', '1.0', '@cataclysmstudios',
  'Core docs for PMOVES architecture, contracts, and services.',
  '{"allow_external_links": true}'::jsonb
)
on conflict (name, version) do update
set owner = excluded.owner,
    description = excluded.description,
    policy = excluded.policy
returning pack_id into strict _pack_arch;

-- If your psql doesn''t support INTO, do a SELECT after insert to fetch pack_id
-- For portability, we''ll emulate via CTEs below.

-- Pack ID resolve (portable)
with p as (
  select pack_id from pmoves_core.grounding_packs
  where name='pmoves-architecture' and version='1.0'
),
assets as (
  select asset_id, uri from pmoves_core.assets
  where uri in (
    's3://assets/docs/PMOVES_ARC.md',
    's3://assets/docs/HI_RAG_RERANKER.md',
    's3://assets/docs/RETRIEVAL_EVAL_GUIDE.md'
  )
)
insert into pmoves_core.pack_members (pack_id, asset_id, selectors, weight, notes)
select p.pack_id, a.asset_id,
       case a.uri
         when 's3://assets/docs/PMOVES_ARC.md' then '{"pages":[1,2,3]}'::jsonb
         when 's3://assets/docs/HI_RAG_RERANKER.md' then '{"sections":["Overview","API"]}'::jsonb
         when 's3://assets/docs/RETRIEVAL_EVAL_GUIDE.md' then '{"sections":["Datasets","Metrics"]}'::jsonb
         else '{}'::jsonb
       end as selectors,
       case a.uri
         when 's3://assets/docs/HI_RAG_RERANKER.md' then 1.2
         else 1.0
       end as weight,
       null as notes
from p, assets a
on conflict (pack_id, asset_id) do update
set selectors = excluded.selectors,
    weight    = excluded.weight;

-- Seed Persona: Archon@1.0
insert into pmoves_core.personas (persona_id, name, version, description, runtime, default_packs, boosts, filters)
values (
  gen_random_uuid(), 'Archon', '1.0', 'Controller/retriever for PMOVES',
  '{"model":"gpt-4o","tools":["hirag.query","kb.viewer","geometry.jump","geometry.decode_text"],"policies":{"freshness_months":18,"must_cite":true}}'::jsonb,
  ARRAY['pmoves-architecture@1.0','recent-delta@rolling'],
  '{"entities":["Hi-RAG","LangExtract","Neo4j","Qdrant"]}'::jsonb,
  '{"exclude_types":["raw-audio"]}'::jsonb
)
on conflict (name, version) do update
set description = excluded.description,
    runtime     = excluded.runtime,
    default_packs = excluded.default_packs,
    boosts      = excluded.boosts,
    filters     = excluded.filters;

-- Gate: retrieval quality must pass before persona publish
insert into pmoves_core.persona_eval_gates (persona_id, dataset_id, metric, threshold, pass)
select p.persona_id, 'archon-smoke-10', 'top3_hit@k', 0.80, null
from pmoves_core.personas p where p.name='Archon' and p.version='1.0'
on conflict (persona_id, dataset_id, metric) do update
set threshold = excluded.threshold;

-- Optional: Seed a rolling "recent-delta@rolling" logical pack in notes (no rows needed)
-- You can implement recent-delta as a query-time filter (last 60 days) instead of a static pack.

-- Verify
select name, version, owner from pmoves_core.grounding_packs;
select name, version, default_packs from pmoves_core.personas;
select count(*) as members from pmoves_core.pack_members pm
join pmoves_core.grounding_packs gp on gp.pack_id = pm.pack_id
where gp.name='pmoves-architecture' and gp.version='1.0';
```

---
## (Optional) SQL – Sample Asset Rows for ComfyUI Outputs
```sql
-- When Publisher runs, it will audit to publisher_audit (not shown here). If you want
-- a manual test asset (image) before wiring Comfy → Webhook, seed one:
insert into pmoves_core.assets (uri, type, mime, title, source, thumbnail_uri)
values ('s3://outputs/2025/pmoves-sample.png','image','image/png','PMOVES Sample Render','comfyui','s3://outputs/2025/pmoves-sample-thumb.jpg')
on conflict do nothing;
```
```



---
# v5.12.1 – CHIT Geometry First‑Class (Services, Agents, SQL, Make)

This patch makes **CHIT (geometry bus + decoders)** a first‑class slice of PMOVES and wires live alignment via Supabase Realtime.

## Geometry Service Group (new)
**Services**
- `geometry-gateway` (API + ShapeStore cache)
- `geometry-decoder` (text/image/audio; enable via flags)
- `geometry-calibration` (metrics, reports)

**Env toggles (.env)**
```
# Geometry core
ENABLE_GEOMETRY=true
GEOMETRY_SHARED_SECRET=change_me    # HMAC for CGP events
GEOMETRY_ENCRYPT_ANCHORS=false      # AES-GCM optional

# Decoders
CHIT_DECODE_TEXT=true
CHIT_DECODE_IMAGE=false
CHIT_DECODE_AUDIO=false

# Realtime (Supabase)
SUPABASE_REALTIME_ENABLED=true
```

**Versioned Endpoints (v0.2)**
```
POST /v0/geometry/event                # ingest CGP (HMAC required)
GET  /v0/shape/{shape_id}              # anchors + constellations + points
GET  /v0/shape/point/{point_id}/jump   # locator (video t=, doc span, image bbox)
POST /v0/geometry/decode/{mod}         # mod ∈ {text,image,audio}
POST /v0/geometry/calibration/report   # KL/JS/W1/coverage
GET  /v0/healthz                       # liveness/ready
```

**Agent tools (register in Agent Zero & Archon)**
- `geometry.publish_cgp`, `geometry.jump`, `geometry.decode_text|image|audio`, `geometry.calibration_report`.
- Route by intent: media/visual → prefer geometry tools; always include `shape_id` in logs/telemetry.

## Make Targets (new)
```make
smoke-geometry: ## Post fixture CGP, decode, jump, calibration, assert OK
	python scripts/chit_client.py --base $$GATEWAY_URL \
	  --cgp tests/data/cgp_fixture.json --sign $$GEOMETRY_SHARED_SECRET \
	  --encrypt-anchors=$$GEOMETRY_ENCRYPT_ANCHORS

realtime-on: ## Enable Supabase realtime for geometry tables
	psql $$DATABASE_URL -f db/v5_12_geometry_realtime.sql

migrate-geometry: ## Apply geometry RLS/DLQ/health views
	psql $$DATABASE_URL -f db/v5_12_geometry_rls.sql
```

## SQL – Realtime & RLS (save as `db/v5_12_geometry_rls.sql`)
```sql
-- RLS: read‑only to anon; writes via service role
alter table if exists public.anchors        enable row level security;
alter table if exists public.constellations enable row level security;
alter table if exists public.shape_points   enable row level security;
alter table if exists pmoves_core.shape_index enable row level security;

create policy anchors_ro on public.anchors for select to anon using (true);
create policy const_ro   on public.constellations for select to anon using (true);
create policy points_ro  on public.shape_points for select to anon using (true);
create policy sidx_ro    on pmoves_core.shape_index for select to anon using (true);

-- Dead‑letter for failed events (publisher/indexer/geometry)
create table if not exists public.event_dlq(
  id bigserial primary key,
  event_type text not null,
  payload jsonb not null,
  error text,
  retried_at timestamptz,
  created_at timestamptz default now()
);

-- Minimal health view (optional)
create or replace view public.geometry_health as
select 'anchors' as table, count(*) as rows from public.anchors
union all
select 'constellations', count(*) from public.constellations
union all
select 'shape_points', count(*) from public.shape_points;
```

## SQL – Realtime Publication (save as `db/v5_12_geometry_realtime.sql`)
```sql
-- Enable realtime stream on geometry tables
alter publication supabase_realtime add table public.shape_points;
alter publication supabase_realtime add table public.constellations;
```

## Live Alignment Query (UI/Graph highlight)
```sql
-- Text ↔ Video alignment via shared constellation anchor (for UI highlight)
select 
  txt.ref_id   as text_doc,
  vid.ref_id   as video_id,
  vid.t_start, vid.t_end,
  a.vec        as anchor_vec
from public.shape_points txt
join public.shape_points vid on vid.constellation_id = txt.constellation_id
join public.constellations c on c.id = txt.constellation_id
join public.anchors a        on a.id = c.anchor_id
where txt.modality='text' and vid.modality='video'
  and txt.ref_id = $1;  -- e.g., 'doc123'
```

## n8n Fallback (no Realtime)
- Poll `public.shape_points` for `created_at > last_seen` every 5s.
- On new rows, call `GET /v0/shape/{shape_id}` and push to UI bus.

## Observability
- Add Prometheus counters: `geometry_events_total`, `geometry_decode_seconds`, `geometry_shape_cache_hits_total`.
- Structured logs include `shape_id`, `constellation_id`, `point_id` in every span.

## Compose/Profile Notes
- Add `geometry` profile; start with `--profile geometry --profile gateway`.
- Ensure `ENABLE_GEOMETRY=true` and secrets set; fail fast if missing.

## Quick CLI (developer)
```bash
python scripts/chit_client.py \
  --base http://localhost:8087 \
  --cgp tests/data/cgp_fixture.json \
  --sign "$GEOMETRY_SHARED_SECRET" \
  --encrypt-anchors=$GEOMETRY_ENCRYPT_ANCHORS
```

