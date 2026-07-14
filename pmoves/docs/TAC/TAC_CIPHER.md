# TAC Tree: Cipher Memory

> **STATUS: A1-Shim APPROVED by DARKXSIDE 2026-07-13** — REST compat layer on new ByteRover upstream.
> See [§Decision Matrix](#decision-matrix--path-selection) for the full path comparison + [§A1-Shim Workorder](#a1-shim-workorder) for execution phases.
> **Last refreshed:** 2026-07-13 (CRUSH-GLM52, upstream re-fork research — 4-agent fan-out + operator decision).

## Service Identity

| Field | Value |
|-------|-------|
| **Service** | Cipher Memory (a.k.a. `cipher-api`) |
| **Current gitlink** | `1c9b2851` on `Pmoves-cipher` fork `main` |
| **Fleet rule status** | ⚠️ **VIOLATION** — `.gitmodules` tracks `branch = main`, should track `PMOVES.AI-Edition-Hardened` |
| **Host port** | `8105` (host-published from container `:3000`) |
| **Container port** | `3000` (internal listener) |
| **Health** | `GET /health` (NOT `/healthz`) |
| **Metrics** | None |
| **Submodule** | `Pmoves-cipher` (fork of `campfirein/byterover-cli`, formerly `campfirein/cipher`) |
| **MCP Bridge** | `pmoves-cipher-mcp/` — ⚠️ **DISABLED dead code** since 2026-05-15 (`.claude/mcp.json:12`) |
| **Docker Profile** | `agents` (as `cipher-api`) |
| **Tier** | data |
| **Class** | Specialized |
| **Evolution** | Base |

## ⚠️ Architectural Fork — PMOVES vs Upstream

The PMOVES fork of `campfirein/byterover-cli` (formerly "Cipher") is **798 commits ahead / 3097 commits behind** upstream `main`. The "ahead" commits are stale upstream code from before the rewrite, NOT PMOVES work. Only **6 commits on fork `main`** + **2 parallel on `PMOVES.AI-Edition-Hardened`** are genuine PMOVES additions.

Upstream rewrote the architecture from vector+graph retrieval to BM25+files. This is a **product decision**, not a sync task.

| Dimension | PMOVES Fork (current, `@byterover/cipher` v0.3.0) | Upstream (`byterover-cli` v3.16.1, "formerly Cipher") |
|-----------|---------------------------------------------------|-------------------------------------------------------|
| **Package** | `@byterover/cipher` | `byterover-cli` (binary `brv`) |
| **Storage** | Qdrant + Neo4j + 6 other vector stores | **Filesystem only** — no DBs, no external infra |
| **Retrieval** | Embedding similarity (semantic) | **BM25 full-text (MiniSearch)** — no embeddings |
| **Knowledge structure** | Flat memories with category enum | **Context Tree** — `Domain > Topic > Subtopic > Entry` markdown hierarchy |
| **HTTP API** | Express REST (`/api/memory`, `/api/sessions`, `/mcp/sse`) | **NONE** — Socket.IO daemon + stdio MCP only |
| **MCP tools** | `pmoves_cipher_*` (4 tools) + native `cipher_*` (6+) | **2 tools**: `brv-query` (BM25 search), `brv-curate` (structured HTML write) |
| **Reasoning traces** | First-class (`store_reasoning_memory`) | **Removed** — folded into `<bv-reason>` element inside topics |
| **Auth** | Bearer middleware (PMOVES-added) | OAuth + API key for ByteRover cloud sync (not REST middleware) |
| **Docker** | PMOVES Dockerfile + compose stanza | **No Dockerfile** — local CLI + daemon only |
| **Categories** | Enum: `code_pattern`/`decision`/`context`/`submodule`/`architecture`/`reasoning` | **Path-based**: `domain/topic/file.md` (no category enum) |
| **Embedding providers** | OpenAI/Gemini/Qwen/Voyage/Bedrock/Ollama/LMStudio/Azure (8) | **None** — embeddings eliminated by design |
| **Scale model** | Vector DB scales horizontally | MiniSearch in-memory, ~10K entries (sharding needed beyond) |

**Upstream's thesis** (from `paper/main.tex`): *"no vector database, no graph database, no embedding service."* The bet is that LLM-curation + BM25 beats embedding pipelines. Benchmarks: LoCoMo 92.8%, LongMemEval-S 92.8%.

**PMOVES's thesis** (from `AGNOTE4482_SITREP.md:138-148`, Marco/Polo pattern): *"store with one phrasing, search with another… the embedding model bridges the gap across phrasings."* Semantic similarity across phrasings is a stated core capability.

These are **incompatible theses**. The re-fork decision is which thesis PMOVES adopts going forward.

## Current State (Ground Truth — what actually ships today)

Verified 2026-07-13 against live gitlink `1c9b2851`:

### What works
- **Native MCP-over-SSE** at `:8105/mcp/sse` — Claude Code connects directly (`.claude/mcp.json:4-7`)
- **Native MCP-over-HTTP** at `:8105/mcp` (POST)
- **REST `/api/memory` CRUD** — 4 routes (POST, GET/search, GET/:id, DELETE) added by PR #5 (B850-CLAUDE, 2026-07-01), backed by `agent.services.vectorStoreManager` with in-memory auto-fallback
- **Bearer auth** via `CIPHER_API_TOKEN` (graceful skip if unset = dev mode)
- **Health** at `GET /health`
- **Agent Zero** connects via SSE in dockerized stack (`docker-compose.yml:2618`)

### What is dead / broken
- **Python MCP bridge (`pmoves-cipher-mcp`)** — DISABLED since 2026-05-15. `.claude/mcp.json:12` marks it `_pmoves-cipher-legacy-python-wrapper` with `_disabled` note. Superseded by direct SSE.
- **Bridge NATS events** — `cipher.memory.stored.v1`, `cipher.memory.searched.v1`, `cipher.reasoning.stored.v1` are declared in `agent_registry.yaml:1002-1004`, registered in `pmoves/services/graphiti/nats_subject_registry.py:172-176` (status `defined_only`), referenced in TAC trees + topology docs. BoTZ publishes/consumes the parallel `botz.cipher.memory.stored.v1`. No live Python `subscribe()` call found, but **the contract is live infrastructure** — declared subjects other services build on. **Must be preserved under any path.**
- **Bridge service discovery** — `pmoves_announcer` publishes to `services.announce.v1`, which has a **LIVE subscriber**: `ServiceAnnouncementListener` at `pmoves/services/common/nats_service_listener.py:130` (queue group `service-listeners`). This IS the PMOVES dynamic service discovery mesh — the bridge announcing itself is how other services resolve its URL at runtime. **Must be preserved under any path.**
- **`gateway-agent` `/skills/store` + `/skills/search` calls** (`app.py:621,642`) — already 404 (no such routes in cipher-api source).
- **Stale vendored copies** at 4 mirror sites (predate PR #5, lack `/api/memory` routes, mislead agents):
  - `PMOVES-BoTZ/features/cipher/pmoves_cipher/`
  - `PMOVES-Archon/external/PMOVES-BoTZ/features/cipher/pmoves_cipher/`
  - `pmoves/integrations/archon/external/PMOVES-BoTZ/features/cipher/pmoves_cipher/` (×2 variants)

### Fleet rule violations
1. `Pmoves-cipher` gitlink tracks `branch = main` — should track `PMOVES.AI-Edition-Hardened` (only fork in the audited set that violates this).
2. `PMOVES.AI-Edition-Hardened` branch on fork has only 2 commits vs main's 6 — parallel re-implementations, not a proper hardening overlay.
3. GitHub reports **278 vulnerabilities (9 critical)** on the old fork default branch — all closed by a clean re-fork.

## PMOVES Memory Topology (all 5 surfaces)

Cipher is ONE of FIVE memory surfaces in PMOVES. Agents and docs routinely conflate them. This map is canonical.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         AGENT LAYER                                      │
│                                                                         │
│  Claude Code ──SSE MCP──► Cipher :8105        (episodic memory)         │
│  Agent Zero  ──SSE MCP──► Cipher :3000 (intra-network)                  │
│  Any agent   ──REST─────► Cipher :8105/api/memory                        │
│                                                                         │
│  Any agent   ──REST─────► Hi-RAG v2 :8086/8087 (document RAG + rerank)   │
│  Any agent   ──MCP stdio► Hi-RAG via pmoves-hirag-mcp                    │
│                                                                         │
│  Semantic-cache ──REST──► Cipher :8105 (Layer 0 pre-check, fail-open)    │
│                ──REST──► pgvector (Layer 1, Postgres)                    │
│                                                                         │
│  Any agent   ──REST─────► Open Notebook :5055 (document KB, SurrealDB)   │
│                                                                         │
│  DoX app    ──internal──► DoX CipherService :8096 (team memory, in-mem)  │
└─────────────────────────────────────────────────────────────────────────┘
```

| Surface | Port | Backend | Purpose | Overlap with Cipher? |
|---------|------|---------|---------|---------------------|
| **Cipher Memory** | 8105 | Neo4j (graph) + Qdrant (vectors) + in-mem fallback | Agent episodic memory, checkpoint/resume | — (this IS Cipher) |
| **Hi-RAG Gateway v2** | 8086/8087 | Qdrant + Neo4j + Meilisearch + cross-encoder | Document/corpus retrieval with reranking | Shares Neo4j instance, different graph domain. Intentionally separate (`HERMES_CIPHER_LOCAL_ARCHITECTURE.md:115`) |
| **Semantic-cache** | (via Cipher) | pgvector (Postgres) | LLM response cache; Layer 0 = Cipher pre-check | **Depends on Cipher** — Layer 0 hits Cipher REST, fail-open to pgvector |
| **Open Notebook** | 5055 | SurrealDB | External document/note KB | Independent. Consumed by DeepResearch, Channel Monitor, Agent Zero, UI |
| **DoX CipherService** | 8096 | In-memory dicts + DoX DB adapter | Team/workspace memory for DoX app | **Namesake only** — separate impl, separate port, NOT the Cipher API |

**Consolidation opportunity:** Cipher's Qdrant usage (semantic search over memories) overlaps functionally with Hi-RAG's Qdrant backend. A post-decision Cipher could delegate embedding storage to Hi-RAG rather than maintaining its own vector index.

## Decision Matrix — Path Selection

Three paths emerged from the 2026-07-13 research fan-out (4 agents: upstream arch, PMOVES topology, usage analysis, video/paper). **No path is committed.** This TAC is the decision document.

### Path A1-Shim — REST compatibility layer on new ByteRover (RECOMMENDED DEFAULT)

Re-fork from upstream `main`. Add a thin PMOVES REST shim (`/api/memory`, `/api/memory/search`, `/health`, `/mcp/sse`) that translates to ByteRover's internal memory manager or `brv-query`/`brv-curate`. Keep PMOVES's embedding layer as a sidecar for semantic search. Agents see zero config change.

| Aspect | Detail |
|--------|--------|
| **Upstream absorption** | ✅ All 3097 commits + 278 vuln fixes |
| **Agent config change** | None — SSE/REST contracts preserved |
| **REST callers broken** | 0 (semantic-cache, analyze_beats, gateway-agent all keep working) |
| **MCP callers broken** | 0 (Claude Code, Agent Zero keep SSE endpoints) |
| **Embedding/semantic search** | ✅ Preserved via PMOVES sidecar |
| **NATS events** | Optional re-wire (currently dead anyway) |
| **Bridge fate** | Stays disabled (already dead); delete in follow-up |
| **Effort** | Medium — shim layer + embedding sidecar + re-implement 6 PMOVES features against new arch |
| **Reversible?** | ✅ Yes — shim can be removed later if A3-Full becomes attractive |
| **Risk** | Lowest — no agent config churn, no capability loss |

### Path A1-Fork — Keep PMOVES architecture, abandon upstream sync

Don't re-fork. Keep PMOVES's current vector+graph+REST+Bearer architecture. Cherry-pick upstream security fixes only. Document the permanent divergence. Accept that PMOVES maintains its own memory stack indefinitely.

| Aspect | Detail |
|--------|--------|
| **Upstream absorption** | ❌ Security fixes only (manual cherry-pick) |
| **Agent config change** | None |
| **REST callers broken** | 0 |
| **MCP callers broken** | 0 |
| **Embedding/semantic search** | ✅ Preserved (current Qdrant+Neo4j) |
| **Effort** | Low now, high ongoing ( perpetual manual security backports) |
| **Reversible?** | ✅ A1-Shim or A3-Full remain options later |
| **Risk** | Drift compounds. 278 vulns (9 critical) stay until manually fixed. |
| **When to choose** | If PMOVES concludes ByteRover's BM25-only architecture is fundamentally wrong for multi-agent semantic recall. |

### Path A3-Full — Adopt ByteRover wholesale

Adopt upstream architecture completely. Migrate MCP callers from `pmoves_cipher_*` to `brv-query`/`brv-curate`. Accept BM25-only retrieval (no embeddings). Kill the bridge, semantic-cache Layer 0, analyze_beats checkpoints. Remap PMOVES categories to domain/topic paths.

| Aspect | Detail |
|--------|--------|
| **Upstream absorption** | ✅ Complete — zero divergence going forward |
| **Agent config change** | `.claude/mcp.json` SSE→stdio; Agent Zero compose SSE→stdio (×2 files) |
| **REST callers broken** | 5 (semantic-cache Layer 0, analyze_beats ×2, gateway-agent ×2 already broken) |
| **MCP callers broken** | 3 (all rename tools `pmoves_cipher_*` → `brv_*`) |
| **Embedding/semantic search** | ❌ **LOST** — BM25 lexical only. Marco/Polo phrasing-bridge breaks. |
| **Reasoning traces** | ❌ **LOST** as first-class — folded into `<bv-reason>` element |
| **Categories** | Remap `code_pattern`/`decision`/etc. → `domain/topic/` paths |
| **Effort** | High — every skill/doc/agent that references cipher tools needs rewrite |
| **Reversible?** | ⚠️ Difficult — data migration to Context Tree is one-way |
| **Risk** | Highest — loses semantic recall (a stated PMOVES core capability), forces fleet-wide config churn |
| **When to choose** | If PMOVES agrees with ByteRover's thesis that LLM-curation + BM25 beats embeddings for multi-agent memory. |

### Path A2 — Rewrite bridge for native MCP (ELIMINATED)

Rewrite `pmoves-cipher-mcp/client.py` to call ByteRover's `brv-query`/`brv-curate` over stdio.

**Eliminated because the bridge is already disabled dead code.** Claude Code bypasses it (direct SSE since 2026-05-15). REST callers don't go through it. Rewriting dead code helps no one.

### Comparison summary

| Criterion | A1-Shim | A1-Fork | A3-Full |
|-----------|---------|---------|---------|
| Upstream sync | ✅ Full | ❌ Security only | ✅ Full |
| Agent config churn | None | None | High (fleet-wide) |
| REST callers preserved | ✅ All | ✅ All | ❌ 5 broken |
| Semantic search preserved | ✅ Sidecar | ✅ Current stack | ❌ BM25 only |
| Effort | Medium | Low now / high ongoing | High |
| Reversibility | ✅ | ✅ | ⚠️ One-way data migration |
| Vuln closure (278/9 crit) | ✅ | ❌ Manual | ✅ |

### Operator-pending input

Two YouTube videos flagged by DARKXSIDE as relevant to the decision:
- `https://www.youtube.com/watch?v=T33iI6izAKw`
- `https://www.youtube.com/watch?v=R-5_2nsF_ZM`

These likely contain the ByteRover team's pitch for the BM25 + LLM-curation thesis. **Decision deferred until operator reviews these** and confirms whether PMOVES's multi-agent use case is better served by semantic embeddings (A1-Shim/A1-Fork) or BM25 (A3-Full).

## Upstream Architecture Reference (ByteRover v3.16.1)

For context once a path is chosen. Sources: `paper/main.tex`, `src/server/infra/mcp/`, `src/agent/infra/memory/`.

### Memory data model (upstream)
- **`Memory` type** (`src/agent/core/domain/memory/types.ts`): flat JSON blob with `content`, `tags: string[]`, `metadata`, `id` (nanoid 12). NO category enum.
- **`MemoryManager`** (`src/agent/infra/memory/memory-manager.ts`): CRUD over `BlobStorage` (file-based). Keys: `memory-{id}`.
- **Context Tree** (the PRIMARY knowledge system): markdown/HTML files organized `Domain > Topic > Subtopic > Entry`. Edges = `@domain/topic/file.md` cross-references. This is what `brv-query`/`brv-curate` operate on.

### Storage backends (upstream)
- **Filesystem only** — `FileBlobStorage` (`src/agent/infra/blob/file-blob-storage.ts`). Blobs as individual files: `{storageDir}/blobs/{key}/content.bin` + `metadata.json`.
- **No vector stores. No graph DBs. No SQLite.** All removed in the rewrite.
- **Search engine**: MiniSearch v7 (in-memory BM25), field boosting (title 5×, path 1.5×), fuzzy 0.2, prefix search.

### Embedding providers (upstream)
- **NONE.** Embeddings deliberately eliminated. Paper §: *"no embedding service."*
- LLM providers (chat/completion, not embeddings): 20+ including Ollama via `openai-compatible` (`src/agent/infra/llm/providers/openai-compatible.ts`).

### MCP tools (upstream — exactly 2)
| Tool | Input | Output | Backend |
|------|-------|--------|---------|
| `brv-query` | `{query, limit?, cwd?}` | `{matchedDocs, metadata, status}` | 5-tier progressive retrieval: cache → BM25 → single LLM call → agentic loop |
| `brv-curate` | `{html (bv-topic), meta?, cwd?}` | write confirmation | HTML validation + atomic file write |

Comparison to PMOVES tools:
| PMOVES tool | ByteRover equivalent | Gap |
|-------------|---------------------|-----|
| `pmoves_cipher_store` | `brv-curate` | brv-curate takes structured HTML, not freeform content+category |
| `pmoves_cipher_search` | `brv-query` | brv-query is BM25 only (no vector/semantic) |
| `pmoves_cipher_store_reasoning` | **NONE** | No reasoning-trace storage; folded into `<bv-reason>` element |
| `pmoves_cipher_reasoning_patterns` | **NONE** | No reasoning pattern search |

### HTTP API surface (upstream)
- **NONE.** No REST routes. Socket.IO daemon + stdio MCP only.
- Daemon selects **random port** in range 49152-65535 (`src/server/infra/daemon/brv-server.ts`).
- Express server exists but serves the static WebUI SPA, not a REST API.

### Auth model (upstream)
- OAuth 2.0 PKCE + API key for **ByteRover cloud provider** (multi-device sync).
- NO Bearer-token middleware (no REST surface to protect).
- Daemon trusts localhost Socket.IO connections.
- `brv login` (interactive) or `brv login --api-key` (headless/CI).

### Config / deployment (upstream)
- Local CLI tool (`brv`) + daemon process. No Dockerfile.
- Daemon: logging, random port, instance lock, Socket.IO + Express WebUI, heartbeat.
- PMOVES would need to author its own Dockerfile + compose stanza if containerizing.

### Migration guidance (upstream)
- **NONE.** No Cipher→ByteRover migration docs in repo.
- `migrate-handler.ts` exists but is for Context Tree format versioning, not Cipher migration.
- `brv-curate` schema is `.strict()` — rejects legacy `{context, files, folder}` shape.

## Current Key Endpoints (subject to decision above)

| Endpoint | Method | Description | Status |
|----------|--------|-------------|--------|
| `/health` | GET | Health check | ✅ Live |
| `/api/memory` | POST | Store a memory (PR #5) | ✅ Live (PMOVES-added) |
| `/api/memory/search` | GET | Semantic search `?q=...` (PR #5) | ✅ Live (PMOVES-added) |
| `/api/memory/:id` | GET, DELETE | CRUD by ID (PR #5) | ✅ Live (PMOVES-added) |
| `/mcp/sse` | GET (SSE) | Native MCP-over-SSE | ✅ Live (primary agent path) |
| `/mcp` | POST | Native MCP-over-HTTP | ✅ Live |
| `/api/sessions/*` | CRUD | Session management | ✅ Live (upstream) |
| `/api/search` | GET | Agent search | ✅ Live (upstream) |
| `/api/message` | POST | Agent messaging | ✅ Live (upstream) |
| `/skills/store`, `/skills/search` | — | Skill pattern store/search | ❌ **Does not exist** — gateway-agent calls 404 |

## MCP Tools (current — subject to decision above)

### Via native SSE (`.claude/mcp.json` — what Claude Code actually uses)
Cipher's native MCP server exposes tools over `/mcp/sse`. Tool names surface as `cipher_*` (upstream-defined).

### Via disabled Python bridge (DEAD — do not use)
| Tool | Description | Status |
|------|-------------|--------|
| `pmoves_cipher_store` | Store knowledge with category and tags | ❌ Bridge disabled |
| `pmoves_cipher_search` | Semantic search over stored memories | ❌ Bridge disabled |
| `pmoves_cipher_store_reasoning` | Store chain-of-thought reasoning traces | ❌ Bridge disabled |
| `pmoves_cipher_reasoning_patterns` | Search past reasoning for similar problems | ❌ Bridge disabled |

**Note:** These 4 tool names are referenced in skills (`pmoves-cipher-memory/SKILL.md`), agent definitions (`memory-agent.md`), commands (`cipher/store.md`, etc.), and the semantic-cache spec. All have documented `MEMORY.md` fallbacks — Cipher is a **soft dependency** across the agent layer.

## Memory Categories (current)

### Knowledge categories
`code_pattern` · `decision` · `context` · `submodule` · `architecture` · `reasoning`

### Agent resilience categories
`agent_plan` · `agent_checkpoint` · `agent_completion`

**Under A3-Full:** these remap to Context Tree paths (e.g., `decisions/`, `patterns/`, `architecture/`). No 1:1 mapping exists for `submodule` or `reasoning`.

## NATS Subjects (live infrastructure — preserve under any path)

These subjects are declared across registries, TAC trees, topology docs, and BoTZ parallel publishers (`botz.cipher.memory.stored.v1`). The bridge publishing them is currently disabled, but the **contract is live** — declared subjects other services and downstream consumers build on. **A1-Shim preserves these by re-emitting from the new REST shim.**

| Subject | Direction | Publisher | Declared consumers |
|---------|-----------|-----------|-------------------|
| `cipher.memory.stored.v1` | Publishes | Bridge (currently disabled) | `agent_registry.yaml:1002`, `nats_subject_registry.py:172`, TAC trees, BoTZ parallel subject |
| `cipher.memory.searched.v1` | Publishes | Bridge (currently disabled) | `agent_registry.yaml:1003`, `nats_subject_registry.py:174`, TAC trees |
| `cipher.reasoning.stored.v1` | Publishes | Bridge (currently disabled) | `agent_registry.yaml:1004`, `nats_subject_registry.py:176`, TAC trees |
| `services.announce.v1` | Publishes | Bridge `pmoves_announcer` | **LIVE subscriber**: `ServiceAnnouncementListener` (`nats_service_listener.py:130`, queue `service-listeners`) → updates `service_registry.py` cache |

## Downstream Consumers (actual usage, verified 2026-07-13)

| Consumer | Interface | Operation | Criticality | Breaks if REST disappears? |
|----------|-----------|-----------|-------------|----------------------------|
| **Claude Code** | SSE MCP `/mcp/sse` | All memory ops | High (primary agent memory) | No (uses MCP, not REST) |
| **Agent Zero** (dockerized) | SSE MCP `cipher-api:3000/mcp/sse` | All memory ops | High | No (uses MCP) |
| **Semantic-cache** | REST `/api/memory/search` | Layer 0 pre-check | Medium (fail-open to pgvector) | ✅ Yes — degrades, no crash |
| **Semantic-cache** | REST `/api/memory` | Store cache miss | Low (fire-and-forget) | ✅ Yes — silent loss |
| **analyze_beats.py** | REST `/api/memory` | Checkpoint store | Low (fire-and-forget) | ✅ Yes — silent loss |
| **analyze_beats.py** | REST `/api/memory/search` | Prior checkpoint retrieve | Low (display only) | ✅ Yes — silent loss |
| **gateway-agent** | REST `/skills/store`, `/skills/search` | Skill patterns | **Already 404** | Already broken |
| **gateway-agent** | REST `/health` | Health probe | Low | ✅ Yes |
| **spark_health.py** | REST `/health` | Optional probe | No | ✅ Yes |
| **hirag-mcp** | REST `/health` | Health sweep | No | ✅ Yes |
| **showtime-api** | REST `/health` | Health probe | No | ✅ Yes |

**Room manifests** referencing Cipher: `z890-infra`, `fordham.community`, `hermes-agent.control`, `4090-field.control`, `demo`, `5090-kilocode.studio`. Most reference via `service_refs`; actual skill bindings are mostly `planned`/`enabled: false`. Only Fordham's `durable-memory` binding is live.

## Security Stance

| Finding | Severity | Status |
|---------|----------|--------|
| 278 vulnerabilities (9 critical) on fork default branch | **CRITICAL** | Open — closed by re-fork (A1-Shim or A3-Full) |
| No API authentication (upstream base) | P2 | **Fixed** — Bearer token via `CIPHER_API_TOKEN` (PMOVES-added, PR #1) |
| A2A discovery endpoint unauthenticated | P1 | **Fixed** — auth-gated (PR #1) |
| `CIPHER_URL` host/container port mismatch | P1 | **Open** — in-network services use `:8105` but container listens on `:3000` |
| `pmoves-cipher-mcp/` not a proper submodule | P2 | Open (low priority — bridge is dead code) |
| `.gitmodules` tracks `main` not `PMOVES.AI-Edition-Hardened` | P1 | **Open** — fleet rule violation |

## PMOVES Additive Commits (the keep-list)

These 6 commits on fork `main` (+ 2 parallel on hardened) are genuine PMOVES work. Under A1-Shim/A3-Full they must be re-implemented against the new architecture. Under A1-Fork they stay as-is.

### On fork `main` (6 commits)
```
c2d4d50f docs(pmoves): add PMOVES.AI integration dossier
873abb1b fix(security): auth-gate cipher A2A discovery endpoint (#1)
ed701cae feat(auth): add Bearer token authentication middleware
c4f8348f feat(cipher): switch to Ollama backend + update MCP capabilities (#3)
b4a780b0 feat(api): add /api/memory CRUD routes for pmoves-cipher-mcp bridge (#5)
1c9b2851 fix(build): official node-gyp disturl + pnpm 9 workspace packages (#6)
```

### On fork `PMOVES.AI-Edition-Hardened` (2 commits — parallel re-implementations)
```
17fef8c1 docs: add PMOVES.AI integration dossier
2bd33b9d fix(a2a): add canonical agent-card endpoint and tighten discovery auth (#2)
```

### Archive branches (preserved 2026-07-13)
- `archive/cipher-pre-refork-2026-07-13-main` — old fork main (798 ahead of old upstream)
- `archive/cipher-pre-refork-2026-07-13-hardened` — old PMOVES.AI-Edition-Hardened

## Open Items

### Decision-pending (BLOCKING)
- [ ] **Operator reviews YouTube videos** (`T33iI6izAKw`, `R-5_2nsF_ZM`) — ByteRover thesis pitch
- [ ] **Operator selects path**: A1-Shim / A1-Fork / A3-Full
- [ ] **This TAC signed off** by operator as the canonical decision record

### Post-decision (any path)
- [ ] Remove stale vendored cipher copies (4 mirror sites)
- [ ] Reconcile `TAC_CIPHER.md`, `CATALOG.md`, `AGNOTE4482_SITREP.md`, `pmoves-cipher-mcp/README.md` to single source of truth
- [ ] Fix `CIPHER_URL` host/container port mismatch in compose (3 files: `docker-compose.yml`, `docker-compose.agents.yml`, `docker-compose.vps.override.yml`)
- [ ] Remove or rewire dead NATS subjects (`cipher.memory.*.v1`) — zero subscribers
- [ ] Remove dead gateway-agent `/skills/*` calls (already 404)

### Path-specific (after decision)
- **A1-Shim:** Re-fork from upstream `main`; build REST compat layer (`/api/memory`, `/health`, `/mcp/sse`); re-implement 6 PMOVES features; flip `.gitmodules` to `PMOVES.AI-Edition-Hardened`; promote gitlink; preserve NATS event emission (`cipher.*.v1` + `services.announce.v1`) by re-emitting from the shim or a thin sidecar; delete the disabled Python bridge
- **A1-Fork:** Cherry-pick upstream security fixes; document permanent divergence; fix 278 vulns manually or accept risk
- **A3-Full:** Re-fork from upstream `main`; migrate `.claude/mcp.json` SSE→stdio; migrate Agent Zero compose SSE→stdio; migrate semantic-cache to pgvector-only; remap categories to domain/topic paths; delete Python bridge + `pmoves_cipher_*` tool references fleet-wide

## A1-Shim Workorder

**Approved by DARKXSIDE 2026-07-13.** Multi-session execution. Each phase is independently PR-able.

### Phase 1 — Re-fork from upstream (foundation)
- [ ] Create fresh `PMOVES.AI-Edition-Hardened` on fork from `campfirein/byterover-cli@main`
- [ ] Delete old `main` + `PMOVES.AI-Edition-Hardened` on fork (archive branches already pushed)
- [ ] Flip `.gitmodules` for `Pmoves-cipher`: `branch = main` → `branch = PMOVES.AI-Edition-Hardened`
- [ ] Promote gitlink in PMOVES.AI superproject
- [ ] Verify: `git submodule update --init Pmoves-cipher` succeeds against new branch

### Phase 2 — REST compat shim (the contract preserver)
Build a PMOVES additive overlay that exposes the contracts agents depend on, translating to ByteRover's internal `MemoryManager` + `brv-query`/`brv-curate`. All 8 minimum contracts from the decision matrix MUST be satisfied.

- [ ] `GET /health` — wraps ByteRover daemon health
- [ ] `POST /api/memory` — stores via ByteRover `MemoryManager.create()`, returns raw top-level `{"id": ...}` JSON (NOT envelope — bridge contract)
- [ ] `GET /api/memory/search?q=...&limit=...&category=...` — routes to `brv-query` (BM25) OR PMOVES embedding sidecar (TBD per semantic-search decision below)
- [ ] `GET /api/memory/:id`, `DELETE /api/memory/:id` — CRUD via `MemoryManager`
- [ ] `GET /mcp/sse` + `POST /mcp` — SSE/HTTP MCP surface (either wrap ByteRover's stdio MCP in a bridge, or implement natively on the shim)
- [ ] Bearer auth middleware (`CIPHER_API_TOKEN`, graceful skip if unset = dev mode)

### Phase 3 — NATS event emission (preserve live infrastructure)
- [ ] Emit `cipher.memory.stored.v1` after `POST /api/memory` success
- [ ] Emit `cipher.memory.searched.v1` after `GET /api/memory/search` success
- [ ] Emit `cipher.reasoning.stored.v1` after reasoning store
- [ ] Publish `services.announce.v1` on startup (preserve service discovery contract — `ServiceAnnouncementListener` at `pmoves/services/common/nats_service_listener.py:130` IS listening)

### Phase 4 — Embedding sidecar (DECIDED: keep embeddings, Qdrant sidecar)

**Operator decision 2026-07-13: PMOVES keeps embeddings** (multimodal ingestion depends on them). Sub-decision A selected: Qdrant sidecar.

Research findings (3-agent fan-out 2026-07-13):
- **LongBow is documentation-only** — never integrated. `LONGBOW_INTEGRATION.md` + `LONGBOW_COMPARATIVE_ANALYSIS.md` describe a planned vector DB + learned router, but Qdrant (:6333) is the de facto vector layer today.
- **Primary embedder:** Qwen3-Embedding-4B @ **2560d** via TensorZero `http://tensorzero-gateway:3030/openai/v1/embeddings` (NOT `/v1/embeddings` — 404s). Model payload: `{"model": "tensorzero::embedding_model_name::qwen3_embedding_4b_local"}`.
- **Shared Qdrant, separate collections:** `pmoves_chunks_qwen3` (2560d, Hi-RAG/extract-worker), `pmoves_chunks` (384d legacy). Cipher sidecar uses a NEW collection `pmoves_cipher_memory` (2560d, COSINE) — NOT the Hi-RAG collection (would pollute document recall with conversational memory).
- **Multimodal stays in dedicated services:** CLAP (:8108, 512d audio), CLIP (inline image ranking in Hi-RAG geometry route). Sidecar is text-only.
- **Dimension landmines:** (1) docs sometimes cite 3072d for Qwen3-4B — actual is 2560d; (2) `QDRANT_RECREATE_ON_DIM_MISMATCH=true` defaults in some compose files could destroy collections — pin to `false` for the sidecar.

- [ ] Add embedding sidecar to `src/pmoves/` — on `POST /api/memory`, embed content via TensorZero and store in Qdrant `pmoves_cipher_memory`; on `GET /api/memory/search`, do vector similarity query (with BM25 fallback if TensorZero/Qdrant unreachable)
- [ ] Provision `pmoves_cipher_memory` collection (2560d, COSINE) — follow `pmoves/scripts/provision_qdrant_pmoves_chunks_qwen3.py` pattern
- [ ] Set `QDRANT_RECREATE_ON_DIM_MISMATCH=false` in the cipher-api compose env
- [ ] Document the 2560d contract in TAC + CATALOG (correct any 3072d drift)

### Phase 5 — Re-implement 6 PMOVES features against new arch
Each was originally a cherry-pick candidate; under A1-Shim they become new commits against the new architecture.

| Feature | Old target | New arch integration point | Effort |
|---------|-----------|---------------------------|--------|
| Bearer auth middleware | Express middleware | Shim's own middleware layer | Small |
| A2A discovery auth-gate | `/.well-known/agent-card.json` route | Shim route or ByteRover daemon config | Small |
| Ollama embedding backend | LLM provider registry | **Sub-decision A:** Qdrant sidecar uses Ollama directly. **B:** N/A | Medium / N/A |
| `/api/memory` CRUD routes | Express routes | Shim routes → `MemoryManager` | Medium |
| Build fixes (node-gyp, pnpm) | `package.json` | Likely obsolete on new arch — verify, close if so | Trivial |
| Integration dossier | Doc-only | Refresh against new arch | Trivial |

### Phase 6 — Compose + gitlink promotion
- [ ] Update `docker-compose.yml` cipher-api stanza: build from new fork, expose shim ports
- [ ] Update `docker-compose.agents.yml`, `docker-compose.vps.override.yml`, `docker-compose.cache.yml`
- [ ] Fix `CIPHER_URL` host/container port mismatch (in-network services currently use `:8105`, container listens on `:3000`)
- [ ] Promote gitlink in PMOVES.AI superproject

### Phase 7 — Vendored variant audit + preserve/optimize (NOT delete)

**Correction 2026-07-13:** The 4 sites are NOT stale duplicates. They are the **BoTZ cipher variant** — a legitimate submodule nesting with its own NATS namespace (`botz.cipher.*`), port (8081), config (`cipher_pmoves.yml` with TensorZero+Qwen3), and Python MCP bridge. The operator confirmed these are submodule forks with branch variants that must be preserved.

**Variant map (3-agent research fan-out 2026-07-13):**

| Site | Path | Type | Branch | Status |
|------|------|------|--------|--------|
| 1 | `PMOVES-BoTZ/features/cipher/pmoves_cipher/` | nested submodule | (no branch specified) | UNINITIALIZED (empty) |
| 2 | `PMOVES-Archon/external/PMOVES-BoTZ/.../pmoves_cipher/` | 3-level nested submodule | (inherits BoTZ) | INIT @ `51eea546` (OLD cipher v0.3.0) |
| 3 | `pmoves/integrations/archon/external/PMOVES-BoTZ/.../pmoves_cipher/` | 4-level nested submodule | (inherits Archon→BoTZ) | INIT @ `51eea546` (SAME as Site 2) |
| 4 | `PMOVES-DoX/external/PMOVES-BoTZ/.../pmoves_cipher/` | nested submodule | `PMOVES.AI-Edition-Hardened` (via DoX BoTZ) | UNINITIALIZED (empty) |

**DoX also has a NATIVE Python CipherService** at `PMOVES-DoX/backend/app/services/cipher_service.py` (port 8096, team workspace memory with RLS, in-memory dicts + DoX DB). This is a NAMESAKE — separate impl, NOT the cipher submodule.

**BoTZ NATS namespace (parallel, live):** `botz.cipher.memory.stored.v1`, `botz.cipher.memory.recalled.v1`, `botz.cipher.pattern.detected.v1`, `botz.cipher.reasoning.complete.v1` — intentionally separate from main `cipher.memory.*.v1`.

- [ ] **Preserve all 4 sites** — they are legitimate BoTZ/DoX variants, not stale copies
- [ ] Add `branch = PMOVES.AI-Edition-Hardened` to `PMOVES-BoTZ/.gitmodules` cipher entry (currently no branch specified — defaults to repo default, which is now the re-forked upstream)
- [ ] Diff `pmoves_cipher_backup/` dirs (vendored pre-submodule snapshots at 3 BoTZ sites) against the initialized submodule — confirm no unique patches before deciding whether to delete
- [ ] Investigate Sites 2+3 symlink consolidation (same PMOVES-Archon repo at two superproject paths)
- [ ] Document the BoTZ cipher variant in this TAC as a sub-section (own port, own NATS namespace, own config) so future agents stop conflating it with the main cipher-api
- [ ] Document the DoX dual-cipher surfaces (Node.js submodule :3000 + Python CipherService :8096) explicitly

### Phase 8 — Doc reconcile (single source of truth)
- [ ] `CATALOG.md` cipher block — update routes, ports, transport
- [ ] `AGNOTE4482_SITREP.md` Cipher Marco/Polo section — remove "Layer 2 gap" (it was based on stale vendored copy)
- [ ] `pmoves-cipher-mcp/README.md` — mark bridge as deprecated/disabled, point to shim
- [ ] `.claude/skills/pmoves-cipher-memory/SKILL.md` — update transport refs
- [ ] `nats-subjects.md` — mark cipher.* subjects as shim-emitted (not bridge-emitted)

### Phase 9 — Trail + RELEASE + CHIT cross-reference

**CHIT findings (3-agent research 2026-07-13):**
- CHIT signs CGP geometry bus packets (`geometry.cgp.v1`) and agent Graphiti trail entries — NOT memory stores
- Memory stores are unsigned today; no consumer verifies signatures on cipher memory; no gate would reject unsigned memories
- ByteRover's `Memory` type has NO provenance fields; CHIT on memory would be a purely additive overlay on the NATS event payload (not required for compliance)
- The semantic-cache uses CHIT/NATS for cache invalidation (`cache.invalidate.*` subjects) — NOT for verifying cipher responses
- No signing identity card exists for cipher-memory (24 cards in `signing_identity_cards.yaml`, none for cipher)

**Minimum CHIT integration:** sign the trail entry after delivery. No in-band memory signing required.

- [ ] Sign trail (`make -C pmoves sign-trail AGENT=crush-glm52 SUMMARY=...`) — records agent provenance for shipping the shim
- [ ] RELEASE claim in `AGNOTE4482PHI.t1.md`
- [ ] Update this TAC's STATUS header to "A1-Shim EXECUTED" once Phase 6 lands
- [ ] **Optional future:** if PMOVES wants CHIT-signed memory events, port `sign_cgp()` (HMAC-SHA256 over canonical JSON, ~15 lines of TypeScript `crypto.createHmac`) and add a `sig` block to the NATS event payload. Provision a signing identity card for cipher-memory. NOT required for A1-Shim compliance.



- **Submodule:** `Pmoves-cipher/` (fork of `campfirein/byterover-cli`)
- **Bridge (dead):** `pmoves-cipher-mcp/`
- **Agent Registry:** `pmoves/config/agent_registry.yaml` → `cipher_memory`
- **Agent Zero TAC:** [`TAC_AGENT_ZERO.md`](./TAC_AGENT_ZERO.md) — primary consumer
- **Hi-RAG:** `.claude/CATALOG.md` Hi-RAG section (no TAC_HIRAG exists)
- **Semantic-cache spec:** `docs/specs/issue-1427-semantic-cache-spec.md`
- **MCP Configuration:** `.claude/mcp.json` → `pmoves-cipher` server entry
- **Memory topology:** `pmoves/docs/AGENTS/HERMES_CIPHER_LOCAL_ARCHITECTURE.md`
- **Marco/Polo pattern:** `pmoves/docs/AGENTS/AGNOTE4482_SITREP.md:138-161`
- **Upstream paper:** `campfirein/byterover-cli/paper/main.tex` (ByteRover architecture thesis)
- **Research artifacts:** 4-agent fan-out findings captured 2026-07-13 (this document is the synthesis)

## Research Citations

This TAC revision synthesizes a 4-agent parallel research fan-out executed 2026-07-13 on PMOVES-SPARK (CRUSH-GLM52):

1. **Upstream architecture agent** — ByteRover v3.16.1 memory model, storage, MCP tools, HTTP surface, auth, deployment, migration guidance. Findings: file-only storage, BM25 retrieval, 2 MCP tools, no REST, no embeddings.
2. **PMOVES topology agent** — All 5 memory surfaces mapped, Cipher call sites inventoried, bridge additive value assessed. Findings: bridge NATS events have zero subscribers; DoX CipherService is a namesake not the same system.
3. **Usage analysis agent** — Every Cipher caller classified by transport, criticality, and break-under-path. Findings: bridge disabled since 2026-05-15; only semantic-cache Layer 0 is a hot-path REST caller (fail-open); gateway-agent `/skills/*` already 404.
4. **Video/paper agent** — YouTube videos NOT fetchable (tool limitation); academic paper extracted. Findings: ByteRover thesis is LLM-curation + BM25 beats embeddings; 92.8% on LoCoMo/LongMemEval-S benchmarks.

**Operator-pending:** YouTube videos `T33iI6izAKw` + `R-5_2nsF_ZM` (ByteRover demos/pitch) — not yet reviewed. Decision deferred.

<!-- GRAPHITI_MARK: CLAUDE-OPUS::TAC-DEEP-DIVE::2026-03-15 -->
<!-- GRAPHITI_MARK: CRUSH-GLM52::TAC-CIPHER-REFORK-DECISION-DOC::2026-07-13 -->
