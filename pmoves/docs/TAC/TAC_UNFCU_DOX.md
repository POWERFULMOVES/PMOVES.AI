# TAC_UNFCU_DOX
_Last updated: 2026-03-15_

## Mission

Private PMOVES-DoX fork for United Nations Federal Credit Union (UNFCU). Replace incumbent vendor Synaptic with a layered document intelligence platform where each tier independently outperforms the competition — from basic ECM through autonomous operations.

**Competitive strategy:** Layer the capabilities so any level Synaptic competes at, UNFCU DoX beats. The full stack is the royal flush.

## Target Environment

- **Organization:** UNFCU — 190+ countries, UN affiliated staff and family
- **Core banking:** Fiserv DNA
- **Board portal:** Aprio
- **Incumbent ECM vendor:** Synaptic (to be replaced)
- **Deployment:** Self-hosted (UNFCU infrastructure or PMOVES managed)

---

## Tier 1 — Document Intelligence

> *Beats: Basic ECM (document storage + keyword search)*

### What This Delivers
- Multi-format document ingestion: PDF, CSV, XLSX, XML, OpenAPI, Postman, media, web
- IBM Docling for PDF processing (multi-page tables, formula extraction, OCR)
- Vector search via FAISS + `all-MiniLM-L6-v2` embeddings
- Q&A engine with citation retrieval (page + bounding box coordinates)
- Structured extraction: NER, metrics, tables via spaCy + LangExtract
- UNFCU-branded Next.js 16 frontend with Tailwind theming

### Services

| Service | Port | Role |
|---------|------|------|
| DoX Backend | 8484 | FastAPI: ingestion, search, Q&A, extraction |
| DoX Frontend | 3001 | Next.js: UNFCU-branded document UI |
| SQLite/Supabase | — | Persistence (factory pattern, switchable) |

### Why It Beats Synaptic at Tier 1
- **10+ input formats** vs Synaptic's PDF + Office
- **Semantic vector search** vs keyword matching
- **Q&A with citations** — point to exact page and bounding box
- **Self-hosted** — no vendor lock-in, no per-seat cloud fees

---

## Tier 2 — Knowledge Platform

> *Beats: Advanced ECM with basic AI features*

### What This Adds (On Top of Tier 1)
- Hi-RAG v2 hybrid retrieval: vectors (Qdrant) + graph (Neo4j) + full-text (Meilisearch)
- Cross-encoder reranking for precision
- Neo4j knowledge graph for compliance relationship traversal
- TensorZero LLM gateway: route to Claude, Qwen, Ollama, or any provider
- Supabase multi-tenant persistence with Row-Level Security
- Intelligent summarization with multiple LLM providers

### Services

| Service | Port | Role |
|---------|------|------|
| Hi-RAG v2 | 8086/8087 | Hybrid retrieval gateway (CPU/GPU) |
| TensorZero | 3030 | LLM routing + ClickHouse observability |
| Supabase | 8000 | PostgreSQL + Auth + RLS |
| Neo4j | 7474/7687 | Knowledge graph |
| Qdrant | 6333 | Vector embeddings |
| Meilisearch | 7700 | Full-text search |

### Why It Beats Synaptic at Tier 2
- **Triple-store retrieval** (vector + graph + full-text) vs single-index
- **Knowledge graph** maps regulatory relationships, compliance chains
- **Multi-provider LLM** — not locked to one AI vendor
- **Row-Level Security** — per-department, per-role data isolation

---

## Tier 3 — Secure Execution & Compliance

> *Beats: Compliance-focused vendors and audit requirements*

### What This Adds (On Top of Tier 2)
- E2B self-hosted Firecracker microVM sandboxes for safe code execution
- CHIT (Cymatic-Holographic Information Transfer) attribution for provenance
- Graphiti trail for agent action audit logging
- JWT fail-closed authentication (no default-open modes)
- NATS authenticated message bus (event-driven architecture)
- Prometheus + Grafana + Loki observability stack
- TensorZero ClickHouse for LLM usage metrics and cost tracking

### Services

| Service | Port | Role |
|---------|------|------|
| E2B MCP Server | 7073 | Agent → sandbox bridge |
| E2B Sandbox | 7070 | Firecracker microVM execution |
| E2B Desktop | 6080 | NoVNC virtual desktop |
| Prometheus | 9090 | Metrics collection |
| Grafana | 3002 | Dashboard visualization |
| Loki | 3100 | Centralized log aggregation |
| NATS | 4222 | Authenticated event bus |

### Why It Beats Synaptic at Tier 3
- **Hardware-isolated code execution** — Firecracker VMs, not containers
- **Cryptographic audit trail** — CHIT HMAC-signed provenance chain
- **Full observability** — every LLM call, every document access, every agent action logged
- **Self-hosted everything** — no data leaves UNFCU infrastructure
- **NATS event bus** — every document lifecycle event tracked and replayable

---

## Tier 4 — Autonomous Operations (The Royal Flush)

> *Beats: Nothing on the market. Category-defining.*

### What This Adds (On Top of Tier 3)
- Agent Zero MCP orchestration — autonomous multi-agent task execution
- SupaSerch multimodal holographic deep research
- DeepResearch LLM-based research planner (async NATS worker)
- EvoSwarm evolutionary optimization for document classification
- Consciousness Service — CGP topology mapping via Geometry Bus
- Flute Gateway — voice interface for accessibility (prosodic synthesis)
- 100+ MCP tools via BoTZ skills marketplace

### Services

| Service | Port | Role |
|---------|------|------|
| Agent Zero | 8080/8081 | Orchestration + UI |
| Archon | 8091/3737 | Agent service + UI |
| SupaSerch | 8099 | Multimodal research |
| DeepResearch | 8098 | LLM research planner |
| EvoSwarm | 8113 | Evolutionary optimization |
| Consciousness | 8105 | CGP consciousness mapping |
| Flute Gateway | 8055/8056 | Voice synthesis |
| BoTZ Gateway | 8054 | Skills marketplace |
| Gateway Agent | 8100 | MCP tool routing |

### Why Tier 4 Is the Royal Flush
- **No ECM vendor offers autonomous agents** — UNFCU operations run themselves
- **Multi-agent research** — ask a question, get a comprehensive report from multiple sources
- **Voice interface** — accessibility for all UNFCU staff globally
- **Evolutionary optimization** — system improves its own classification and retrieval
- **Geometric intelligence** — visualize document relationships in hyperbolic space

---

## Competitive Comparison Matrix

| Capability | Synaptic (Est.) | UNFCU DoX Tier |
|-----------|-----------------|---------------|
| Document storage | Basic file system | Tier 1 — MinIO + Supabase + structured extraction |
| Search | Keyword | Tier 1 — Vector search with FAISS |
| AI summarization | None/basic | Tier 2 — Multi-provider LLM via TensorZero |
| Knowledge graph | None | Tier 2 — Neo4j relationship traversal |
| Hybrid retrieval | None | Tier 2 — Hi-RAG v2 (vector + graph + full-text) |
| Compliance audit | Manual logs | Tier 3 — CHIT attribution + Graphiti + Loki |
| Secure execution | None | Tier 3 — Firecracker microVM sandboxes |
| Real-time events | Polling | Tier 3 — NATS WebSocket streaming |
| Full observability | None | Tier 3 — Prometheus + Grafana + ClickHouse |
| Agent orchestration | None | Tier 4 — Agent Zero + 100+ MCP tools |
| Voice interface | None | Tier 4 — Flute Gateway prosodic synthesis |
| Self-improving AI | None | Tier 4 — EvoSwarm evolutionary optimization |
| Deployment freedom | Vendor cloud | All tiers — Self-hosted on any infrastructure |

---

## Branding Spec

| Component | PMOVES-DoX | UNFCU DoX |
|-----------|-----------|-----------|
| Primary color | `hsl(263, 70%, 50%)` purple | UNFCU blue (from brand guide) |
| Sidebar logo | "P" + "PMOVES-DoX" | UNFCU shield + "Document Intelligence" |
| Page title | "PMOVES-DoX" | "UNFCU Document Intelligence" |
| Backend prefix | `[PMOVES-DoX]` | `[UNFCU-DoX]` |
| Docker images | `pmoves-dox-*` | `unfcu/dox-*` |
| Repo | `POWERFULMOVES/PMOVES-DoX` | Private `UNFCU-DoX` |

### Files to Customize
1. `frontend/app/globals.css` — HSL color variables
2. `frontend/app/layout.tsx` — Title, metadata, OG images
3. `frontend/components/Sidebar.tsx` — Logo + branding text
4. `frontend/public/` — Favicon, icons, grid pattern
5. `backend/app/main.py` — FastAPI title, log prefix
6. `docker-compose.yml` — Image names, env defaults

---

## Implementation Phases

### Phase 1 — This Week (Docs)
- [x] TAC_UNFCU_DOX.md (this file)
- [ ] TAC_UNFCU_DOX_ARCHITECTURE.md (service diagrams)
- [x] Merge PR #964 (umbrella TACs)

### Phase 2 — Next Week (Fork + Tier 1)
- [ ] Create private repo `UNFCU-DoX`
- [ ] Apply UNFCU branding (CSS, logo, metadata)
- [ ] Standalone Tier 1 deployment
- [ ] Demo: upload → search → Q&A with citations

### Phase 3 — Week 3 (Tier 2-3 Integration)
- [ ] Wire Hi-RAG v2, TensorZero, Supabase, Neo4j
- [ ] Configure E2B, CHIT, observability
- [ ] Build presentation materials from TAC docs

### Phase 4 — Presentation
- [ ] Live demo at each tier
- [ ] Competitive comparison walkthrough
- [ ] Royal flush: Tier 4 autonomous operations

---

## Verification

```bash
# Tier 1 (standalone DoX)
curl -s http://localhost:8484/healthz
curl -X POST http://localhost:8484/documents/upload -F "file=@sample.pdf"
curl -s http://localhost:8484/search?q=compliance

# Tier 2 (knowledge platform)
curl -X POST http://localhost:8086/hirag/query -d '{"query":"regulatory requirement","top_k":10}'
curl -s http://localhost:3030/v1/chat/completions -d '{"model":"claude-sonnet-4-5","messages":[{"role":"user","content":"Summarize this document"}]}'

# Tier 3 (secure execution)
curl -s http://localhost:7073/healthz  # E2B MCP
curl -s http://localhost:9090/api/v1/query?query=up  # Prometheus

# Tier 4 (autonomous)
curl -s http://localhost:8080/healthz  # Agent Zero
```
