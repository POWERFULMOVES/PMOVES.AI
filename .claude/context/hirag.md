# HiRAG context

**Submodules:** [PMOVES-HiRAG/](https://github.com/POWERFULMOVES/PMOVES-HiRAG) (the algorithm/research work) + [pmoves-hirag-mcp/](https://github.com/POWERFULMOVES/pmoves-hirag-mcp) (the MCP server)
**Submodule pins:** PMOVES-HiRAG `e904b12a477ad670d5036e059912c2889c308926` (tracks `PMOVES.AI-Edition-Hardened`), pmoves-hirag-mcp `0ec18d886643bf16a9b415873b4898409421c024` (main)
**Compose services:** `hi-rag-gateway` (CPU, port 8089→8086, legacy profile) and `hi-rag-gateway-gpu` (GPU, port 8090→8086, gpu + legacy profile)
**MCP server name:** `pmoves-hirag-mcp`
**MCP transport:** SSE (declared in agent registry; not yet in `.claude/mcp.json` — wiring is a follow-up)
**Discovery entry:** `pmoves/config/agent_registry.yaml` → `mcp_servers.pmoves_hirag_mcp`
**Grounding source:** `true` (per the registry: "a discovering agent fetches startup grounding here")

HiRAG is PMOVES's hybrid retrieval layer — vector + graph + full-text, combined under a single query interface. It's the second of the two `grounding_source: true` MCP servers in the registry (cipher is the other). This context captures what it is, what's wired, what's pending, and how a Mavis-class agent should use it.

## What HiRAG is

The "hybrid" in HiRAG is a three-way retrieval: dense vector (Qdrant), graph traversal (Neo4j), and full-text search (MeiliSearch). A single query fans out to all three, the results are merged and reranked, and a unified top-K comes back. The legacy gateway (`hi-rag-gateway`) and v2 gateway (`hi-rag-gateway-v2`) are the two HTTP surfaces; the MCP server is the discovery-friendly entry point.

The research/algorithm substrate is in PMOVES-HiRAG, which tracks the hardened branch. The companion paper "Latent Geometry as a Control Knob" (in `pmoves/docs/context/Latent_Geometry_Is_a_Control_Knob/`) is the theoretical motivation — the claim is that the latent geometry of the vector space encodes the relationship structure that a graph would otherwise have to be told about, and that hybrid retrieval is a way to combine the geometry's implicit structure with explicit graph structure. The HiRAG v2 gateway is the implementation of that thesis.

## What's wired

Three things, in priority order:

1. **MCP server entry in agent registry** — `pmoves_hirag_mcp` is declared in `pmoves/config/agent_registry.yaml` line 3032 with `transport: "sse"`, `endpoint: ${PMOVES_HIRAG_MCP_ENDPOINT:-http://pmoves-hirag-mcp:8080/sse}`, `action_namespace: "mcp.v1.hirag"`, `capabilities: ["retrieve", "graph", "search", "notebook"]`, `rooms: ["4090-field.room.control", "hermes-agent.room.control"]`, `grounding_source: true`, `status: "planned"`. The entry exists; the MCP server itself runs as a Docker service in compose.

2. **Legacy hi-rag-gateway in compose** — both the CPU and GPU variants are in the compose overlay system. The CPU service is `hi-rag-gateway` on port `8089→8086`; the GPU service is `hi-rag-gateway-gpu` on port `8090→8086`. Both are gated on the `legacy` profile; the GPU service also needs the `gpu` profile. Both depend on Qdrant and Neo4j.

3. **Smoke test path** — `docker compose --profile legacy up -d qdrant neo4j hi-rag-gateway` brings up the legacy stack, then `curl -sS http://localhost:8089/hirag/query -H 'content-type: application/json' -d '{"query":"hello","namespace":"pmoves","k":3}'` exercises the query interface. The README notes that `make bootstrap-data` is the right way to populate the demo data before running smokes.

## What's pending

Three things, in priority order:

1. **`.claude/mcp.json` registration** — unlike cipher (which has both a registry entry AND a `.claude/mcp.json` server), HiRAG is in the registry only. A future PMOVES-aware agent that tries to consume the MCP server directly from `.claude/mcp.json` will not find it. The fix is a one-block addition to `.claude/mcp.json` mirroring the `pmoves-cipher` pattern (SSE transport, URL from the same env var the registry references). Recommendation: do this when HiRAG becomes a real cold-start surface, not in the wire-up PR (the MCP server is `status: "planned"`, not `"active"`).

2. **v2 gateway promotion** — the v2 README explicitly says "v2 remains the preferred path for advanced features and UI" but the legacy stack is what's actually wired in compose. The v2 is documented but not deployed. The risk is that a new agent is built against the legacy gateway and the v2 stays second-class. Recommendation: a follow-up slice that promotes v2 to the default and demotes the legacy stack to "compatibility only."

3. **PMOVES-HiRAG submodule freshness** — the submodule tracks `PMOVES.AI-Edition-Hardened`, not `main`. The most recent commit is `e904b12a` from August 2026; the upstream research is presumably still landing there. The risk is the algorithm substrate drifts from the v2 gateway implementation. Recommendation: a `submodule-integrity` check on every PR that touches either the submodule or the gateway; the existing `.github/scripts/validate_submodule_gitlinks.sh` covers the gitlink but not the freshness-vs-main check.

## How a Mavis-class agent should use it

Three patterns, in priority order:

1. **Read on cold start for grounding.** The `grounding_source: true` flag in the registry entry means a discovering agent fetches startup grounding here. Concretely: when Mavis first loads, it should issue a `retrieve(query="<lane context>", namespace="pmoves", k=5)` call against HiRAG to surface the most relevant prior work, plans, and CHIT trail entries for the lane it's about to work in. The cipher MCP complements this (cipher is the durable memory; HiRAG is the relevant-now retrieval over that memory).

2. **Issue hybrid queries for cross-cutting context.** A single HiRAG query covers the vector + graph + full-text space. The common case: "what did we decide about X last time it came up?" — a vector match on the topic, a graph match on related people/decisions, and a full-text match on the literal phrase. The merged top-K is the right context window for a planning step.

3. **Fall back to scoped search for narrow questions.** If the question is highly specific (a function name, a commit SHA, a person), full-text search via Meili is faster than HiRAG. The MCP server's `search` capability is the right entry point; reserve the broader `retrieve` for open-ended questions.

## What HiRAG is NOT

- Not a primary database. The durable source of truth is Supabase (Postgres) for structured data, Neo4j for the graph, and Qdrant for vectors. HiRAG is the read-side.
- Not a real-time index. HiRAG's indices are populated by the bootstrap-data make target, not by event-driven writes. If you write to Qdrant/Neo4j/Meili directly, HiRAG will see it on its next query; if you need a guaranteed-fresh view, query the underlying store.
- Not a replacement for cipher. Cipher is the durable memory; HiRAG is the retrieval over it. A write goes to cipher; a read goes to HiRAG.
- Not a search engine. HiRAG searches PMOVES-side data (the seeded corpus). For web search, use the `mmx search web` CLI or a web-search MCP.

## Reference

- Submodule (algorithm substrate): `PMOVES-HiRAG/` (PMOVES fork of HiRAG research; tracks `PMOVES.AI-Edition-Hardened`)
- Submodule (MCP server): `pmoves-hirag-mcp/`
- Compose services: `hi-rag-gateway` (CPU, legacy profile) and `hi-rag-gateway-gpu` (GPU, gpu+legacy profile)
- Service docs: `pmoves/docs/services/hi-rag-gateway/README.md` and `pmoves/docs/services/hi-rag-gateway-v2/README.md`
- Agent registry: `pmoves/config/agent_registry.yaml` → `mcp_servers.pmoves_hirag_mcp`
- Theory paper: `pmoves/docs/context/Latent_Geometry_Is_a_Control_Knob/`
- v2 design notes: see `hi-rag-gateway-v2/README.md` and the LATEST_ENTRY notes in the submodule
- Hybrid search: Qdrant (vector) + Neo4j (graph) + MeiliSearch (full-text), merged at the gateway
- Discovery rooms: `4090-field.room.control`, `hermes-agent.room.control`
