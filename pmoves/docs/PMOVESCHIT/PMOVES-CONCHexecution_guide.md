# PMOVES Consciousness Integration • Execution Guide
_Last updated: 2025-12-09_

This guide operationalizes the consciousness knowledge harvest and its transformation into grounded personas via the PMOVES stack (Supabase, Geometry Bus, CHIT playback, Hi-RAG v2, Evo Swarm).

---

## Architecture Overview

```
Consciousness Dataset (Landscape of Consciousness taxonomy)
    │
    ▼
CHR (Constellation Harvest Regularization)
    │ embeddings → optimize anchors U → soft assignments p
    ▼
Constellations (directional modes + entropy profiles)
    │
    ▼
CGP (CHIT Geometry Packet) - encoded shapes
    │
    ▼
Geometry Bus Publication → Hi-RAG v2 ShapeStore
    │
    ▼
Persona Grounding (consciousness shapes → combinations → LLM selection)
```

**Key Concepts:**
- **Anchors (U)**: Unit direction vectors in embedding space (K constellations, e.g., K=8)
- **Soft Assignments (p)**: Probability distribution of each unit across constellations
- **Spectrum**: Soft histogram of projections (slab entropy, tau-softmax)
- **Super-nodes**: Meta-clustering of anchors (S clusters) = "Resonant Modes"
- **CGP**: CHIT Geometry Packet - compact geometric encoding of consciousness domains

---

## Current State Assessment

| Component | Status | Notes |
|-----------|--------|-------|
| Directory structure | ✅ Created | 10 theory categories |
| Research papers | ✅ 3 files | ~2MB HTML content |
| RAG schema | ✅ SQL exists | consciousness-schema.sql |
| Theory content | ❌ Empty | Needs harvest scripts |
| Website mirror | ❌ Empty | Needs Selenium scraper |
| Embeddings JSONL | ⚠️ Minimal | Only 3 chunks |
| CGP mapper | ❌ Missing | Needs implementation |
| Persona eval gates | ❌ Not wired | Schema only |

---

## Phase 0: Stack Initialization

```bash
# Core infrastructure
make env-setup
make supa-start
make up
make up-agents

# Verify services are healthy
make verify-all
```

**Optional services:**
```bash
make up-n8n          # Embedding automation workflows
make notebook-up     # Open Notebook enrichment
make web-geometry    # Geometry visualization UI
make up-yt           # PMOVES.YT video ingestion
```

**Expected ports:**
| Service | Port | Purpose |
|---------|------|---------|
| Hi-RAG v2 | 8086 | Hybrid retrieval + ShapeStore |
| Agent Zero | 8080 | Orchestration + MCP API |
| TensorZero | 3030 | LLM gateway |
| Supabase | 5432 | Postgres + pgvector |
| Qdrant | 6333 | Vector embeddings |
| Neo4j | 7687 | Knowledge graph |
| NATS | 4222 | Event bus |

---

## Phase 1: Data Harvest (2-4 hours)

### 1.1 Static Content Harvest

```bash
# Primary harvester - downloads research papers, creates directory scaffold
bash "pmoves/docs/PMOVES.AI PLANS/consciousness_downloader.sh"

# Or via make target
make -C pmoves harvest-consciousness
```

**Expected outputs in `pmoves/data/consciousness/Constellation-Harvest-Regularization/`:**
```
├── categories/              # Category taxonomy
├── theories/                # 10 theory directories
│   ├── Anomalous-Altered-States/
│   ├── Challenge-Theories/
│   ├── Dualisms/
│   ├── Idealisms/
│   ├── Integrated-Information-Theory/
│   ├── Materialism-Theories/
│   ├── Monisms/
│   ├── Non-Reductive-Physicalism/
│   ├── Panpsychisms/
│   └── Quantum-Theories/
├── research-papers/         # PDFs, HTML articles
├── website-mirror/          # Static HTML snapshots
├── data-exports/            # discovered-links.json
└── scripts/                 # Generated automation helpers
```

### 1.2 Dynamic Content Harvest (Selenium)

Requires Windows/Chrome with Selenium:

```powershell
# On Windows host with Chrome + Selenium installed
pwsh -File pmoves/data/consciousness/Constellation-Harvest-Regularization/scripts/selenium-scraper.ps1
```

**Alternative (manual):**
```powershell
pwsh -File "pmoves/docs/PMOVES.AI PLANS/consciousness_downloader.ps1"
```

This captures JavaScript-rendered content from closertotruth.com theory pages.

### 1.3 Verification

```bash
# Check theory content populated
find pmoves/data/consciousness/Constellation-Harvest-Regularization/theories -name "*.html" -o -name "*.md" | wc -l
# Expected: 50-200 files

# Check research papers
ls -la pmoves/data/consciousness/Constellation-Harvest-Regularization/research-papers/

# Check discovered links
cat pmoves/data/consciousness/Constellation-Harvest-Regularization/data-exports/discovered-links.json | jq length
```

---

## Phase 2: Chunking & Embedding Preparation (1-2 hours)

### 2.1 Generate Chunked JSONL

```bash
# Run consciousness build script
python pmoves/tools/consciousness_build.py

# Or manual chunking
python -c "
import json
from pathlib import Path

theories_dir = Path('pmoves/data/consciousness/Constellation-Harvest-Regularization/theories')
chunks = []

for theory_dir in theories_dir.iterdir():
    if theory_dir.is_dir():
        for html_file in theory_dir.glob('*.html'):
            # Strip HTML, chunk by paragraph
            # Add to chunks with metadata
            pass

# Write to JSONL
output = Path('pmoves/data/consciousness/Constellation-Harvest-Regularization/processed-for-rag/embeddings-ready/consciousness-chunks.jsonl')
with open(output, 'w') as f:
    for chunk in chunks:
        f.write(json.dumps(chunk) + '\n')
"
```

**Expected JSONL format:**
```json
{"id": "chunk_001", "text": "...", "category": "Panpsychisms", "source_url": "...", "namespace": "pmoves.consciousness"}
```

### 2.2 Apply Supabase Schema

```bash
# Option A: Supabase CLI
supabase status --output env > supabase/.tmp_env && source supabase/.tmp_env
psql "${SUPABASE_DB_URL}" -f pmoves/data/consciousness/Constellation-Harvest-Regularization/processed-for-rag/supabase-import/consciousness-schema.sql

# Option B: Docker Compose runtime
docker compose -p pmoves exec postgres psql -U pmoves -d pmoves -f /data/consciousness/Constellation-Harvest-Regularization/processed-for-rag/supabase-import/consciousness-schema.sql
```

**Schema creates:**
```sql
create table consciousness_theories (
  id text primary key,
  title text not null,
  url text,
  category text,
  content text not null,
  embedding vector(1536),
  namespace text default 'pmoves.consciousness',
  created_at timestamptz default now()
);

create index idx_consciousness_embedding
  on consciousness_theories using ivfflat (embedding vector_cosine_ops);
create index idx_consciousness_category
  on consciousness_theories(category);
```

### 2.3 Generate Embeddings via n8n

```bash
make up-n8n
```

1. Open n8n UI at http://localhost:5678
2. Import workflow: `processed-for-rag/supabase-import/n8n-workflow.json`
3. Configure credentials:
   - Hugging Face API token (or use TensorZero embeddings endpoint)
   - Supabase connection string
4. Execute workflow
5. Monitor progress in Prometheus/Grafana

**Alternative: Direct TensorZero embedding:**
```bash
# For each chunk
curl -X POST http://localhost:3030/openai/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{"model": "tensorzero::embedding_model_name::qwen3_embedding_4b_local", "input": "chunk text here"}'
```

---

## Phase 3: Video Ingestion (30 min - 2 hours)

### 3.1 Configure Video Sources

Edit `processed-for-rag/supabase-import/consciousness-video-sources.json`:

```json
{
  "sources": [
    {"url": "https://youtube.com/watch?v=xxx", "theory": "Panpsychisms"},
    {"url": "https://youtube.com/watch?v=yyy", "theory": "Integrated-Information-Theory"}
  ]
}
```

### 3.2 Ingest via PMOVES.YT

```bash
make up-yt

# Dry run first
make ingest-consciousness-yt ARGS="--max 5 --dry-run"

# Review output, then run for real
make ingest-consciousness-yt ARGS="--max 5"
```

**Pipeline:**
1. PMOVES.YT downloads video to MinIO
2. FFmpeg-Whisper transcribes audio
3. Transcript indexed to Hi-RAG
4. NATS events published:
   - `ingest.file.added.v1`
   - `ingest.transcript.ready.v1`

---

## Phase 4: CGP Generation & Geometry Publication (1-2 hours)

### 4.1 Generate CGP Packets

**Using CHIT encoder:**
```bash
python pmoves/tools/chit_backend.py \
  --input pmoves/data/consciousness/Constellation-Harvest-Regularization/processed-for-rag/embeddings-ready/consciousness-chunks.jsonl \
  --output pmoves/data/consciousness/geometry_payload.json \
  --K 8 \
  --bins 8 \
  --backend sentence-transformers/all-MiniLM-L6-v2
```

**Expected CGP structure:**
```json
{
  "spec": "chit.cgp.v0.1",
  "meta": {
    "source": "consciousness-harvest",
    "K": 8,
    "bins": 8,
    "mhep": 2.45,
    "backend": "sentence-transformers/all-MiniLM-L6-v2"
  },
  "super_nodes": [
    {
      "id": "super_0",
      "label": "Resonant Mode 0 (Panpsychism cluster)",
      "constellations": [
        {
          "id": "const_0_0",
          "anchor": [0.012, -0.31, ...],
          "summary": "consciousness, experience, fundamental",
          "spectrum": [0.08, 0.11, 0.15, ...],
          "points": [...]
        }
      ]
    }
  ]
}
```

### 4.2 Publish to Geometry Bus

```bash
# Option A: Make target
make mesh-handshake FILE=pmoves/data/consciousness/geometry_payload.json

# Option B: Direct NATS publish
nats pub geometry.cgp.v1 "$(cat pmoves/data/consciousness/geometry_payload.json)"

# Option C: Agent Zero API
curl -X POST http://localhost:8080/events/publish \
  -H "Content-Type: application/json" \
  -d @pmoves/data/consciousness/geometry_payload.json
```

### 4.3 Verify Geometry Ingestion

```bash
# Smoke tests
make smoke-geometry
make smoke-geometry-db

# Visual verification
make web-geometry
# Open http://localhost:3000/geometry

# Query Hi-RAG with shape constraint
curl -X POST http://localhost:8086/hirag/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "what is consciousness",
    "top_k": 10,
    "shape_id": "super_0",
    "constellation_id": "const_0_0"
  }'
```

---

## Phase 5: Persona Grounding (1-2 hours)

### 5.0 Prerequisites - Apply Grounding Schema

Before creating grounding packs and personas, ensure the required tables exist:

```bash
# Apply the grounded personas schema (creates grounding_packs, personas, persona_eval_gates tables)
psql "${SUPABASE_DB_URL}" -f pmoves/db/v5_12_grounded_personas.sql

# Or via Docker Compose
docker compose -p pmoves exec postgres psql -U pmoves -d pmoves -f /app/db/v5_12_grounded_personas.sql

# Verify tables were created
psql "${SUPABASE_DB_URL}" -c "\dt grounding_packs; \dt personas; \dt persona_eval_gates;"
```

**Required tables:**
- `grounding_packs` - Knowledge pack definitions
- `pack_members` - Assets linked to packs
- `personas` - Agent personas with grounding configurations
- `persona_eval_gates` - Quality thresholds for persona retrieval

### 5.1 Create Consciousness Grounding Pack

```sql
-- Insert grounding pack
INSERT INTO grounding_packs (pack_id, name, version, owner, description, policy)
VALUES (
  gen_random_uuid(),
  'pmoves-consciousness',
  '1.0',
  'pmoves',
  'Landscape of Consciousness theories, research papers, and video transcripts',
  '{"access": "public", "retrieval_limit": 50}'
);

-- Link assets to pack
INSERT INTO pack_members (pack_id, asset_id, selectors, weight, notes)
SELECT
  (SELECT pack_id FROM grounding_packs WHERE name = 'pmoves-consciousness'),
  id,
  '{"sections": ["all"]}',
  1.0,
  category
FROM consciousness_theories;
```

### 5.2 Create Consciousness Persona

```sql
INSERT INTO personas (persona_id, name, version, description, runtime, default_packs, boosts, filters)
VALUES (
  gen_random_uuid(),
  'Consciousness-Explorer',
  '1.0',
  'An expert in consciousness theories spanning materialism, dualism, panpsychism, and quantum approaches',
  '{
    "model": "claude-sonnet-4-5",
    "tools": ["hirag_query", "geometry_decode"],
    "tone": "academic yet accessible"
  }',
  ARRAY['pmoves-consciousness@1.0'],
  '{
    "entities": ["consciousness", "qualia", "phenomenal experience"],
    "topics": ["hard problem", "integrated information", "panpsychism"]
  }',
  '{"exclude_types": ["video_raw"], "min_quality": 0.7}'
);
```

### 5.3 Configure Eval Gates

```sql
-- Retrieval quality gates
INSERT INTO persona_eval_gates (persona_id, dataset_id, metric, threshold)
SELECT
  persona_id,
  'consciousness-eval-v1',
  metric,
  threshold
FROM (VALUES
  ('top3_hit@k', 0.75),
  ('MRR@10', 0.60),
  ('NDCG@5', 0.55)
) AS gates(metric, threshold),
personas WHERE name = 'Consciousness-Explorer';
```

### 5.4 Test Persona Retrieval

```bash
# Query via persona
curl -X POST http://localhost:8086/hirag/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "explain the hard problem of consciousness",
    "persona": "Consciousness-Explorer@1.0",
    "top_k": 10,
    "rerank": true
  }'
```

---

## Phase 6: Evo Swarm & Meta-Learning

### 6.1 Register Consciousness Namespace

Edit `pmoves/env.shared`:
```bash
EVOSWARM_CONTENT_NAMESPACES=pmoves.consciousness,pmoves.architecture
EVOSWARM_CONTROLLER_ENABLED=true
```

### 6.2 Restart Agents

```bash
make up-agents
```

### 6.3 Monitor Swarm Activity

```bash
# Tail swarm meta events
python pmoves/tools/realtime_listener.py --topics geometry.swarm.meta.v1 --max 10

# Or via NATS CLI
nats sub "geometry.swarm.meta.v1"
```

**Swarm meta events:**
```json
{
  "namespace": "pmoves.consciousness",
  "pack_id": "uuid",
  "status": "active",
  "best_fitness": 0.87,
  "ts": "2025-12-09T..."
}
```

---

## Phase 7: CHIT Playback Verification

### 7.1 Test Exact Decode

```bash
python pmoves/tools/chit_decoder.py \
  --cgp pmoves/data/consciousness/geometry_payload.json \
  --mode exact
```

### 7.2 Test Geometry-Only Decode

```bash
python pmoves/tools/chit_decoder.py \
  --cgp pmoves/data/consciousness/geometry_payload.json \
  --corpus pmoves/data/consciousness/.../consciousness-chunks.jsonl \
  --mode geometry \
  --compute-metrics
```

**Expected metrics:**
- KL divergence < 0.3
- Coverage > 0.8
- Per-constellation fidelity reports

### 7.3 Test Multimodal Decode (if video content)

```bash
python pmoves/tools/chit_decoder_mm.py \
  --cgp pmoves/data/consciousness/geometry_payload.json \
  --image-corpus ./images/ \
  --mode clip
```

---

## Phase 8: Validation & Documentation

### 8.1 Comprehensive Smoke Tests

```bash
make smoke
make smoke-hirag-v1
make smoke-geometry
```

### 8.2 Archive Evidence

```bash
# Create session log
mkdir -p pmoves/docs/logs/consciousness-harvest-$(date +%Y%m%d)

# Archive artifacts
cp pmoves/data/consciousness/geometry_payload.json pmoves/docs/logs/consciousness-harvest-*/
# Screenshot Geometry UI
# Export Supabase query results
```

### 8.3 Update Documentation

- [ ] `pmoves/docs/NEXT_STEPS.md` - Mark consciousness harvest tasks complete
- [ ] `pmoves/docs/context/PMOVES_COMPLETE_ARCHITECTURE.md` - Add consciousness knowledge sources
- [ ] `pmoves/docs/PMOVES.AI PLANS/FINAL_INTEGRATION_ROLLUP.md` - Update integration status

---

## Troubleshooting

### Selenium Scraper Fails
```
Error: Chrome not found
```
**Fix:** Install Chrome + ChromeDriver, ensure in PATH

### Embedding Timeout
```
Error: TensorZero request timeout
```
**Fix:** Increase `TENSORZERO_TIMEOUT=300` in env.shared, batch smaller chunks

### CGP Validation Fails
```
Error: Invalid CGP schema
```
**Fix:** Validate against `pmoves/contracts/schemas/geometry/cgp.v1.schema.json`:
```bash
python -c "
import json, jsonschema
schema = json.load(open('pmoves/contracts/schemas/geometry/cgp.v1.schema.json'))
cgp = json.load(open('pmoves/data/consciousness/geometry_payload.json'))
jsonschema.validate(cgp, schema)
print('Valid CGP')
"
```

### Hi-RAG ShapeStore Empty
```
Warning: No shapes found for query
```
**Fix:** Verify CGP published to NATS, check Hi-RAG logs:
```bash
docker logs hi-rag-gateway-v2 2>&1 | grep -i shape
```

---

## Quick Reference

| Task | Command |
|------|---------|
| Stack status | `make verify-all` |
| Harvest consciousness | `make -C pmoves harvest-consciousness` |
| Apply schema | `make supa-migrate` |
| Publish geometry | `make mesh-handshake FILE=...` |
| Smoke tests | `make smoke smoke-geometry` |
| Geometry UI | `make web-geometry` |
| NATS events | `nats sub "geometry.>"` |

**Key directories:**
- Harvest data: `pmoves/data/consciousness/Constellation-Harvest-Regularization/`
- CGP schema: `pmoves/contracts/schemas/geometry/cgp.v1.schema.json`
- CHIT tools: `pmoves/tools/chit_*.py`

---

## Missing Components (TODO)

1. **CGP Auto-Mapper**: Transform consciousness_theories → CGP packets automatically
2. **Retrieval-Eval Dataset**: 50-100 labeled queries for persona gates
3. **Persona Publish Gate Service**: Async evaluator for metric thresholds
4. **Geometry Service Endpoints**: `/v0/geometry/*` REST API
5. **Consciousness Metadata Schema**: Extended fields (author, epistemology, relations)

---

Keep this guide updated as ingestion scripts, CGP mappers, or automation targets evolve.
