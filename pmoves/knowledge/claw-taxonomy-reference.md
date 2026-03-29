# PMOVES Claw Taxonomy — Reference

Last updated: 2026-03-29
Author: KiloCode GLM ▲ | DARKXSIDE ✦

## Bespoke Integration Principle

Every model integration in PMOVES follows a structured process:

1. **Study** — Provider docs, HuggingFace model cards, benchmarks
2. **Understand** — Context window, reasoning, tool use, vision, token limits
3. **Configure** — Map to claw taxonomy with proper endpoints and fallbacks
4. **Test** — Smokes, model readiness checks, edge cases
5. **Document** — Record in taxonomy for all agents

## Provider Matrix

### Z.AI GLM (Coding Plan)
- Endpoint: `https://api.z.ai/api/coding/paas/v4`
- Primary: glm-5.1 (204K context, reasoning)
- Fallback: glm-4.7
- MCP: Vision, Web Search, Web Reader, Zread
- Docs: https://docs.z.ai/devpack/using5.1

### Anthropic Claude
- Primary: claude-opus-4 (Z890), claude-sonnet-4 (5090/4090)
- Fallback: claude-haiku-4-5
- Native vision, extended thinking
- Integration: Direct API + TensorZero

### OpenAI Codex
- Primary: codex-mini-latest
- Fallback: gpt-4o
- Integration: TensorZero gateway

### Local GPU (Ollama + vLLM)
- Namespace: pmoves/ (PMOVES.Flare)
- Examples: pmoves/qwen-3-coder-32b, pmoves/gemma-3-embed
- Discovery: GPU orchestrator via mesh.gpu.model.loaded.v1
- Pre-study: HuggingFace model cards

## Claw Nodes

| Node | Role | Primary Models |
|------|------|---------------|
| Z890 | Full infra coordinator | Claude Opus 4, Codex |
| 5090 | GPU inference specialist | GLM-5.1, Ollama/vLLM |
| 4090 | Active GPU contributor | GLM-5.1, Ollama (7-14B) |

## PMOVES.Flare Namespace Convention

Model names: `pmoves/<family>/<variant>`
Example: `pmoves/glm-5.1`, `pmoves/qwen-3-coder-32b`

## Coding Plan Lanes (fallback chain)

`local → Ollama Cloud → coding_plan (GLM/Claude/Codex)`

## References

- Full taxonomy: pmoves/docs/CLAW_TAXONOMY.md
- Model namespace: pmoves/configs/flare-model-namespace.yaml
- Provider catalog: pmoves/config/provider_catalog.yaml
- GPU models: pmoves/config/gpu-models.yaml
