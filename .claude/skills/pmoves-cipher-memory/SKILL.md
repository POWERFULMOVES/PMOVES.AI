---
name: pmoves-cipher-memory
description: Fleet-wide persistent memory for PMOVES.AI and every PMOVES agent (Claude, Crush peers, KiloCode, Agent Zero, Hermes) across all nodes.
---

# PMOVES Cipher Memory Skill

**Purpose**: Fleet-wide persistent memory across sessions, agents, and nodes.
Cipher is the remember-layer for the whole PMOVES lattice — not a single-node,
single-agent tool. If Cipher is down, an agent still *works* but silently loses
every prior session's lessons; the preflight below exists so that state is
never silent.

## Where Cipher lives (fleet topology)

| Surface | URL | Notes |
|---|---|---|
| Fleet endpoint | `http://${TS_Z890}:8105/mcp/sse` | Hosted on the Z890 node, reachable over the tailnet from every other node |
| Local endpoint | `http://localhost:8105/mcp/sse` | The node's own `cipher-api` container — always prefer this when it is up |
| Stateless HTTP | `POST http://<host>:8105/mcp` | Same tools, no SSE stream (Pmoves-cipher e24f1323) |

- Every node runs its own `cipher-api` (compose profile `agents`); Z890
  publishes it to the tailnet (`CIPHER_BIND=0.0.0.0` in Z890's `env.shared`).
- Memory is durable per node (`cipher-data` volume). Local-first: store to your
  node; the fleet endpoint covers you when your node's instance is down.
- Embedding pipeline: TensorZero `qwen3_embedding_4b_local` (2560d) with an
  Ollama fallback, stored in Qdrant as named vectors `dense` + `bm25` (sparse,
  idf) and queried with hybrid RRF fusion. Fail-open: with the vector backend
  down, store/search degrade to lexical — check for `embedded: false` /
  missing `score` rather than assuming vectors.

## Before every session: preflight + recall (required, not optional)

Cipher is a startup requirement. Run the preflight, then recall:

```
python pmoves/tools/cipher_preflight.py        # authenticates from env; exit 0 = memory is real
pmoves_cipher_session_recall                   # purpose-built cold-start primitive
pmoves_cipher_search  (category=agent_checkpoint or agent_completion)
```

An unmeasured preflight (exit 3) or a 401/403 is NOT a pass — fall back to the
auto-memory directory and say so rather than recalling nothing silently.

## Required on every call: `agentId`

`pmoves_cipher_store` and `pmoves_cipher_search` **require** `agentId`. Use your
signing-card `agent_id` from `pmoves/config/signing_identity_cards.yaml`
(`claude-opus`, `crush`, `4090-claude`, `z890-claude`, ...). The tool's own
description suggests names like `claude-4090`, which match **no card** — the
card is `4090-claude`.

### Identity is enforced when a token is present

| Server mode | Behavior |
|---|---|
| No `CIPHER_API_TOKEN` on server (dev) | Advisory: any `agentId` accepted |
| Legacy token (`CIPHER_API_TOKEN`, bootstrap) | Identity pinned to `bootstrap`; tool-arg `agentId` must equal it or 403 |
| Per-agent token (`cipher_<uuid>` via Supabase) | Identity pinned to the minted agent |

Under enforcement:
- `agentId` is **required on every call** (including search).
- `agentId: "*"` cross-agent search is **rejected** (403) — it is a dev-mode
  convenience only. Cold-start reads therefore only see your own scope.

Mint a per-agent token (requires Supabase up):
`make -C pmoves cipher-mint-token AGENT=crush` — distribution into a node's
`env.shared` is a fleet-identity decision, not automatic.

## Reproducible setup (no hardcoded paths, any node)

1. `make -C pmoves secrets-funnel` — puts `CIPHER_API_TOKEN` into `env.shared`
2. `python3 -m pmoves.tools.mini_cli crush setup` — regenerates crush.json;
   the cipher entries carry `Authorization: Bearer ${CIPHER_API_TOKEN:-}`
3. Launch through `crush-pmoves` — the launcher env bridge resolves
   `${TS_*}` tailnet names and puts the token in the process env so the
   placeholders expand (Claude Code: `.claude/mcp.json` roster + claude-pmoves)
4. Verify: `python pmoves/tools/cipher_preflight.py`

The URL/bearer contract is mirrored from `pmoves/config/mcp_inventory.json`
(canonical) and guarded by `test_crush_cipher_matches_inventory.py`.

## MCP Tools

Ten tools exist. This skill documented three until 2026-08-21; the other seven —
including both session primitives the cold-start rule depends on — were missing.

| tool | purpose |
|---|---|
| `pmoves_cipher_store` | store knowledge with category + tags |
| `pmoves_cipher_search` | search stored memories |
| `pmoves_cipher_store_reasoning` | store a chain-of-thought trace |
| `pmoves_cipher_reasoning_patterns` | retrieve recurring reasoning patterns |
| `pmoves_cipher_session_save` | persist session state |
| `pmoves_cipher_session_recall` | restore prior session state (cold start) |
| `pmoves_cipher_hybrid_search` | combined vector + text search (cipher + HiRAG fusion) |
| `pmoves_cipher_graph_expand` | expand a memory's graph neighbourhood (Neo4j) |
| `pmoves_cipher_mcp_list` | list registered MCP surfaces |
| `pmoves_cipher_mcp_get` | fetch one MCP surface record |

### Categories (nine — the enum is shared by store and search)

- `code_pattern`: Reusable code patterns and conventions
- `decision`: Architectural decisions and rationale
- `context`: Project-specific context
- `submodule`: PMOVES submodule knowledge
- `architecture`: System patterns and design
- `reasoning`: Chain-of-thought reasoning traces
- `agent_plan`: A durable plan an agent can resume from
- `agent_checkpoint`: Mid-work state at a phase boundary
- `agent_completion`: What was actually finished, and what was tried

The last three drive the cold-start pattern above — filter on them so the next
session inherits a plan, a checkpoint, and an honest completion record.

### Store

```
Use pmoves_cipher_store to remember:
- content: The knowledge to store
- agentId: REQUIRED — your signing-card agent_id
- category: one of the nine above
- tags: Optional list; include your node tag (z890, 5090, spark, kvm4-1, ...)
```

Retrieval is per-agent scoped. Under token enforcement you can only see your
own scope; write records your peers need under the shared agent identity your
node's token policy defines.

### Search

```
Use pmoves_cipher_search to find:
- query: Search query
- agentId: REQUIRED — your signing-card agent_id
- category: Optional filter
- limit: Maximum results (default: 10)
```

Queries match stored wording closely (lexical fallback has no vectors).

## Session workflow

1. **Start**: preflight → `session_recall` → scoped search (`agent_checkpoint`)
2. **Work**: store discoveries and decisions as they happen (`Store Early`)
3. **End**: `session_save` a checkpoint with active lanes + context paths
4. **On completion**: store an `agent_completion` record — what was tried,
   what worked, what remains

## Ops quick reference

- `make -C pmoves up-cipher-full` — Qdrant + TensorZero + Ollama + NATS + cipher-api
- `make -C pmoves up-cipher-nobuild` — apply env/port changes without a rebuild
- `make -C pmoves qdrant-provision-cipher` / `qdrant-verify-cipher` — eager
  collection provisioning + dense+BM25+RRF round-trip
- `make -C pmoves cipher-memory-smoke` — end-to-end POST+search, FAILS if the
  vector path is dead
- `make -C pmoves cipher-health` — liveness
- `python pmoves/tools/cipher_roundtrip_probe.py` — authenticated MCP
  initialize/store/search/checkpoint in one shot

## Key principles

- **Store Early**: don't wait — store patterns as you find them
- **Use Categories**: organize by type for retrieval
- **Tag Liberally**: include the node tag so fleet records stay attributable
- **Capture Reasoning**: the "why" is as important as the "what"
- **Search First**: check what's stored before re-discovering
- **Never assume memory**: preflight or it didn't happen
