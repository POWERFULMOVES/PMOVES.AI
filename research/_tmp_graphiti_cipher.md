# GRAPHITI TAC Trees & Cipher-MCP Encryption Research

> Generated: 2026-04-17 | Scope: 6 TAC trees + TAC_CIPHER.md + 14 cipher-mcp files

---

## 1. GRAPHITI TAC Trees Catalog

31 total TAC tree files exist in `pmoves/configs/tac_trees/`. Zero files have 'graphiti' in their filename. Six files contain 'graphiti' references in content. All six named trees were found and read in full.

### 1.1 tokenism-chit.tac.yaml

**Path:** `pmoves/configs/tac_trees/tokenism-chit.tac.yaml`
**Name:** ToKenism CHIT Attribution Engine v1.0.0
**Purpose:** Verify ToKenism CGP encoding, simulation pipeline, NATS geometry bus integration, TypeScript module health

**Key Nodes:**
| Node ID | Task | Check Type |
|---------|------|------------|
| `tokenism.submodule.initialized` | Submodule initialized (not shallow) | file_exists: PMOVES-ToKenism-Multi/package.json |
| `tokenism.submodule.chit-contracts` | CHIT contract modules present | file_exists: integrations/contracts/chit/ |
| `tokenism.nats.cgp-subject` | CGP subject publishing | grep: geometry.cgp\|tokenism.cgp |
| `tokenism.nats.simulation` | Simulation result subjects | grep: tokenism.simulation |
| `tokenism.env.no-export` | No export syntax in env files | inverted grep: ^export |
| `tokenism.env.compose` | Docker Compose service defined | grep: tokenism-simulator\|tokenism-ui |
| `tokenism.skills.pairings` | Skill pairing references (3+) | grep in skill-pairings.yaml |
| `tokenism.skills.cgp-schema` | CGP schema version alignment | grep: chit.cgp.v |

**GRAPHITI References:** Skill pairings include `pr-monitor-graphiti-chit`. CGP schema versions: transport=geometry.cgp.v1, payload=chit.cgp.v0.2, canonical=chit.cgp.v1.0.

**NATS Subjects:** `geometry.cgp.v1`, `tokenism.cgp.ready.v1`, `tokenism.simulation.result.v1`

---

### 1.2 training-pipeline.tac.yaml

**Path:** `pmoves/configs/tac_trees/training-pipeline.tac.yaml`
**Name:** TAC_TRAINING_PIPELINE v1.0.0
**Purpose:** Three-phase fine-tuning pipeline (Embeddings/Agentic/Voice) using Unsloth on 5090 GPU

**Key Nodes (3 phases + infrastructure):**

**Phase 1 - Embeddings (Crawl):** `training.embed.data_prep` → `validate` → `train` → `eval` → `publish` → `register` → `deploy`
- Base model: qwen3-embedding:4b (2560d), LoRA rank 16-32, contrastive loss
- Sources include "Agent Graphiti trail entries"

**Phase 2 - Agentic (Walk):** `training.agent.data_prep` → `train` → `eval` → `publish` → `deploy`
- Base: Qwen2.5-7B-Instruct or Llama-3.1-8B-Instruct, QLoRA 4-bit

**Phase 3 - Voice (Run):** `training.voice.data_prep` → `train` → `eval` → `deploy`
- Fish S2 Pro + F5-TTS adaptation

**Infrastructure:** VRAM swap protocol, z890 TTS failover, E2B sandbox eval, NATS lifecycle events

**GRAPHITI References:** Training data sources include "Agent Graphiti trail entries" for embedding fine-tuning. This means Graphiti trail data is used as training corpus for domain-specific retrieval models.

**NATS Subjects (6):** `training.job.started.v1`, `training.job.completed.v1`, `training.job.failed.v1`, `training.eval.result.v1`, `training.model.published.v1`, `training.model.deployed.v1`

**All statuses:** `planned`

---

### 1.3 archon-agents.tac.yaml

**Path:** `pmoves/configs/tac_trees/archon-agents.tac.yaml`
**Name:** Archon Agent Service v1.0.0
**Purpose:** Verify Archon service config, Supabase prompts, Agent Zero MCP integration

**Key Nodes:**
| Node ID | Task | Check |
|---------|------|-------|
| `archon.service.submodule` | Submodule initialized | file_exists: PMOVES-Archon/pyproject.toml |
| `archon.service.compose-defined` | Service in compose | grep: archon: (port 8091/3737) |
| `archon.service.healthcheck` | Health endpoint | grep: archon.*healthz |
| `archon.supabase.url-config` | Supabase URL | grep: SUPABASE_URL |
| `archon.supabase.service-key` | Service role key | grep: SERVICE_ROLE_KEY |
| `archon.mcp.url-config` | MCP service URL | grep: MCP_SERVICE_URL |
| `archon.mcp.client-auth` | MCP credentials | grep: MCP_CLIENT_ID/SECRET |
| `archon.tensorzero.work-orders` | archon_work_orders function | grep in tensorzero.toml |
| `archon.tensorzero.code-review` | archon_code_review function | grep in tensorzero.toml |

**GRAPHITI References:** `archon.tensorzero.code-review` is used in the `pr-monitor-graphiti-chit` skill pairing. Archon executes the `graphiti-trail-sync` step (step 4) in that pairing.

---

### 1.4 skills-taxonomy.tac.yaml

**Path:** `pmoves/configs/tac_trees/skills-taxonomy.tac.yaml`
**Name:** TAC_SKILLS_TAXONOMY v1.0.0
**Purpose:** Complete catalog of 119 skills across 36 domains

**Metadata:** 119 total skills, 36 domains, source: `.claude/commands/`

**GRAPHITI-Relevant Skills:**

| Skill | Command | GRAPHITI Role |
|-------|---------|---------------|
| `skills.chit.review-sweep` | `/chit:review-sweep` | Encode PR learnings as CGP packet for Graphiti (step 3 in pr-monitor-graphiti-chit) |
| `skills.chit.sign-trail` | `/chit:sign-trail` | Sign Graphiti trail entry with CHIT HMAC (step 4) |
| `skills.agent-sdk.handoff` | `/agent-sdk:handoff` | Publishes `agent.graphiti.signed.v1` on handoff |
| `skills.cipher.store` | `/cipher:store` | Stores to Cipher Memory (Neo4j-backed) |
| `skills.cipher.search` | `/cipher:search` | Searches Cipher Memory knowledge graph |
| `skills.cipher.reasoning` | `/cipher:reasoning` | Stores/queries reasoning traces |

**Key Dependency Chain - pr-monitor-graphiti-chit:**
```
Step 1: /pr-monitor (codex) → ops.pr.monitor.completed.v1
Step 2: /pr-trim (claude-opus) → ops.pr.trim.completed.v1
Step 3: /chit:review-sweep (tokenism) → ops.pr.learnings.encoded.v1
Step 4: /chit:sign-trail (archon) → agent.graphiti.signed.v1
```

**9 Total Skill Pairings:** model-benchmark-viz, ingest-chit-index, research-summarize-render, chit-3d-viz, voice-synthesis, agent-card-gen, pr-monitor-graphiti-chit, health-sync, finance-sync

---

### 1.5 p7-agents-skills-lifecycle.tac.yaml

**Path:** `pmoves/configs/tac_trees/p7-agents-skills-lifecycle.tac.yaml`
**Name:** TAC_P7_AGENTS_SKILLS_LIFECYCLE v1.0.0
**Purpose:** Full lifecycle: agent registration, SKILL.md discovery, model assignment, VRAM budgeting, node placement, skill pairing validation

**7 Phases:**
1. **Registration** - 11 CLI agent signatures (glyphs, colors, voices), AGENTS.md format, persona binding
2. **Discovery** - SKILL.md format spec, 6 deployed SKILL.md files, pterm search integration
3. **Model Assignment** - TensorZero routing, agent→model preferences, local mesh via Ollama+Tailscale
4. **VRAM Budget** - 5090 (32GB), z890 (24GB), 4090 laptop (16GB)
5. **Skill Pairing Validation** - 7 defined pairings, voice synthesis chain detailed
6. **Onboarding** - 7-step checklist for new agents
7. **Migration** - Platform abstraction (Discord→Matrix), standalone Docker runtime

**GRAPHITI References:** Onboarding step 7: "Sign Graphiti trail entry for attribution" — every new agent must sign a Graphiti trail entry as part of onboarding.

**Nodes:** 5 physical nodes (powerfulmoves-5090, z890, laptop-4090, kvm4-1, kvm4-2)

---

### 1.6 agent-teams-taxonomy.tac.yaml

**Path:** `pmoves/configs/tac_trees/agent-teams-taxonomy.tac.yaml`
**Name:** TAC_AGENT_TEAMS_TAXONOMY v1.0.0
**Purpose:** 11 teams, 62 agents, NATS subjects, skill pairing participation, compute requirements

**11 Teams Summary:**

| Team | Agents | GPU | Key GRAPHITI Role |
|------|--------|-----|-------------------|
| Orchestration | 6 | Optional | `agent.graphiti.signed.v1` publisher (BoTZ gateway) |
| Research & Knowledge | 9 | Partial | cipher_memory (Neo4j) stores Graphiti data |
| Media & Voice | 11 | Heavy | — |
| Data & Storage | 9 | None | Neo4j + Qdrant backend for Cipher/Graphiti |
| User Interfaces | 6 | None | — |
| Automation | 4 | None | — |
| Evolution & CHIT | 4 | Heavy | tokenism encodes CGP for Graphiti |
| Infrastructure | 3 | None | — |
| Sandbox & Execution | 8 | Cloud | — |
| External Contributors | 7 | None | codex+claude-opus in pr-monitor-graphiti-chit |
| Life Integration | 2 | None | — |

**GRAPHITI NATS Subject:** `agent.graphiti.signed.v1` — published by BoTZ Gateway (orchestration team) and External Contributors team. Consumed by Graphiti trail sync.

**Audit Rules:** Single-team membership, minimum 1 NATS subject per team, 62 agent count invariant, 9 pairing coverage.

---

### 1.7 TAC_CIPHER.md (Bonus — not a YAML tree but critical context)

**Path:** `pmoves/docs/TAC/TAC_CIPHER.md`
**Service:** Cipher Memory, Port 8096, Tier: data

**Upstream:** Neo4j (required), Qdrant (optional), NATS (optional)
**Downstream:** Agent Zero, Archon, BoTZ Gateway, Claude Code CLI, all agents

**MCP Tools:** `pmoves_cipher_store`, `pmoves_cipher_search`, `pmoves_cipher_store_reasoning`, `pmoves_cipher_reasoning_patterns`

**Memory Categories:** `code_pattern`, `decision`, `context`, `submodule`, `architecture`, `reasoning`
**Resilience Categories:** `agent_plan`, `agent_checkpoint`, `agent_completion`

**NATS Subjects:** `cipher.memory.stored.v1`, `cipher.memory.searched.v1`, `cipher.reasoning.stored.v1`

**Security:** Bearer token auth via `CIPHER_API_TOKEN` (skips if unset = dev mode). No `/metrics` endpoint.

**CHIT Integration:** None — stores CHIT data but doesn't generate/process CGP packets.

---

## 2. Cipher-MCP Architecture

### 2.1 File Inventory (14 files)

```
pmoves-cipher-mcp/
├── main.py                          # Entry point: health loop + NATS announce + MCP server
├── README.md                        # Architecture docs, MCP config, quick start
├── pyproject.toml                   # Python 3.11+, deps: mcp, httpx, nats-py
├── .gitignore                       # Standard Python ignores
├── cipher_mcp/
│   ├── __init__.py                  # Package docstring, __version__ = 0.1.0
│   ├── client.py                    # HTTP client for Cipher Memory Node.js backend
│   ├── nats_events.py               # Fire-and-forget NATS event publisher
│   ├── server.py                    # MCP stdio server (mcp library)
│   └── tools.py                     # 4 MCP tool definitions + handlers
├── pmoves_health/
│   └── __init__.py                  # Async health check via CipherClient
├── pmoves_announcer/
│   └── __init__.py                  # NATS service discovery announcer
├── pmoves_common/
│   └── __init__.py                  # Shared enums: ServiceTier, HealthStatus, MemoryCategory
└── pmoves_registry/
    └── __init__.py                  # URL resolution: cipher, NATS, tensorzero
```

### 2.2 Entry Point (main.py)

Three concurrent components launched via asyncio:

```
asyncio.run(run())
  ├── asyncio.create_task(_announce_once())     # NATS services.announce.v1 (fire-and-forget)
  ├── asyncio.create_task(_health_loop(60s))     # Periodic health check to Cipher :8096
  └── await mcp_main()                           # Blocking MCP stdio server
```

- Health loop: logs unhealthy status to stderr every 60s
- NATS announce: best-effort, logs skip on failure
- MCP server: blocking stdio transport for Claude Code CLI

### 2.3 MCP Server (cipher_mcp/server.py)

- Uses `mcp` Python library (>=1.0.0)
- Server name: `pmoves-cipher`, version 0.1.0
- Transport: stdio (for Claude Code CLI integration)
- Delegates tool handling to `TOOL_HANDLERS` dict from tools.py

### 2.4 MCP Tools (cipher_mcp/tools.py)

**4 tools exposed:**

| Tool Name | Function | NATS Event | Description |
|-----------|----------|------------|-------------|
| `pmoves_cipher_store` | `pmoves_cipher_store()` | `cipher.memory.stored.v1` | Store content with category+tags |
| `pmoves_cipher_search` | `pmoves_cipher_search()` | `cipher.memory.searched.v1` | Semantic search (?q=...) |
| `pmoves_cipher_store_reasoning` | `pmoves_cipher_store_reasoning()` | `cipher.reasoning.stored.v1` | Store Q/reasoning/result trace |
| `pmoves_cipher_reasoning_patterns` | `pmoves_cipher_reasoning_patterns()` | (none) | Search reasoning category only |

All NATS events are fire-and-forget via `_spawn_background()` — tool returns immediately, NATS publish happens asynchronously. Failed NATS publishes are logged to stderr but never block the tool response.

**Input Schema Highlights:**
- `pmoves_cipher_store`: content (required), category (enum: 6 values, default=context), tags (string[]), metadata (object)
- `pmoves_cipher_search`: query (required), category (optional), tags (optional), limit (int, default=10)

### 2.5 HTTP Client (cipher_mcp/client.py)

`CipherClient` class — async HTTP client using `httpx`:

**URL Resolution:** `CIPHER_URL` → `CIPHER_MEMORY_URL` → `http://localhost:8096`

**Auth:** Reads `CIPHER_API_TOKEN` env var, sends `Authorization: Bearer <token>` header if set. No token = no auth header (dev mode).

**Methods:**
- `health_check()` → GET /health
- `store_memory(content, category, tags, metadata)` → POST /api/memory
- `search_memories(query, category, tags, limit)` → GET /api/memory/search?q=...
- `store_reasoning(question, reasoning, result, ...)` → delegates to store_memory with formatted content
- `search_reasoning(query, limit)` → delegates to search_memories with category=reasoning
- `get_memory(memory_id)` → GET /api/memory/{id}
- `delete_memory(memory_id)` → DELETE /api/memory/{id}

**Data model:** `MemoryItem` dataclass with id, content, category, tags, created_at, embedding_id (optional), reasoning_id (optional).

**Error hierarchy:** `CipherClientError` → `CipherConnectionError`, `CipherAPIError`

### 2.6 NATS Events (cipher_mcp/nats_events.py)

Three event types, all fire-and-forget:

```python
SUBJECT_STORED = "cipher.memory.stored.v1"        # {memory_id, category, tags, timestamp}
SUBJECT_SEARCHED = "cipher.memory.searched.v1"     # {query, result_count, category, timestamp}
SUBJECT_REASONING_STORED = "cipher.reasoning.stored.v1"  # {reasoning_id, question[:200], timestamp}
```

**Connection pattern:** connect (5s timeout) → publish → flush → close. Always closes in finally block. Never raises — logs to stderr on failure.

### 2.7 Service Packages

**pmoves_common/__init__.py** — Shared enums:
- `ServiceTier`: data, api, llm, worker, media, agent, ui (7-tier architecture)
- `HealthStatus`: healthy, degraded, unhealthy
- `MemoryCategory`: code_pattern, decision, context, submodule, architecture, reasoning

**pmoves_health/__init__.py** — Single `health_check()` async function:
- Calls `CipherClient().health_check()`
- Returns `{status: "healthy"|"unhealthy"|"degraded", detail: ...}`
- Catches CipherClientError → unhealthy, generic Exception → degraded

**pmoves_announcer/__init__.py** — NATS service discovery:
- `ServiceAnnouncement` dataclass: slug, name, url, health_check, tier, port, timestamp, metadata
- Publishes to `services.announce.v1`
- Default: slug=cipher-mcp, tier=API, port=8082, metadata={bridge_for: cipher-memory, protocol: mcp, transport: stdio}
- Same connect→publish→flush→close pattern as nats_events.py

**pmoves_registry/__init__.py** — URL resolution:
- `get_cipher_url()`: CIPHER_URL → CIPHER_MEMORY_URL → http://localhost:8096
- `get_nats_url()`: NATS_URL → nats://nats:pmoves@nats:4222
- `get_tensorzero_url()`: TENSORZERO_URL → TENSORZERO_GATEWAY_URL → http://tensorzero-gateway:3030

### 2.8 Dependencies (pyproject.toml)

```toml
requires-python = ">=3.11"
dependencies = [
  "mcp>=1.0.0",        # MCP protocol server
  "httpx>=0.27.0",      # Async HTTP client
  "nats-py>=2.7.0",     # NATS client
]
build-system = "hatchling"
```

No cryptography libraries. No Neo4j driver. No Qdrant client. No TensorZero client.

---

## 3. Encryption/Signing Implementation Details

### 3.1 CRITICAL FINDING: No Cryptographic Operations in cipher-mcp

**The `pmoves-cipher-mcp/` submodule contains ZERO encryption, decryption, signing, or verification code.**

Exhaustive grep results for cryptographic terms:

| Term | Matches | Nature |
|------|---------|--------|
| `encrypt` | 0 | — |
| `decrypt` | 0 | — |
| `sign` | 0 | — |
| `verify` | 0 | — |
| `hmac` | 0 | — |
| `sha` | 0 | — |
| `aes` | 0 | — |
| `rsa` | 0 | — |
| `crypto` | 0 | — |
| `hsm` | 0 | — |
| `pkcs` | 0 | — |
| `tpm` | 0 | — |
| `key_store` | 0 | — |
| `hardware.*key` | 0 | — |

All grep matches for "cipher" are naming references (CipherClient, Cipher Memory, cipher_mcp) — not cryptographic operations.

### 3.2 What "Cipher" Actually Means

In PMOVES.AI, "Cipher Memory" is a **knowledge-graph memory service** backed by Neo4j, not a cryptographic module. The name likely derives from "deciphering” knowledge or encoding information into a graph structure, not from encryption.

### 3.3 Authentication (Not Encryption)

The only security mechanism is Bearer token authentication:

```python
# cipher_mcp/client.py
self._token = os.getenv("CIPHER_API_TOKEN", "")

def _get_headers(self) -> dict:
    if self._token:
        return {"Authorization": f"Bearer {self._token}"}
    return {}
```

- Token is a static env var, not dynamically generated
- No token = no auth header sent (dev mode)
- No token validation logic in MCP bridge (validated by Cipher Memory Node.js backend)
- No TLS/mTLS configuration in the bridge (relies on transport layer)

### 3.4 Where CHIT HMAC Signing Actually Lives

The TAC trees reference "Sign Graphiti trail entry with CHIT HMAC" (`/chit:sign-trail` skill, `agent.graphiti.signed.v1` NATS subject). This signing logic is NOT in cipher-mcp. Based on TAC tree analysis:

- **Agent responsible:** archon (step 4 of pr-monitor-graphiti-chit pairing)
- **Make target:** `make -C pmoves sign-trail`
- **Likely location:** PMOVES-Archon/ submodule or pmoves/tools/chit/ directory
- **Not found in:** pmoves-cipher-mcp/, Pmoves-cipher/ (Node.js backend)

The actual HMAC implementation would be in the Archon service or a shared CHIT library, not in the Cipher MCP bridge.

### 3.5 Key Management

**No key management exists in cipher-mcp.** The only "key" is `CIPHER_API_TOKEN` — a static bearer token passed via environment variable. There is:
- No key generation
- No key rotation (though `tokenism.credential.rotated.v1` NATS subject exists in the broader system)
- No key storage (HSM, vault, K8s secret)
- No key derivation

---

## 4. Cross-References

### 4.1 Docker / Dockerfile

**No Dockerfile exists in pmoves-cipher-mcp/.** The submodule is not containerized independently.

The Cipher Memory Node.js backend runs as `cipher-api` in the main `pmoves/docker-compose.yml` (profile: `agents`, port 8096). The MCP bridge runs as a stdio process spawned by Claude Code CLI — no container needed.

README mentions: "The Cipher Memory backend runs as cipher-api in the PMOVES docker-compose stack (profile: agents, port 8096). It shares the existing Neo4j instance."

### 4.2 NATS Subjects

**4 subjects defined in cipher-mcp code:**

| Subject | File | Direction | Payload |
|---------|------|-----------|---------|
| `services.announce.v1` | pmoves_announcer | Publish | ServiceAnnouncement JSON (slug, name, url, tier, port, metadata) |
| `cipher.memory.stored.v1` | cipher_mcp/nats_events.py | Publish | {memory_id, category, tags, timestamp} |
| `cipher.memory.searched.v1` | cipher_mcp/nats_events.py | Publish | {query, result_count, category, timestamp} |
| `cipher.reasoning.stored.v1` | cipher_mcp/nats_events.py | Publish | {reasoning_id, question[:200], timestamp} |

**GRAPHITI-related NATS subject (NOT in cipher-mcp):**
- `agent.graphiti.signed.v1` — referenced in skills-taxonomy and agent-teams-taxonomy TAC trees, published by archon agent on trail signing

**Default NATS URL:** `nats://nats:pmoves@nats:4222` (hardcoded fallback, overridable via NATS_URL env)

### 4.3 TensorZero Configuration

**Minimal reference only.** `pmoves_registry/__init__.py` exports `get_tensorzero_url()` but it is never imported or called anywhere in cipher-mcp. It exists as a registry stub for potential future use.

```python
def get_tensorzero_url() -> str:
    return (
        os.getenv("TENSORZERO_URL") or
        os.getenv("TENSORZERO_GATEWAY_URL") or
        "http://tensorzero-gateway:3030"
    )
```

No TensorZero client usage, no model routing, no embedding calls through TensorZero in this submodule.

### 4.4 Neo4j References

**Documentation only.** Neo4j is referenced in README.md architecture diagram and comments:
- "Cipher Memory (Node.js / Neo4j)” — architecture diagram
- “shares the existing Neo4j instance” — Docker section

No Neo4j driver (`neo4j` Python package) in dependencies. No Cypher queries. All Neo4j interaction happens in the Cipher Memory Node.js backend (Pmoves-cipher/ submodule).

### 4.5 Qdrant References

**Single comment only.** In `cipher_mcp/client.py` docstring:
```python
"""
Cipher Memory provides:
- Store memory with embeddings (Qdrant)
- Search by semantic similarity
- Store reasoning traces (knowledge graph)
- Query reasoning patterns
"""
```

No Qdrant client (`qdrant-client` Python package) in dependencies. All vector search is handled by the Cipher Memory Node.js backend.

---

## 5. Key Findings & Gaps

### 5.1 GRAPHITI Integration Pattern

GRAPHITI in PMOVES.AI is an **attribution and trail-tracking system** woven into the PR review workflow:

```
PR Created → codex scans (/pr-monitor) → claude-opus trims (/pr-trim)
  → tokenism encodes learnings as CGP (/chit:review-sweep)
  → archon signs trail entry (/chit:sign-trail) → agent.graphiti.signed.v1
```

GRAPHITI data flows:
- **Into training:** Agent Graphiti trail entries are used as embedding fine-tuning training data
- **Into Cipher Memory:** Stored via Neo4j knowledge graph (cipher_memory agent, port 8096)
- **Into onboarding:** Every new agent must sign a Graphiti trail entry
- **Into handoffs:** Agent SDK handoff publishes `agent.graphiti.signed.v1`

### 5.2 Critical Gap: CHIT HMAC Signing Location Unknown

The `/chit:sign-trail` skill (CHIT HMAC signing of Graphiti trail entries) is referenced across multiple TAC trees but the actual implementation was NOT found in:
- pmoves-cipher-mcp/ (this research)
- The 6 TAC trees (they reference it but don't contain it)

**Confirmed locations to investigate (from file tree + auto-context):**
- `pmoves/tools/chit/` — 4 files exist (CHIT encode/decode/sign tools)
- `pmoves/tests/test_sign_trail.py` — test file for sign-trail functionality
- `pmoves/tools/chit_security_validator.py` — CHIT security validation with access control
- `PMOVES-Archon/` submodule (archon agent executes step 4)
- `PMOVES-ToKenism-Multi/integrations/contracts/chit/` — CHIT TypeScript contract modules
- `make -C pmoves sign-trail` target in Makefile
- `pmoves/docs/SECRETS_PIPELINE_REFERENCE.md` — documents CHIT crypto layer in secrets funnel

### 5.3 Cipher-MCP is a Thin Bridge, Not a Crypto Module

The cipher-mcp submodule is a straightforward MCP→HTTP bridge with NATS event side-effects:
- 4 MCP tools → 4 HTTP endpoints on Cipher Memory :8096
- 3 NATS fire-and-forget events after successful operations
- 1 NATS service announcement on startup
- 1 periodic health check loop
- Zero cryptographic operations
- Zero direct database connections (Neo4j/Qdrant)

### 5.4 Security Gaps

| Gap | Severity | Details |
|-----|----------|---------|
| No auth in dev mode | P2 | `CIPHER_API_TOKEN` unset = no Authorization header sent |
| Static bearer token | P2 | No rotation mechanism in cipher-mcp (rotation exists elsewhere: `tokenism.credential.rotated.v1`) |
| No TLS config | P3 | Relies on network isolation / Docker network / Tailscale mesh |
| No input validation | P3 | MCP tool args passed directly to HTTP client without sanitization |
| NATS credentials in default URL | P3 | `nats://nats:pmoves@nats:4222` has password in hardcoded fallback |

### 5.5 Architecture Gaps

| Gap | Status | Details |
|-----|--------|---------|
| Not a proper git submodule | Open | Lives in main repo, not git submodule (per TAC_CIPHER.md) |
| No /metrics endpoint | Open | Not scraped by Prometheus |
| No tests | Open | Zero test files in cipher-mcp |
| get_tensorzero_url() unused | Stub | Exported but never called |
| pmoves_reasoning_patterns no NATS event | Inconsistency | Other 3 tools emit NATS events; reasoning_patterns search does not |
| Announcer port mismatch | Potential bug | Announcer defaults to port 8082 but Cipher Memory is on 8096 |

### 5.6 GRAPHITI Data Flow Summary

```
                    ┌─────────────────────────────────┐
                    │     GRAPHITI Trail System       │
                    │  (attribution + provenance)      │
                    └──────────┬──────────────────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
              ▼                ▼                ▼
     ┌────────────┐   ┌────────────┐   ┌────────────┐
     │ Cipher Mem  │   │ Training   │   │ Agent      │
     │ (Neo4j)     │   │ Pipeline   │   │ Onboarding │
     │ :8096       │   │ (Unsloth)  │   │ (step 7)   │
     └──────┬─────┘   └────────────┘   └────────────┘
            │
            │ MCP stdio
            ▼
     ┌────────────┐
     │ cipher-mcp │ ← This research subject
     │ (Python)    │
     └────────────┘
```

Cipher-MCP is the Claude Code CLI access path to Cipher Memory where Graphiti trail data is stored. It does not participate in signing, encryption, or CGP encoding — those happen in other services (ToKenism, Archon).

---

*End of research document.*
