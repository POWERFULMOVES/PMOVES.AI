# TAC — Cipher as Village Memory

> **GRAPHITI_MARK:** TAC-CIPHER-VILLAGE::2026-07-28
> **Status:** Phase B PR 1 in-flight (agentId parameter on all 4 MCP tools)
> **Supersedes:** `SPARK_CIPHER_VILLAGE_ARCH_2026-07-28.md` handoff (content merged here)
> **Trigger:** Operator vision 2026-07-28 — "cipher api village [memory]; every agent crush claude kimi whether in cli or claw needs access to their own cipher and cipher connects to neo4j and hirag and supabase"

## Thesis

Cipher is the **first glue layer** of the PMOVES MOF architecture. It is the broker through which any model — from a 1B local Ollama model to a frontier cloud model — gains:

1. **Unlimited context** via semantic retrieval (Qdrant dense + BM25 sparse + RRF fusion)
2. **Persistent memory** across sessions (Marco/Polo: store with one phrasing, retrieve with another)
3. **Tool discovery** via MCP catalog (brokers BoTZ gateway's tool registry)
4. **Session state** so cold starts stop re-reading 1000-line AGNOTE files
5. **Graph memory** via Neo4j (decisions link to context, reasoning links to decisions)
6. **Hybrid retrieval** via HiRAG (cipher → HiRAG for cross-collection search)
7. **Relational persistence** via Supabase (token registry, access log, mirror tables)

A model spawning into any harness (crush, claude, kimi, clawz) calls cipher first to bootstrap identity, retrieve its state of play, fetch its tool catalog, and load its session context. **Models model; tools tool; cipher brokers.**

## The matrix

Three orthogonal dimensions define an agent instance:

| Dimension | Examples | Source of truth |
|------------|----------|-----------------|
| **Agent** | crush-spark, claude-4090, kimi-spark, clawz-darkxsides, hermes-knuckles, nemotron-1 | `signing_identity_cards.yaml` `agent_id` |
| **Harness** | crush, claude-code, kimi-cli, kilocode, openclaw, hermes-agent, pinokio-p7 | process binary + `.config/` directory |
| **Model** | glm-5.2 (zai), glm-5-turbo (zai), qwen3.5:35b (ollama), nemotron-3-super:120b (ollama), claude-sonnet-4.5, kimi-k2.6 | `crush.json` / `.kimi/config.toml` / etc. |

The cipher `agentId` field carries the **Agent** coordinate. The harness and model are recorded in the memory payload as `source.harness` and `source.model` for observability and replay.

## Scope model (Option A+B combined)

| Option | Layer | Status |
|--------|-------|--------|
| **A. agentId in tool input** | Application — every tool takes `agentId` (required); Qdrant payload filter | **PR 1 (this lane)** |
| **B. Per-agent tokens** | Auth — `CIPHER_API_TOKEN` resolves to `agentId`; middleware injects into tool context | **PR 2** |
| **C. Per-agent Qdrant collections** | Storage — `pmoves_cipher_memory_<agentId>` | **Deferred** — collection-per-agent scales poorly; Option A+B filter is sufficient |

With A+B: agent self-declares `agentId` on every call (A); token middleware verifies it matches the token's bound agent (B). Mismatch → 403. Dev-skip (no token) → A alone applies (advisory).

## Tool inventory (current + planned)

| Tool | Status | Purpose |
|------|--------|---------|
| `pmoves_cipher_store` | ✅ exists (PR 1 adds agentId) | Store memory with category, tags, agentId |
| `pmoves_cipher_search` | ✅ exists (PR 1 adds agentId) | Semantic search scoped by agentId |
| `pmoves_cipher_store_reasoning` | ✅ exists (PR 1 adds agentId) | Store chain-of-thought |
| `pmoves_cipher_reasoning_patterns` | ✅ exists (PR 1 adds agentId) | Search past reasoning |
| `pmoves_cipher_session_save` | **PR 4** | Save session state (cold-start semantic cache write) |
| `pmoves_cipher_session_recall` | **PR 4** | Recall latest session state for this agent (cold-start cache read) |
| `pmoves_cipher_mcp_list` | **PR 3** | List MCPs from BoTZ gateway catalog (filtered by agentId scopes) |
| `pmoves_cipher_mcp_get` | **PR 3** | Get one MCP definition from BoTZ gateway |
| `pmoves_cipher_graph_expand` | **PR 5** | Given a memory id, return Neo4j neighborhood |
| `pmoves_cipher_hybrid_search` | **PR 6** | Proxy HiRAG `:8086/hirag/query` against cipher collection |

## Phase plan

### Phase A — Cipher stood up on SPARK ✅ DONE 2026-07-28
- Rebuilt from Pmoves-cipher@hardened `d9fab9a8`
- Regenerated stale `package-lock.json` (nats@2.29.3 missing from PR #2116)
- Container live on `:8105`, attached to pmoves_app+pmoves_data+pmoves_bus+pmoves_external+pmoves_api
- crush.json entry re-enabled, MCP SSE handshake verified

### Phase B PR 1 — agentId parameter (Option A) — **IN FLIGHT**
Branch: `feat/cipher-agent-scope` on Pmoves-cipher fork.

Files modified:
- `src/pmoves/mcp-sse.ts` — add `agentId` to all 4 tool schemas (required); thread through to store/search calls
- `src/pmoves/embedding.ts` — `storeVector` and `search` accept `agentId`; payload includes `agentId`; filter includes `agentId`
- `src/pmoves/memory-routes.ts` — REST `/api/memory` POST accepts `agentId` in body; GET search accepts `?agentId=`

Migration note: existing Qdrant points (none yet on fresh install) lack `agentId` payload. Search filter uses `must` for `agentId` so only the owning agent's points surface — but write always stamps `agentId`.

### Phase B PR 2 — Per-agent tokens (Option B)
Branch: `feat/cipher-per-agent-tokens` (depends on PR 1).

- New table: `pmoves_core.cipher_agent_tokens` (token UUID PK, agent_id, scopes[], created_at, revoked_at, created_by)
- New table: `pmoves_core.cipher_access_log` (id, agent_id, tool, memory_id, ts, harness, model)
- New endpoint: `POST /api/agents/mint-token` (admin-only — bootstrap token in env)
- `auth.ts` middleware: on Bearer token, look up agent_id, attach to `req.agentId`
- Tool dispatch: use `req.agentId` if present (enforcement); fall back to args.agentId if dev-skip (advisory)
- Mismatch (token agent_id ≠ args.agentId) → 403
- Make target: `make -C pmoves cipher-mint-token AGENT=crush-spark` → prints token

### Phase B PR 3 — MCP catalog (BoTZ bridge)
Branch: `feat/cipher-mcp-catalog` (depends on PR 1 for `agentId` scoping; PR 2 token scopes are optional for fine-grained filtering).

Three pre-existing pieces need wiring:
1. **BotZ-gateway .NET** (`PMOVES-BotZ-gateway/dotnet/Microsoft.McpGateway.Management/`) — Redis-backed CRUD (`tool:{name}`, `tool:list` keys)
2. **Cipher aggregator** (`PMOVES-BoTZ/features/cipher/pmoves_cipher/src/core/mcp/aggregator.ts`) — in-memory Map of tools collected from downstream MCPs
3. **gateway-agent ToolRegistry** (`pmoves/services/gateway-agent/app.py:215-305`) — 5-min TTL cache, GET /tools

The bridge:
- Cipher reads `GET /tools` from gateway-agent (or falls back to an empty list if the gateway is unreachable)
- Exposes `pmoves_cipher_mcp_list` / `pmoves_cipher_mcp_get` MCP tools
- Filter by `agentId` scopes when a PR 2 token is present (each token has a `scopes[]` array)
- Publishes `cipher.mcp.catalog.updated.v1` on NATS when the catalog changes

### Phase B PR 4 — Session state (semantic cache)
Branch: `feat/cipher-session-state` (depends on PR 1).

Infrastructure already exists at `pmoves/services/semantic-cache/`:
- `cipher_layer.py` — queries Cipher Memory API before pgvector fallback
- pgvector table `pmoves_cache.llm_semantic_cache` (migration `20260702000000_semantic_cache.sql`)
- `search_semantic_cache()` SQL function

New cipher tools:
- `pmoves_cipher_session_save` — args: `{agentId, summary, prompt_digest?, context_paths[]}` → stores as category=`agent_checkpoint`
- `pmoves_cipher_session_recall` — args: `{agentId, query?}` → returns most recent `agent_checkpoint` matching semantic query (or just most recent if no query)

cold-start flow:
1. crush boots, calls `pmoves_cipher_session_recall(agentId="crush-spark", query="latest state of play")`
2. cipher returns cached session summary
3. crush loads summary instead of full AGNOTE4482 (saves ~30k tokens)
4. If no hit, crush reads AGNOTE4482, calls `pmoves_cipher_session_save` to cache for next time

### Phase B PR 5 — Neo4j graph memory
Branch: `feat/cipher-neo4j-graph` (depends on PR 1).

- Add `neo4j-driver` npm dep
- New `src/pmoves/graph.ts` — driver wrapper
- On `pmoves_cipher_store`: write Qdrant point AND Neo4j `(:Memory {id, agentId, category, tags, content, ts})`
- Optional edge inference: `(:Memory)-[:SAME_CATEGORY]->(:Memory)` for same agentId + category
- New tool `pmoves_cipher_graph_expand` — given memory id, return N-hop neighborhood

### Phase B PR 6 — HiRAG hybrid retrieval
Branch: `feat/cipher-hirag-bridge` (depends on PR 1).

Pattern (i): cipher calls HiRAG.
- New tool `pmoves_cipher_hybrid_search` — args: `{agentId, query, collections[]?}`
- Cipher proxies `POST http://hi-rag-gateway-v2:8086/hirag/query` with the agent's query
- Default `collections`: `["pmoves_chunks_qwen3"]` (KB) + `["pmoves_cipher_memory"]` (cipher's own)
- Returns fused results from both

### Phase C — Fleet rollout (post-PR 2)
1. Mint one `CIPHER_API_TOKEN` per fleet agent via `make -C pmoves cipher-mint-token AGENT=<id>`
2. Add tokens to `env.tier-agent` + secrets-funnel
3. Update each CLI's MCP config:
   - claude `.claude/mcp.json` `pmoves-cipher.headers.Authorization`
   - crush `~/.config/crush/crush.json` `pmoves-cipher.headers.Authorization`
   - kimi `.kimi/mcp.json` `pmoves-cipher.headers.Authorization`
   - ClaWZ: gateway-agent `A0_SET_mcp_servers.cipher.headers.Authorization`
4. crush-pmoves.sh launcher loads env.shared so `${CIPHER_API_TOKEN}` resolves per-node

## Agent access patterns (target)

| Agent | Harness | Model | agentId | Cold start |
|-------|---------|-------|---------|------------|
| Crush on SPARK | crush CLI | glm-5.2 (zai) | `crush-spark` | session_recall → trail entry → identity |
| Claude on 4090 | claude-code | sonnet-4.5 | `claude-4090` | session_recall → boot protocol → trail |
| Kimi on SPARK | kimi-cli | kimi-k2.6 | `kimi-spark` | session_recall → trail entry |
| ClaWZ | gateway-agent | (per-task) | `clawz-<room>` | session_recall → room manifest |
| Hermes on Knuckles | hermes-agent | hermes-v4 | `hermes-knuckles` | session_recall → trust ledger |

## New-agent bootstrap via CHIT (Phase D future)

A new local-model agent (e.g., a fresh Ollama deploy of `nemotron-3-super:120b`) bootstraps via:
1. Mint token → `agentId=nemotron-1`
2. Call `pmoves_cipher_session_recall(query="known roads danger room agent trails")`
3. Cipher returns compiled digest of:
   - PATTERNS.md Known Roads table
   - AGENT_TRAIL.md recent entries for this agent
   - danger-room run history
   - relevant AGNOTE4482 sections
4. Agent enters the lattice with full context, no manual doc reading

This is the operator's "CHIT will allow new agents from local models to read up known roads" pattern.

## Files

| File | Role |
|------|------|
| `Pmoves-cipher/src/pmoves/mcp-sse.ts` | MCP tool definitions + dispatch (PR 1) |
| `Pmoves-cipher/src/pmoves/embedding.ts` | Qdrant sidecar (PR 1: agentId in payload+filter) |
| `Pmoves-cipher/src/pmoves/memory-routes.ts` | REST `/api/memory` (PR 1: agentId in body+query) |
| `Pmoves-cipher/src/pmoves/graph.ts` | Neo4j driver wrapper (PR 5 — new) |
| `Pmoves-cipher/src/pmoves/hirag-client.ts` | HiRAG proxy client (PR 6 — new) |
| `Pmoves-cipher/src/pmoves/mcp-catalog.ts` | BoTZ gateway Redis client (PR 3 — new) |
| `Pmoves-cipher/src/pmoves/auth.ts` | Token → agentId resolution (PR 2 — extend) |
| `pmoves/supabase/migrations/<ts>_cipher_agent_tokens.sql` | Token registry schema (PR 2 — new) |
| `pmoves/services/semantic-cache/cipher_layer.py` | Already exists — wire to session_save/recall (PR 4) |

## Open questions

1. **agentId format**: match `signing_identity_cards.yaml` `agent_id` exactly? (e.g., `crush-spark`, `claude-4090`) — **YES, recommended**
2. **Token storage**: Supabase `pmoves_core` schema (alongside existing tables) or new `pmoves_cipher` schema? — **`pmoves_core` recommended** (single auth namespace)
3. **Cipher dev-skip behavior**: when `CIPHER_API_TOKEN` unset, should `agentId` be required from args or default to `"anonymous"`? — **required from args, default to `"anonymous"` if absent** (advisory mode)
4. **Session cache TTL**: 24h? 7d? — **7d recommended** (covers weekly sprint cycle)
5. **Neo4j edge inference**: automatic on store (slow writes), or background job? — **background job recommended** (write latency stays low)
