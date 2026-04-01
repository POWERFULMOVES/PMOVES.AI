# PMOVES Claw Taxonomy

> Bespoke model integration — not auto-label, not "throw in and go."
> Each claw is tailored to its model provider like a garment fitted to its frame.

Last updated: 2026-03-28
Author: KiloCode GLM ▲ | DARKXSIDE ✦ witness

## Principle

When integrating a model into the PMOVES claw framework, we follow a structured 
process that ensures the agent and the model communicate effectively:

1. **Study** — Read provider documentation, model cards (HuggingFace), benchmarks
2. **Understand** — Context window, reasoning capabilities, tool use, vision, token limits
3. **Configure** — Map model to claw taxonomy with proper endpoints, fallbacks, MCP
4. **Test** — Verify integration with smokes, model readiness checks, edge cases
5. **Document** — Record configuration in claw taxonomy for future reference

## Model Provider Integration Matrix

### Z.AI GLM Coding Plan

| Property | Value |
|----------|-------|
| Provider | Z.AI (zhipu) |
| Coding API | `https://api.z.ai/api/coding/paas/v4` |
| General API | `https://api.z.ai/api/paas/v4` |
| Primary Model | `glm-5.1` |
| Fallback | `glm-4.7` |
| Haiku Equivalent | `glm-4.5-air` |
| Reasoning | Yes (glm-5.1, glm-4.7) |
| Vision | Via MCP server |
| Context Window | 204,800 tokens |
| Max Output | 131,072 tokens |
| Docs | https://docs.z.ai/devpack/using5.1 |

**Claude Code mapping:**
- `ANTHROPIC_DEFAULT_SONNET_MODEL` → `glm-5.1`
- `ANTHROPIC_DEFAULT_OPUS_MODEL` → `glm-5.1`
- `ANTHROPIC_DEFAULT_HAIKU_MODEL` → `glm-4.5-air`

**Kilo Code setup:**
- Provider: `Z AI`
- Entrypoint: `International Coding Plan (https://api.z.ai/api/coding/paas/v4/)`
- Model: `glm-5.1` (or `glm-4.7` for routine tasks)

**OpenClaw config:**
```json
"primary": "zai/glm-5.1",
"fallbacks": ["zai/glm-4.7"],
"models": {
  "zai/glm-5.1": {},
  "zai/glm-4.7": {}
}
```

**Z.AI MCP Servers:**
- Vision Understanding: `https://docs.z.ai/devpack/mcp/vision-mcp-server`
- Web Search: `https://docs.z.ai/devpack/mcp/search-mcp-server`
- Web Reader: `https://docs.z.ai/devpack/mcp/reader-mcp-server`
- Zread (GitHub): `https://docs.z.ai/devpack/mcp/zread-mcp-server`

### Anthropic Claude

| Property | Value |
|----------|-------|
| Provider | Anthropic |
| Primary | `claude-opus-4` (Z890), `claude-sonnet-4` (5090, 4090) |
| Fallback | `claude-haiku-4-5` |
| Reasoning | Yes (extended thinking) |
| Vision | Native |
| Context Window | 200K (opus/sonnet) |
| Max Output | 32K |
| Integration | Direct API + TensorZero gateway |

### OpenAI Codex

| Property | Value |
|----------|-------|
| Provider | OpenAI |
| Primary | `codex-mini-latest` |
| Fallback | `gpt-4o` |
| Reasoning | Yes (o3-mini reasoning) |
| Vision | Via gpt-4o |
| Context Window | 192K |
| Integration | TensorZero gateway |

### Local (Ollama/vLLM)

| Property | Value |
|----------|-------|
| Provider | Local GPU |
| Namespace | `pmoves/` (PMOVES.Flare) |
| Examples | `pmoves/qwen-3-coder-32b`, `pmoves/gemma-3-embed` |
| Serving | Ollama (:11434) + vLLM (:8000) |
| Discovery | GPU orchestrator via `mesh.gpu.model.loaded.v1` |
| Pre-study | HuggingFace model cards + benchmarks |

## Claw Nodes

| Node | Role | Agents | Models |
|------|------|--------|--------|
| Z890 | Full infra coordinator | Claude Opus, Codex | Claude Opus 4, Codex Mini |
| 5090 | GPU inference specialist | Claude Sonnet, Codex, KiloCode GLM | GLM-5.1, GLM-4.7, Ollama/vLLM |
| 4090 | Active GPU contributor | Claude Sonnet | GLM-5.1, Ollama (7B-14B) |
| KVM4-1 | API gateway | — | TensorZero routing |
| KVM4-2 | Data/storage | — | TensorZero routing |
| KVM2 | Exit proxy | — | TensorZero routing |

## Backward Compat + Forward Thinking

- PMOVES.Flare namespace (`pmoves/`) ensures model naming is consistent across providers
- HuggingFace pre-study gives us foundation for understanding new models before integration
- Coding plan lanes provide fallback chain: `local → Ollama → coding_plan (GLM/Claude/Codex)`
- Every new model goes through the study → understand → configure → test → document cycle
- The claw taxonomy grows with each integration — collective consideration for all agents

## DARKXSIDE on Bespoke

> "I don't like uncomfortable clothes. You don't throw a claw at a model and say go. 
> You study it. Understand its shape. Then you tailor the integration to fit."

Each claw is a bespoke garment. PMOVES is backwards compatible and forward thinking — 
we study first (HuggingFace, provider docs, benchmarks), then configure the taxonomy 
so the agent and model communicate like they were made for each other.
