# UNFCU DoX — Architecture Overview

> Presentation-ready architecture reference for the UNFCU Document Intelligence platform.
> Each tier is independently deployable and independently beats Synaptic at that level.

---

## System Architecture (All 4 Tiers)

```
╔══════════════════════════════════════════════════════════════════════╗
║                    TIER 4: AUTONOMOUS OPERATIONS                    ║
║                                                                      ║
║  Agent Zero ─── SupaSerch ─── DeepResearch ─── EvoSwarm             ║
║    (8080)        (8099)        (8098)          (8113)               ║
║      │                                                               ║
║  Gateway Agent ── BoTZ Gateway ── Flute Voice ── Consciousness      ║
║    (8100)          (8054)         (8055)          (8105)            ║
╠══════════════════════════════════════════════════════════════════════╣
║                    TIER 3: SECURE EXECUTION                         ║
║                                                                      ║
║  E2B Sandbox ── E2B Desktop ── E2B Surf ── E2B MCP                  ║
║    (7070)        (6080)        (3080)      (7073)                   ║
║         Firecracker microVMs │ KVM isolation                        ║
║                              │                                       ║
║  CHIT Attribution ── Graphiti Trail ── JWT Auth ── NATS Auth        ║
║                                                                      ║
║  Prometheus ─── Grafana ─── Loki ─── TZ ClickHouse                  ║
║    (9090)       (3002)     (3100)     (8123)                        ║
╠══════════════════════════════════════════════════════════════════════╣
║                    TIER 2: KNOWLEDGE PLATFORM                       ║
║                                                                      ║
║  Hi-RAG v2 ─────────── TensorZero Gateway                           ║
║  (8086/8087)            (3030)                                       ║
║    │  │  │                │                                          ║
║    │  │  └── Meilisearch  └── Claude / Qwen / Ollama                ║
║    │  │      (7700)           (multi-provider LLM)                  ║
║    │  └── Neo4j                                                      ║
║    │      (7474)  ◄── Compliance graph                              ║
║    └── Qdrant                                                        ║
║        (6333)  ◄── Vector embeddings                                ║
║                                                                      ║
║  Supabase (8000) ◄── PostgreSQL + Auth + RLS                        ║
╠══════════════════════════════════════════════════════════════════════╣
║                    TIER 1: DOCUMENT INTELLIGENCE                    ║
║                                                                      ║
║  ┌─────────────────────────────────────────────────────────┐        ║
║  │              UNFCU DoX Frontend (3001)                   │        ║
║  │     Next.js 16 │ React 19 │ Tailwind │ UNFCU Brand     │        ║
║  │                                                          │        ║
║  │  Workspace │ Artifacts │ Search │ Q&A │ Geometry │ Logs │        ║
║  └──────────────────────────┬──────────────────────────────┘        ║
║                              │                                       ║
║  ┌──────────────────────────▼──────────────────────────────┐        ║
║  │              UNFCU DoX Backend (8484)                    │        ║
║  │     FastAPI │ Docling │ FAISS │ spaCy │ JWT Auth        │        ║
║  │                                                          │        ║
║  │  /documents  │  /search  │  /analysis  │  /graph        │        ║
║  │  /cipher     │  /system  │  /models    │  /a2a          │        ║
║  └─────────────────────────────────────────────────────────┘        ║
║                                                                      ║
║  Ingestion: PDF │ CSV │ XLSX │ XML │ OpenAPI │ Media │ Web          ║
╚══════════════════════════════════════════════════════════════════════╝
```

---

## Data Flow: Document Lifecycle

```
UNFCU Staff uploads PDF
       │
       ▼
DoX Backend (8484)
  ├── Docling extracts text, tables, formulas, images
  ├── spaCy + LangExtract: NER, language detection
  ├── FAISS indexes embeddings (Tier 1)
  │
  ├── [Tier 2] Qdrant + Meilisearch indexing via Extract Worker
  ├── [Tier 2] Neo4j: store compliance relationships
  ├── [Tier 2] TensorZero: generate summary via LLM
  │
  ├── [Tier 3] NATS: publish ingest.file.added.v1
  ├── [Tier 3] CHIT: sign provenance trail
  ├── [Tier 3] Prometheus: record ingestion metrics
  │
  └── [Tier 4] Agent Zero: trigger downstream analysis
              ├── SupaSerch: cross-reference with external sources
              ├── DeepResearch: generate compliance assessment
              └── Flute: voice notification of completion
```

---

## Search Flow: Query Lifecycle

```
UNFCU Staff asks: "What are our Basel III capital requirements?"
       │
       ▼
  [Tier 1] DoX FAISS vector search
       │ ── returns top-k similar chunks with citations
       │
  [Tier 2] Hi-RAG v2 hybrid retrieval
       ├── Qdrant: semantic vector matches
       ├── Neo4j: traverse compliance → regulation → requirement graph
       ├── Meilisearch: exact term matches in regulatory docs
       └── Cross-encoder reranking → best results
       │
  [Tier 2] TensorZero → LLM generates answer with citations
       │
  [Tier 3] Audit: log query + response + sources in ClickHouse
       │
  [Tier 4] Agent Zero can auto-research if answer is incomplete
       └── DeepResearch plans multi-step investigation
```

---

## Security Architecture (Tier 3)

```
                   Internet
                      │
               ┌──────▼──────┐
               │   Reverse    │
               │   Proxy      │  TLS termination
               └──────┬──────┘
                      │
          ┌───────────┼───────────┐
          │           │           │
     ┌────▼───┐  ┌───▼────┐  ┌──▼──────┐
     │Frontend │  │Backend │  │Grafana  │
     │  :3001  │  │ :8484  │  │  :3002  │
     └────┬───┘  └───┬────┘  └─────────┘
          │          │
          │     JWT Validation (fail-closed)
          │     HS256 HMAC-SHA256
          │          │
     ┌────▼──────────▼────┐
     │    NATS Bus (:4222) │  Authenticated
     │    nats:pmoves@     │  JetStream enabled
     └────────┬───────────┘
              │
    ┌─────────┼──────────┐
    │         │          │
┌───▼───┐ ┌──▼───┐ ┌───▼──────┐
│ CHIT  │ │Loki  │ │ClickHse │
│ Trail │ │:3100 │ │ :8123   │
└───────┘ └──────┘ └─────────┘

E2B Sandbox Isolation:
┌─────────────────────────────┐
│ Firecracker microVM (KVM)   │
│   ├── 2 CPU cores (cgroup)  │
│   ├── 2 GB RAM (cgroup)     │
│   ├── No internet (default) │
│   ├── Separate netns         │
│   └── UID 65532 (non-root)  │
└─────────────────────────────┘
```

---

## Deployment Options

### Option A: Standalone (Fastest — Tier 1 Only)
```bash
cd UNFCU-DoX
docker compose up -d  # backend + frontend + SQLite
```
- 2 containers, no external dependencies
- SQLite for persistence
- FAISS for local vector search
- Demo-ready in minutes

### Option B: Knowledge Platform (Tier 1 + 2)
```bash
cd UNFCU-DoX
docker compose -f docker-compose.supabase.yml up -d
# + parent PMOVES services
make -C pmoves up-data up-agents
```
- Supabase, Qdrant, Meilisearch, Neo4j, TensorZero
- Hi-RAG v2 hybrid retrieval
- Multi-provider LLM routing

### Option C: Full Stack (All 4 Tiers)
```bash
make -C pmoves env-setup
make -C pmoves up  # All profiles
cd UNFCU-DoX
docker compose -f docker-compose.docked.yml up -d
```
- Everything: agents, sandboxes, observability, voice
- The royal flush

---

## Key Metrics for Presentation

| Metric | Value | Source |
|--------|-------|--------|
| Input formats supported | 10+ | DoX ingestion pipeline |
| Search latency (p99) | <200ms | FAISS + Hi-RAG benchmark |
| LLM providers available | 7+ | TensorZero routing config |
| Concurrent sandboxes | 5 | E2B Firecracker config |
| Agent tools available | 100+ | BoTZ MCP marketplace |
| NATS event subjects | 40+ | `.claude/context/nats-subjects.md` |
| Docker services (full) | 60+ | `docker-compose.yml` |
| Code: DoX backend | 15K+ lines | FastAPI + ingestion + search |
| Code: DoX frontend | 10K+ lines | Next.js + D3 + Three.js |
| TAC documentation | 40 files | Comprehensive architecture docs |

---

## UNFCU-Specific Use Cases

### 1. Regulatory Document Intelligence
- Ingest Basel III, NCUA, FATF, AML/KYC regulatory documents
- Neo4j maps regulation → requirement → policy → procedure chains
- Q&A: "What are our obligations under NCUA regulation 12 CFR 701?"
- Agent auto-research: cross-reference with latest regulatory updates

### 2. Compliance Audit Trail
- Every document access, search, and LLM interaction logged
- CHIT-signed provenance chain: who accessed what, when, why
- Grafana dashboards for compliance officers
- Export audit reports for examiners

### 3. Multi-Language Support (190+ Countries)
- LangExtract language detection for multilingual document corpus
- TensorZero routes to language-appropriate LLM models
- Flute Gateway voice interface for accessibility
- Supabase RLS isolates country-office data

### 4. Secure Code Execution for Analytics
- UNFCU analysts run Python scripts on financial data
- E2B Firecracker sandbox: isolated, resource-limited, audited
- No code touches production data directly — sandbox reads from MinIO
- Results reviewed before export

### 5. Board Document Management
- Complements existing Aprio board portal
- DoX handles the document intelligence layer Aprio can't
- Ingest board packets, extract key metrics, generate summaries
- Knowledge graph tracks decision → action → outcome chains
