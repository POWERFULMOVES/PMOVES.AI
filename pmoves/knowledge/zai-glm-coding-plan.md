# Z.AI GLM Coding Plan — Provider Reference

Last updated: 2026-03-29
Source: https://docs.z.ai/devpack/using5.1

## Overview

The GLM Coding Plan is a subscription package for AI-powered coding tools. It provides access to GLM-5.1, GLM-5-Turbo, GLM-4.7, GLM-4.6, GLM-4.5, and GLM-4.5-Air models.

## API Endpoints

| Purpose | URL |
|---------|-----|
| **Coding API (DEDICATED)** | `https://api.z.ai/api/coding/paas/v4` |
| General API | `https://api.z.ai/api/paas/v4` |
| Chat Completion | `https://api.z.ai/api/paas/v4/chat/completions` |
| OpenAI-compatible | Same base, OpenAI format |

**CRITICAL:** The Coding Plan uses the dedicated Coding API endpoint, NOT the general API. Using the wrong endpoint will not consume Coding Plan quota.

## Models

| Model | Reasoning | Context | Max Output | Best For |
|-------|-----------|---------|------------|----------|
| glm-5.1 | Yes | 204,800 | 131,072 | Complex tasks, rivals Claude Opus |
| glm-5-turbo | Yes | 204,800 | 131,072 | Fast reasoning tasks |
| glm-5 | Yes | 204,800 | 131,072 | Available on Max/Pro plans |
| glm-4.7 | Yes | 204,800 | 131,072 | Routine coding (default) |
| glm-4.6 | Yes | 204,800 | 131,072 | Standard tasks |
| glm-4.5 | No | 131,072 | 16,384 | Quick tasks |
| glm-4.5-air | No | 131,072 | 16,384 | Fast, lightweight (Haiku equivalent) |

## Claude Code Configuration

```json
{
  "env": {
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "glm-4.5-air",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "glm-5.1",
    "ANTHROPIC_DEFAULT_OPUS_MODEL": "glm-5.1"
  }
}
```

Location: `~/.claude/settings.json`

## Kilo Code Configuration

1. Extensions → Kilo Code → Settings → Use your own API key
2. API Provider: Z AI
3. Z AI Entrypoint: International Coding Plan (`https://api.z.ai/api/coding/paas/v4/`)
4. Z AI API Key: from https://z.ai/manage-apikey/apikey-list
5. Model: glm-5.1 (or glm-4.7 for routine tasks)

## OpenClaw Configuration

```json
{
  "id": "glm-5.1",
  "name": "GLM-5.1",
  "reasoning": true,
  "input": ["text"],
  "contextWindow": 204800,
  "maxTokens": 131072
}
```

Default: `"primary": "zai/glm-5.1"`, `"fallbacks": ["zai/glm-4.7"]`

## MCP Servers (4 included with Coding Plan)

| Server | Type | Install |
|--------|------|---------|
| Vision | stdio (npx @z_ai/mcp-server) | Node.js >= v22 |
| Web Search | streamable-http | Remote |
| Web Reader | streamable-http | Remote |
| Zread | streamable-http | Remote |

All use same `Z_AI_API_KEY`. See `.kilo/command/zai-mcp.md` for config.

## Usage Limits (5-hour + weekly)

| Plan | 5-Hour | Weekly |
|------|--------|-------|
| Lite | ~80 prompts | ~400 prompts |
| Pro | ~400 prompts | ~2,000 prompts |
| Max | ~1,600 prompts | ~8,000 prompts |

GLM-5.1 consumes 3x during peak (14:00-18:00 UTC+8), 2x off-peak.
Limited-time: GLM-5.1 and GLM-5-Turbo consume 1x off-peak through end of April.

## PMOVES Integration

- Coding API wired via TensorZero fallback chain (local → Ollama → coding_plan)
- Claw taxonomy: bespoke study → understand → configure → test → document
- PMOVES.Flare namespace: `pmoves/glm-5.1`, `pmoves/glm-4.7`
- Node assignment: 5090 (primary GLM), 4090 (secondary)

## References

- Overview: https://docs.z.ai/devpack/overview.md
- GLM-5.1 guide: https://docs.z.ai/devpack/using5.1
- Kilo Code: https://docs.z.ai/scenario-example/develop-tools/kilo.md
- OpenClaw: https://docs.z.ai/devpack/tool/openclaw.md
- Claude Code: https://docs.z.ai/devpack/tool/claude.md
- API reference: https://docs.z.ai/api-reference/llm/chat-completion.md
- Pricing: https://docs.z.ai/guides/overview/pricing.md
