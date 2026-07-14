# KiloCode + HuggingFace MCP Convergence Plan

> **For:** 5090 KiloCode operator and fleet coordinators.
> **Status:** PROPOSED — needs 5090 operator confirmation.
> **Date:** 2026-07-14

## Current State

- **5090 KiloCode** is working on HuggingFace MCP integration
- **Elder-Melchor Hermes** has Docker MCP Gateway with HuggingFace tools (167 tools)
- **Topology matrix** (PR #2111) documents that 5090 uses `opencode-5090.json` config
- **Kimi MCP config** (PR #2112) now has Cipher + Agent Zero via Tailscale

## Convergence Actions

### 1. Align HuggingFace MCP Server

Both nodes should use the same MCP server package:

| Node | Current | Target |
|------|---------|--------|
| 5090 (KiloCode) | `@llmindset/hf-mcp-server@0.3.30` | Same — pinned |
| Elder-Melchor (Hermes) | Docker MCP Gateway (hugging-face) | Same Docker MCP or `@llmindset/hf-mcp-server@0.3.30` via npx |

### 2. Share HF_TOKEN Securely

- HF_TOKEN should be in `pmoves/env.shared` (gitignored) — NOT committed
- KiloCode on 5090 reads from `kilo.json` env section
- Hermes on Elder-Melchor reads from Docker MCP gateway config
- **Rule:** Never commit HF_TOKEN. Use env var reference `${HF_TOKEN}`.

### 3. Document KiloCode MCP Access

Update `pmoves/configs/claws/opencode-5090.json` to include:
- `pmoves-cipher`: SSE at `${TS_Z890}:8105/mcp/sse` (already present, path fixed in #2112)
- `huggingface`: `@llmindset/hf-mcp-server@0.3.30` (already pinned in #2085)
- `agent-zero`: HTTP at `${TS_Z890}:8080/mcp` (already present)

### 4. Align with Topology Matrix

The topology matrix (PR #2111) documents the canonical mapping:
- 5090 → KiloCode primary, glm-5.2 model, Z.AI provider only
- 5090 → Claude Code secondary, opus model, Anthropic only
- 5090 → Hermes tertiary, any provider (fallback)

KiloCode on 5090 should verify it matches the matrix and report any discrepancies.

### 5. BoTZ Gateway Alignment

When BoTZ Gateway deploys on KVM4-1 (Task 5), 5090's KiloCode should switch from direct Tailscale connections to the BoTZ Gateway endpoint:
- `pmoves-cipher`: `${TS_KVM4}:8054/cipher/sse` (via BoTZ)
- `agent-zero`: `${TS_KVM4}:8054/agent-zero` (via BoTZ)
- `huggingface`: `${TS_KVM4}:8054/huggingface` (via BoTZ)

This centralizes MCP access through a single gateway endpoint.