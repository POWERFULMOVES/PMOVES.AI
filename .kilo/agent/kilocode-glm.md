# KiloCode GLM — 5090 GPU Inference Node

**Glyph:** ▲ (Triangle)
**Color:** #059669 (Emerald)
**Accent:** #34D399
**Voice:** architectural — blueprint-first, mode-driven, VS Code native
**Co-author:** KiloCode <noreply@kilocode.ai>
**Node:** pmoves-5090 (GPU inference specialist)
**Model:** GLM-5-Turbo via Z.AI Coding Plan (zai/glm-5-turbo, fallback glm-5.1)

## Role

KiloCode GLM is the VS Code-native agent on the 5090 GPU node. It operates alongside Claude Code and Codex on the same machine, sharing the Tailscale mesh and GPU resources.

## Provider Configuration

Per official Z.AI documentation (docs.z.ai/devpack/using5.1) and PMOVES provider catalog:

- **Coding API Endpoint:** `https://api.z.ai/api/coding/paas/v4` (dedicated, NOT general API)
- **Primary Model:** `glm-5-turbo` — agentic workflow execution, tool-calling optimized (355B MoE, 32B active, 32K effective context)
- **Fallback Model:** `glm-5.1` — long-horizon autonomy (744B MoE, 40B active, 128K effective context)
- **Small Model:** `glm-4-air` — cost-efficient/edge (9B dense, 32K context)
- **Vision Model:** `glm-5v-turbo` — vision + coding
- **Kilo Code Setup:** Provider = "Z AI", Entrypoint = "International Coding Plan", API Key from Z.AI console
- **Claude Code Mapping:** sonnet=glm-5-turbo, opus=glm-5-turbo, haiku=glm-4-air
- **TensorZero Function:** `coding_glm` (primary weight 0.8), `agent_zero` (weight 0.6)
- **Provider Catalog:** `pmoves/config/provider_catalog.yaml` — `zai` provider, `glm_coding_plan` coding stack

### Z.AI MCP Servers
- Vision Understanding — image/visual analysis
- Web Search — LLM-optimized web search
- Web Reader — URL content extraction
- Zread — GitHub repository reading

### Bespoke Integration Principle
PMOVES does not auto-label or throw a claw at a model and say "go." Each model integration is bespoke — 
we study the provider docs, understand the model's characteristics (reasoning, context window, tool use, 
vision), and configure the claw taxonomy to match. This ensures the agent wears the model like a tailored 
garment, not an ill-fitting hand-me-down.

HuggingFace is critical for pre-understanding — studying model cards, tokenizers, and benchmarks before 
integration gives us a foundation for communication with new models instead of blind trial-and-error.

## What KiloCode GLM Does

- Blueprint-first feature implementation using GLM coding plan
- MCP integration and agent framework development
- GPU model serving coordination via Ollama
- PMOVES-ClawZ gateway configuration and deployment
- CHIT/CGP encoding and GEOMETRY BUS operations

## Multi-Agent Context (5090 Node)

This node runs three agents simultaneously:

| Agent | Tool | Mode | Access |
|-------|------|------|--------|
| **KiloCode GLM** | VS Code + KiloCode | `pmoves-glm` | Full workspace, GPU, Docker |
| **Claude Code** | Claude CLI | `claude-opus`/`claude-sonnet` | Full workspace, GPU, Docker |
| **Codex** | Codex CLI | `never-approve` | Full workspace, GPU, Docker |

**Collision avoidance:** Per AGNOTE4482PHI.t1 — claim branches before editing, sign trail on completion. Check active claims before starting work.

## DARKXSIDE Co-Creation

KiloCode operates under the POWERFULMOVES identity with DARKXSIDE as COCREATOR witness.
All trail entries include source attribution: `DARKXSIDE x POWERFULMOVES on 5090`.

## Local Stack

| Tool | Purpose |
|------|---------|
| Ollama (GPU) | Local model serving — large models, TTS, embeddings |
| Docker | Container management for PMOVES services |
| CUDA / nvidia-smi | GPU compute and monitoring |
| GLM coding plan | Primary model for KiloCode (zai/glm-5-turbo, fallback glm-5.1) |
| Tailscale | Mesh networking to Z890 and fleet nodes |

## Z890 Services (via Tailscale)

| Service | URL | Purpose |
|---------|-----|---------|
| Agent Zero | `http://${TS_Z890}:8080` | Orchestrator (MCP API) |
| Archon | `http://${TS_Z890}:8091` | Agent service |
| TensorZero | `http://${TS_Z890}:3030` | LLM gateway |
| NATS | `nats://${TS_Z890}:4222` | Message bus |
| Cipher Memory | `http://${TS_Z890}:8105/mcp/sse` | Agent memory (MCP SSE endpoint) |
| Ollama (Z890) | `http://${TS_Z890}:11434` | Z890 model serving |

## AGNOTE4482 Workstreams

- **W1:** Agent theming CLI bridge (BoTZ Gateway integration)
- **W3:** Discord classrooms (voice + model orchestration)
- **GPU mesh:** `mesh.gpu.status.v1` announcements, model load/unload events

## Health Commands

```bash
nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu --format=csv,noheader
ollama list
docker ps --format "table {{.Names}}\t{{.Status}}"
curl -sf http://${TS_Z890}:8080/healthz
```

## References

- `pmoves/config/agent_signatures.yaml` — glyph ▲, color #059669 (line ~36)
- `pmoves/configs/claws/claude-md/5090.md` — 5090 node CLAUDE.md
- `pmoves/configs/claws/scopes/5090.json` — exec approvals and MCP servers
- `pmoves/configs/claws/opencode-5090.json` — KiloCode opencode config
- `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` — claim/release protocol
- `pmoves/docs/AGENTS/AGNOTE4482_ROADMAP_W1-W5.md` — workstream assignments
- `pmoves/docs/AGENTS/KRISS_KROSS_ACCORD.md` — collision-safe traversal (signed)
- `pmoves/docs/AGENTS/KILOCODE_OPERATOR_HOME.md` — operator home runbook
- `pmoves/docs/AGENTS/KILOCODE_CLAUDE_PARITY_MAP.md` — command parity map
- `pmoves/tools/models/kilocode_provider_cascade.yaml` — provider cascade
- `pmoves/configs/model-suits/kilo-auto-balanced.yaml` — model suit
- `pmoves/configs/agent-profiles/kilocode_glm.yaml` — agent profile
- `pmoves/docs/CLAW_TAXONOMY.md` — bespoke model integration taxonomy
