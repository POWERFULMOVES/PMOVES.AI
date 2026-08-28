# PMOVES.AI Agent Topology Matrix — Harness, Tooling, Roles

> **For:** All agents and operators entering PMOVES lanes.
> **Status:** CANONICAL — the single source of truth for agent/harness/node/tool mapping.
> **Last updated:** 2026-07-12
> **Owner:** hermes-agent

---

## 1. Harness Matrix — Per-Agent Stack

### 1.1 Claude Code (◆)

| Property | Value |
|----------|-------|
| **Models** | opus (primary), sonnet, haiku — **Anthropic only** |
| **Restrictions** | Cannot use Z.AI, Kimi, MiniMax, or DeepSeek |
| **MCP** | `.claude/mcp.json` — Cipher, Docker, Supabase, Tailscale, HuggingFace |
| **Agents** | `.claude/agents/*.md` — Three-Body delivery/control/memory + specialists |
| **Bootstrap** | `claude` (direct), `claude-pmoves` (planned wrapper) |

### 1.2 KiloCode (▲)

| Property | Value |
|----------|-------|
| **Models** | glm-5.2, glm-5-turbo, glm-5.1, glm-4-air — **Z.AI only** |
| **Restrictions** | Cannot use Claude, OpenAI, or Anthropic |
| **MCP** | `kilo.json` — Cipher (`${TS_Z890}:8105/mcp/sse`), Tailscale, HuggingFace |
| **Node** | 5090 (primary, GPU inference workhorse) |

### 1.3 Kimi (●)

| Property | Value |
|----------|-------|
| **Models** | kimi-k2.7-code (Moonshot), qwen3.5 (local Ollama) |
| **Restrictions** | Moonshot + Ollama only |
| **MCP** | `.kimi/mcp.json` (planned) |
| **Bootstrap** | `make -C pmoves kimi` |

### 1.4 Hermes Agent (⚕)

| Property | Value |
|----------|-------|
| **Models** | zai-coding → kimi → minimax-oauth → openrouter → ollama-cloud |
| **Restrictions** | **None — provider-agnostic, 30+ providers** |
| **MCP** | Docker MCP Gateway (167 tools) |
| **Profile** | `pmoves-hermes-elder` on Elder-Melchor |

### 1.5 Codex (■)

| Property | Value |
|----------|-------|
| **Models** | codex (GPT-5.4) — **OpenAI only** |
| **Node** | Floating (no fixed node) |

---

## 2. Node × Agent × Model × MCP Matrix

| Node | Role | Agents | Primary Model | MCP Access | Local Services |
|------|------|--------|-------------|------------|----------------|
| **Z890** | Infra/CI | Claude (primary), Hermes, Kimi | claude-opus | Cipher (local), Docker, Supabase, Tailscale, HF | Neo4j, NATS, Cipher, Agent Zero, TensorZero, Hi-RAG, Supabase, Monitoring |
| **5090** | GPU inference | KiloCode (primary), Claude, Hermes | glm-5.2 | Cipher (TS_Z890), Tailscale, HF, Agent Zero | Ollama, TensorZero, Hi-RAG GPU |
| **4090** | Field/laptop | Claude, Hermes, Kimi | claude-sonnet-4 | Cipher (TS_Z890), Agent Zero | Ollama (light) |
| **Elder-Melchor** | Hermes gateway | Hermes (primary), Kimi | zai-coding | Docker MCP (167 tools), Cipher (TS_Z890 → local planned) | Ollama, (Neo4j+NATS+Cipher planned) |
| **SPARK** | Edge 70B | Hermes, Codex | hermes3:70b | Cipher (TS_Z890) | Ollama (70B), NeMo |
| **B850** | AMD ROCm | Claude, Hermes | hermes3:8b (ROCm) | Cipher (TS_Z890) | Ollama (ROCm) |
| **KVM4-1** | VPS gateway | Claude, Hermes | claude-sonnet-4 | Cipher (TS_Z890), Agent Zero, Supabase | **BoTZ Gateway (8054)**, NATS leaf, CI runner |
| **KVM4-2** | Data/storage | Claude | claude-sonnet-4 | Cipher (local) | Storage tier |
| **KVM2** | Exit proxy | Claude (light) | claude-haiku-4-5 | None | Network only |

---

## 3. Harness Model Restrictions

| Harness | Allowed | Blocked | Routing Rule |
|---------|---------|---------|-------------|
| Claude Code | opus, sonnet, haiku | Z.AI, Kimi, MiniMax | Route to Claude for deep reasoning/security |
| KiloCode | glm-5.2, glm-5-turbo | Claude, OpenAI | Route to KiloCode for agentic coding on Z.AI plan |
| Kimi | kimi-k2.7-code, qwen3.5 | Claude, Z.AI | Route to Kimi for long-context (128K+) tasks |
| Hermes | Any (30+) | None | Route to Hermes for multi-provider fallback |
| Codex | codex (GPT-5.4) | Claude, Z.AI | Route to Codex for GitHub/PR automation |

---

## 4. BoTZ Gateway — Central MCP Hub

BoTZ Gateway (port 8054) runs on KVM4-1 (VPS) and aggregates all MCP servers for fleet-wide access.

| MCP Server | Port | Protocol | Exposed Via |
|------------|------|----------|------------|
| Cipher Memory | 8105 | SSE | BoTZ Gateway |
| Agent Zero | 8080 | HTTP | BoTZ Gateway |
| Supabase | 8000 | HTTP | BoTZ Gateway |
| TensorZero | 3030 | HTTP | BoTZ Gateway |
| Hi-RAG | 8086 | HTTP | BoTZ Gateway |
| NATS | 4222 | TCP | Direct (mesh) |
| GitHub MCP | — | stdio | BoTZ (token minting) |

---

## 5. Bootstrap Aliases Needed

| Alias | Command | Status |
|-------|---------|--------|
| `claude-pmoves` | `claude --agent delivery-agent` | **Needed** |
| `kilo-pmoves` | `kilo --agent kilocode-glm` | **Needed** |
| `hermes-pmoves` | `hermes -p pmoves-hermes-elder` | ✅ Exists |
| `codex-pmoves` | `codex --config .codex/` | **Needed** |
| `make -C pmoves kimi` | Kimi with PMOVES context | ✅ Exists |
| `make -C pmoves claude` | Claude with PMOVES context | **Needed** |
| `make -C pmoves kilo` | KiloCode with PMOVES context | **Needed** |

---

## 6. Convergence Action Items

1. **Fix opencode configs**: `/sse` → `/mcp/sse` in all `pmoves/configs/claws/opencode-*.json`
2. **Create `claude-pmoves`** bootstrap wrapper script
3. **Create `.kimi/mcp.json`** with Cipher + Agent Zero MCP servers
4. **Deploy BoTZ Gateway on KVM4-1** with all MCP servers
5. **Implement local Cipher** on Elder-Melchor (Phase 1 of cipher arch)
6. **Create make targets**: `make -C pmoves claude`, `make -C pmoves kilo`
7. **Document TensorZero function mapping** per harness
8. **Configure fallback chains** per harness per node