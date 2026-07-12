---
name: pmoves-kimi-bootstrap
description: PMOVES-KIMI session bootstrap and model/agent selection guidance for Kimi Code CLI operators.
---

# PMOVES-KIMI Bootstrap Skill

Use this skill when the user starts a Kimi session in PMOVES.AI, asks about PMOVES-KIMI configuration, or needs guidance on which model/agent to use.

## Session start checklist

1. Read `.kimi/AGENTS.md` first — it is the canonical Kimi bootstrap for this project.
2. Disclose reachable vs missing MCPs:
   - `pmoves-cipher`
   - `docker`
   - `pmoves-docker-gateway`
   - `pmoves-nats-fleet`
   - `pmoves-e2b`
   - `pmoves-supabase`
   - `huggingface`
3. Confirm launch was via `make -C pmoves kimi`. If not, warn that the project config/MCP set may not be loaded.
4. Check `CHIT_PASSPHRASE` availability for provenance signing.

## Model selection rules

| User need | Suggest |
|---|---|
| General PMOVES development | `pmoves/qwen3.5-35b` (local) or `kimi-for-coding` (remote) |
| Large multi-file refactor / architecture | `kimi-k2.7-code` or `pmoves/hermes-v4-70b` |
| Security / hardening review | `pmoves/hermes-v4-70b` or `kimi-k2.7-code` |
| Fast edge / sub-agent task | `pmoves/hermes-v4-8b` or `pmoves/llama3.2-3b` |
| Voice / persona generation | TensorZero-routed voice providers via Agent Zero |

## Agent ecosystem pointers

- **Agent Zero** is the top-level orchestrator. Use `http://localhost:8080/mcp/command` for delegation, don't duplicate orchestration logic.
- **Claw / ACP** routes harness requests. Kimi is already mapped as `agentId: "kimi"` in `PMOVES-ClawZ/extensions/acpx/skills/acp-router/SKILL.md`.
- **Botz Gateway** tracks BoTZ instances and work items via REST/NATS, not MCP.

## Common commands

```bash
# Launch Kimi with PMOVES context
make -C pmoves kimi

# Test an MCP server
kimi mcp test pmoves-cipher

# Sign a trail entry
CHIT_PASSPHRASE=... make -C pmoves sign-trail AGENT=kimi SUMMARY="..."

# Browser / computer use (E2B Surf)
make -C pmoves surf-up   # needs E2B_API_KEY + OPENAI_API_KEY

# Danger Room desktop sandbox
make -C pmoves danger-room-desktop-up   # needs E2B_API_KEY

# Build a container with Danger Room theme fanfare
make -C pmoves danger-room-build IMAGE=agent-zero
```
