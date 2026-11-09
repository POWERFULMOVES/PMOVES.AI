# Cipher as Village Memory — Architecture Review

> **GRAPHITI_MARK:** SPARK-KIMI::CIPHER-VILLAGE-ARCH-REVIEW::2026-07-28
> **Status:** Architecture findings + Phase A delivered; Phase B/C deferred to lane
> **Trigger:** Operator direction — "cipher api village [memory]; every agent crush claude kimi whether in cli or claw needs access to their own cipher and cipher connects to neo4j and hirag and supabase"

## Current state (verified live on SPARK 2026-07-28)

| Layer | State | Evidence |
|-------|-------|----------|
| cipher-api container | ✅ running | `pmoves-cipher-api` Up healthy on host `:8105` |
| Container internal port | ✅ `:8105` (not `:3000` — TAC doc is stale) | honors `PMOVES_PORT` env |
| MCP-over-SSE endpoint | ✅ `/mcp/sse` 4 tools | handshake verified, session established |
| 4 MCP tools | ✅ all registered | `pmoves_cipher_store`, `pmoves_cipher_search`, `pmoves_cipher_store_reasoning`, `pmoves_cipher_reasoning_patterns` |
| Categories (9) | ✅ defined | `code_pattern`, `decision`, `context`, `submodule`, `architecture`, `reasoning`, `agent_plan`, `agent_checkpoint`, `agent_completion` |
| Qdrant vector sidecar | ✅ connected | `pmoves_cipher_memory` collection, 2560d COSINE, BM25 sparse fallback |
| TensorZero embeddings | ✅ connected | `qwen3_embedding_4b_local`, 2560d |
| Ollama embedding fallback | ✅ wired (code) | `qwen3-embedding:4b` (untested live — host Ollama bind 127.0.0.1-only) |
| NATS event emission | ✅ connected | `cipher.memory.stored.v1`, `.searched.v1`, `cipher.reasoning.stored.v1`, `services.announce.v1` |
| Supabase reachability | ✅ FIXED THIS SESSION | cipher-api attached to `pmoves_api`; `supabase-kong:8000` now reachable |
| Auth | ⚠️ dev-skip mode | `CIPHER_API_TOKEN` unset; `/health` open, all other routes also open (dev-skip rule) |
| Per-agent scoping | ❌ **MISSING** | MemoryManager is global namespace; `sessionId` is MCP-SSE-transport-session, not agent identity |
| Neo4j wiring | ❌ **NOT IMPLEMENTED** | reachable on `pmoves_data:7687` but no code in `src/pmoves/*.ts` |
| HiRAG wiring | ❌ **NOT IMPLEMENTED** | reachable on `pmoves_app:8086` but no code in `src/pmoves/*.ts` |
| Supabase persistence | ❌ **NOT IMPLEMENTED** | now reachable; no code in `src/pmoves/*.ts` |

## Gap analysis — what "every agent gets their own cipher" needs

### Gap 1: Per-agent scope (architectural)

The current shim uses ByteRover's `MemoryManager` — a **global** namespace. Every MCP client that connects reads/writes the same memory store. The MCP `sessionId` returned in the SSE handshake is the **transport session** (one per SSE connection), not an agent identity.

**Implication today:** if crush, claude, kimi, and ClawZ all connect to `:8105/mcp/sse`, they all share the same memory pool. crush's `pmoves_cipher_store` is visible to claude's `pmoves_cipher_search`. There is no isolation.

**Three options (not mutually exclusive):**

| Option | How | Tradeoff |
|--------|-----|----------|
| **A. Agent ID in tool input** | add `agentId` (required) to `pmoves_cipher_store`/`_search`/`_store_reasoning`/`_reasoning_patterns` schemas; filter Qdrant payload by `agentId` | simplest; relies on agent self-identification (no enforcement) |
| **B. Per-agent tokens** | mint one `CIPHER_API_TOKEN` per agent; shim resolves token → agentId; scopes all storage/search by agentId | enforcement at auth layer; needs token-mint endpoint |
| **C. Per-agent Qdrant collections** | one collection per agent (`pmoves_cipher_memory_<agentId>`); token → collection map | hardest isolation; collection-per-agent scales to fleet size |

**Recommended:** Option B (per-agent tokens) — matches the PMOVES pattern (`signing_identity_cards.yaml` already issues per-agent cards) and gives real enforcement without N collections.

### Gap 2: Neo4j integration (graph memory)

The shim has no Neo4j client. The PMOVES architecture intent is that cipher memories form a **graph** — decisions link to context, submodules link to architecture, reasoning links to decisions. Today all memories are flat Qdrant points with category + tags.

**What's needed:**
- `neo4j-driver` npm dep in `Pmoves-cipher/package.json`
- `src/pmoves/graph.ts` — Neo4j client wrapper
- On `pmoves_cipher_store`: write Qdrant point AND Neo4j node (`Memory {id, agentId, category, tags, content, ts}`)
- Optional: infer edges from tag/category overlap (`(:Memory)-[:SAME_CATEGORY]->(:Memory)`)
- On `pmoves_cipher_search`: vector + lexical match in Qdrant → expand via Neo4j traversal
- New tool: `pmoves_cipher_graph_expand` — given a memory id, return its neighborhood

### Gap 3: HiRAG wiring (hybrid retrieval)

HiRAG v2 (`:8086`) already does Qdrant + Neo4j + Meilisearch hybrid retrieval for the **knowledge base**. Cipher memory is a separate Qdrant collection, NOT exposed via HiRAG.

**Two integration patterns:**

| Pattern | How | Tradeoff |
|--------|-----|----------|
| **i. Cipher calls HiRAG** | new tool `pmoves_cipher_hybrid_search` that proxies `POST :8086/hirag/query` against cipher's collection | cipher stays focused on memory; HiRAG owns retrieval |
| **ii. HiRAG consumes cipher collection** | add `pmoves_cipher_memory` to HiRAG's Qdrant namespace + Neo4j graph | unified retrieval; but couples HiRAG config to cipher lifecycle |

**Recommended:** Pattern (i) — cipher is the broker, HiRAG is a service it calls.

### Gap 4: Supabase persistence

cipher-api currently uses in-process MemoryManager (in-memory). Qdrant is the durable vector layer. **There is no relational persistence** — agent metadata, access logs, token→agent map (Option B above) all need a relational store.

**What's needed:**
- `pg` or `postgres` npm dep
- `src/pmoves/supabase.ts` — PostgREST client (no full ORM needed)
- Schema migration: `pmoves_core.cipher_agent_tokens` (token, agent_id, scopes, created_at, revoked_at), `pmoves_core.cipher_access_log` (agent_id, tool, memory_id, ts)
- On tool call: verify token, log access, write/read Qdrant, write Neo4j
- Optional: `pmoves_core.cipher_memories` mirror table for SQL-side queries / dashboards

## Phase plan

### Phase A — Delivered this session ✅
- [x] Rebuild cipher-api from Pmoves-cipher@hardened `d9fab9a8` (regenerated `package-lock.json` — A1-Shim PR #2116 left it out of sync; `nats@2.29.3` missing)
- [x] Container running on host `:8105`
- [x] Attach cipher-api to `pmoves_api` network (was only on app/bus/data/external; supabase-kong unreachable)
- [x] crush.json: pmoves-cipher SSE → `http://localhost:8105/mcp/sse`, `disabled: false`
- [x] Build `pmoves-cipher-api:spark-local` image
- [x] Health verified (`{"status":"healthy","service":"cipher-pmoves-shim","version":"0.1.0"}`)
- [x] MCP SSE handshake verified (session endpoint returned)

### Phase B — Per-agent scoping (multi-PR lane)
Target PRs:
1. `feat(cipher): agentId parameter on all 4 MCP tools` — Option A first (simple, immediate)
2. `feat(cipher): per-agent token mint endpoint` — Option B (enforcement)
3. `feat(cipher): Supabase token+access-log tables` — relational backing
4. `feat(cipher): Neo4j graph integration` — `graph.ts` + write-on-store + expand-on-search
5. `feat(cipher): HiRAG hybrid_search tool` — pattern (i)

### Phase C — Fleet rollout
1. Mint one `CIPHER_API_TOKEN` per fleet agent via Supabase (crush-spark, claude-4090, kimi-spark, clawz-*, etc.)
2. Add tokens to env.tier-agent + secrets-funnel
3. Update each CLI's MCP config (claude `.claude/mcp.json`, crush `~/.config/crush/crush.json`, kimi `.kimi/mcp.json`)
4. ClaWZ: wire via `services.announce.v1` discovery → agent calls cipher via gateway-agent `/mcp/*`

## Agent access patterns (today + target)

| Agent | Today (Phase A) | Target (Phase B+) |
|-------|----------------|-------------------|
| **crush (SPARK)** | crush.json points at `localhost:8105/mcp/sse`, dev-skip auth | per-agent token, `agentId=crush-spark` |
| **claude code (any node)** | `.claude/mcp.json` `pmoves-cipher` entry, dev-skip auth | per-agent token, `agentId=claude-<node>` |
| **kimi (SPARK)** | NOT wired today — needs `.kimi/mcp.json` entry | per-agent token, `agentId=kimi-spark` |
| **ClawZ** | reaches cipher via gateway-agent `A0_SET_mcp_servers` compose env | gateway-agent resolves per-agent token via X-Agent-Token header |

## Files touched this session

| File | Change |
|------|--------|
| `Pmoves-cipher/package-lock.json` | regenerated (npm install --package-lock-only); uncommitted in submodule — needs PR to `POWERFULMOVES/Pmoves-cipher` |
| `Pmoves-cipher` gitlink (superproject) | advanced from `7525c004` → `d9fab9a8` (only in working tree; needs promotion commit) |
| `pmoves-cipher-api` container | created, networks attached (pmoves_app + pmoves_data + pmoves_bus + pmoves_external + pmoves_api), running |
| `~/.config/crush/crush.json` | pmoves-cipher entry re-enabled with localhost URL |

## Open questions for operator

1. **Scoping model:** Option A (agentId in tool input), B (per-agent tokens), or C (per-agent Qdrant collections)? Recommended B.
2. **Neo4j integration depth:** mirror all memories as nodes? Or only cross-link via category/tag overlap?
3. **HiRAG pattern:** cipher calls HiRAG (i), or HiRAG consumes cipher collection (ii)? Recommended (i).
4. **Supabase schema location:** `pmoves_core` schema (alongside existing tables) or new `pmoves_cipher` schema?
5. **Token mint UX:** `make -C pmoves cipher-mint-token AGENT=crush-spark` Make target? Or Supabase Studio UI?
