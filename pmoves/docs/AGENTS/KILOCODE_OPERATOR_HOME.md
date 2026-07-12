# KiloCode Operator Home (PMOVES)
_Last updated: 2026-07-11_

This is the KiloCode-first operations guide for PMOVES.AI. It mirrors the mature
Claude and Codex setups, but keeps KiloCode workflows blueprint-first and VS Code-native.

KiloCode GLM (glyph ▲, color #059669) is the third agentic interface on the 5090 node,
alongside Claude Code and Codex. It uses GLM-5.2 via Z.AI coding plan as primary model.

## Identity

| Property | Value |
|----------|-------|
| Glyph | ▲ (Triangle) |
| Color | #059669 (Emerald) |
| Accent | #34D399 |
| Voice | architectural — blueprint-first, mode-driven |
| Node | pmoves-5090 (desktop-9950xd) |
| Model | GLM-5.2 (zai/glm-5.2, fallback glm-5-turbo) |
| COCREATOR | DARKXSIDE ✦ |

## Runtime signaling

- Use `pmoves-glm` mode for blueprint-first implementation.
- Use `pmoves-code` mode for general service development.
- Use `pmoves-architect` mode for system design and orchestration planning.
- Use `pmoves-cocreate` mode for DARKXSIDE creative co-authorship.
- See all 11 modes in `.kilocodemodes`.

## KRISS KROSS lane roles

- `KiloCode GLM` lead mode: blueprint-first implementation, MCP integration, GPU model serving.
- `Claude` in KiloCode-led windows: analysis, review, field brief authoring.
- `Codex` in KiloCode-led windows: terse code generation, integration tasks.
- Use overlay handoff rules from `pmoves/docs/AGENTS/KRISS_KROSS_ACCORD.md` when scopes intersect.
- KiloCode signed: `ACK::KILOCODE-GLM::KRISS-KROSS-ACCORD::2026-07-11`

## Three-Body Declaration

KiloCode defaults to **Delivery Body** (execution lane):
```
Three-body: delivery=KILOCODE-GLM, control=DARKXSIDE, memory=this trail.
```

All trail entries carry dual attribution: `▲ KiloCode GLM` + `✦ DARKXSIDE`.
Source line: `DARKXSIDE x POWERFULMOVES on 5090`.

## Bootstrap

1. Verify coding plan key is set: `echo $Z_AI_API_KEY`
2. Start VS Code with KiloCode extension
3. Default agent: `kilocode-glm` (set in `kilo.json`)
4. Default model: `zai/glm-5.2` (with `glm-5-turbo` fallback)
5. Open this runbook for reference

## Ecosystem traversal

KiloCode should traverse the existing PMOVES surfaces in this order:

1. Operator lane: this runbook
2. Service map: `.claude/CLAUDE.md`
3. Submodule map: `.claude/context/submodules.md`
4. Model routing: `pmoves/tools/models/kilocode_provider_cascade.yaml`
5. Agent profile: `pmoves/configs/agent-profiles/kilocode_glm.yaml`
6. Memory path: Cipher MCP at `http://localhost:8105/sse`
7. Persona + voice path: `pmoves/docs/AGENTS/PERSONAS.md`

## MCP Servers

| Server | Type | Purpose |
|--------|------|---------|
| `zai-vision` | local | GLM-5V-Turbo vision analysis, OCR, UI-to-code |
| `zai-web-search` | remote | LLM-optimized web search |
| `zai-web-reader` | remote | Full webpage content extraction |
| `zai-zread` | remote | GitHub repo search and file reading |
| `pmoves-cipher` | remote | Agent memory (Neo4j knowledge graph) |
| `tailscale` | local | Tailnet inventory, stale-node cleanup, ACL ops |
| `huggingface` | local | HF model/dataset/spaces search |
| `docker` | local | Container inspection via Docker socket |

## Z.AI MCP Server Rate Limits

Per Z.AI documentation (`.kilo/command/zai-mcp.md`):

| Server | Rate Limit | Window |
|--------|-----------|--------|
| Web Search | 30 requests/min | rolling |
| Web Reader | 30 requests/min | rolling |
| Zread | 30 requests/min | rolling |
| Vision | 10 requests/min | rolling (heavier compute) |

## Provider Configuration

### Primary: Z.AI Coding Plan
- **Endpoint:** `https://api.z.ai/api/coding/paas/v4`
- **API Key:** `${Z_AI_API_KEY}`
- **Models:** glm-5.2 (primary), glm-5-turbo (agentic), glm-5.1 (reasoning), glm-5v-turbo (vision), glm-4-air (fast)

### Secondary: KiloCode Plan
- **Endpoint:** `https://api.kilocode.ai/api/openrouter`
- **API Key:** `${KILOCODE_API_KEY}`
- **Model:** `kilo-auto/balanced` (provider picks model)

### Tertiary: Ollama Cloud
- **Endpoint:** `https://ollama.com/v1`
- **API Key:** `${OLLAMA_API_KEY}`
- **Model:** `glm-5.2`

### TensorZero Routing
- **Gateway:** `http://localhost:3030`
- **Primary function:** `coding_glm` (weight 0.8 for GLM-5-Turbo)
- **KiloCode function:** `coding_kilocode` (weight 0.7 for kilo-auto/balanced)
- **Orchestrator:** `pmoves_orchestrator_coding` (weight 0.3 for kilo-auto/balanced)

## Health Commands

```bash
# GPU status
nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu --format=csv,noheader

# Local models
ollama list

# Container status
docker ps --format "table {{.Names}}\t{{.Status}}"

# Remote services (via Tailscale)
curl -sf http://${TS_Z890}:8080/healthz  # Agent Zero
curl -sf http://${TS_Z890}:3030/health   # TensorZero
curl -sf http://${TS_Z890}:8105/health   # Cipher Memory

# Z.AI coding plan check
curl -s https://api.z.ai/api/coding/paas/v4/models \
  -H "Authorization: Bearer $Z_AI_API_KEY"
```

## Local Stack

| Tool | Purpose |
|------|---------|
| Ollama (GPU) | Local model serving — large models, TTS, embeddings |
| Docker | Container management for PMOVES services |
| CUDA / nvidia-smi | GPU compute and monitoring |
| GLM coding plan | Primary model (zai/glm-5.2, fallback glm-5-turbo) |
| Tailscale | Mesh networking to Z890 and fleet nodes |

## Z890 Services (via Tailscale)

| Service | URL | Purpose |
|---------|-----|---------|
| Agent Zero | `http://${TS_Z890}:8080` | Orchestrator (MCP API) |
| Archon | `http://${TS_Z890}:8091` | Agent service |
| TensorZero | `http://${TS_Z890}:3030` | LLM gateway |
| NATS | `nats://${TS_Z890}:4222` | Message bus |
| Cipher Memory | `http://${TS_Z890}:8105/sse` | Agent memory (MCP SSE) |
| Ollama (Z890) | `http://${TS_Z890}:11434` | Z890 model serving |

## Claim/Release Protocol

Before any edit to a shared branch:

1. **Check** Active Claim Register in `AGNOTE4482PHI.t1.md`
2. **CLAIM** with branch + scope + TTL
3. **Work** and update progress in PR comments
4. **RELEASE** with next_actions and signed ACK

```
<ISO-8601> CLAIM `KILOCODE-GLM` scope: <description>.
  branch: `<name>`. pr_numbers: [#<n>].
  agent_signature: `ACK::KILOCODE-GLM::<SCOPE>`.
  Three-body: delivery=KILOCODE-GLM, control=DARKXSIDE, memory=this trail.
```

## References

- `pmoves/config/agent_signatures.yaml` — glyph ▲, color #059669
- `pmoves/tools/models/kilocode_provider_cascade.yaml` — provider cascade
- `pmoves/configs/agent-profiles/kilocode_glm.yaml` — agent profile
- `pmoves/configs/model-suits/glm-5.2.yaml` — model suit
- `pmoves/configs/claws/opencode-5090.json` — KiloCode node config
- `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` — claim/release protocol
- `pmoves/docs/AGENTS/KRISS_KROSS_ACCORD.md` — collision-safe traversal
- `pmoves/docs/AGENTS/KRISS_KROSS_ACK.md` — DARKXSIDE attestation
- `pmoves/docs/AGENTS/DARKXSIDE_SIGNATURE.md` — COCREATOR witness
- `pmoves/docs/AGENTS/AGNOTE4482_ROADMAP_W1-W5.md` — workstream assignments

<!-- GRAPHITI_MARK: KILOCODE-GLM::OPERATOR-HOME::2026-07-11 -->
