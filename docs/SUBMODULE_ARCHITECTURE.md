# PMOVES.AI Submodule Architecture

**Last Updated**: 2026-02-12
**Repository**: https://github.com/POWERFULMOVES/PMOVES.AI

## Overview

PMOVES.AI is a monorepo containing 45+ submodules that form a distributed AI agent ecosystem. Each submodule is a standalone service that can operate independently or integrate with the parent PMOVES.AI infrastructure.

## Design Principles

### Git vs Runtime Integration

**Git Submodules = Code Ownership**
- Each service owns its codebase via a git submodule
- Enables version tracking and independent development
- Follows "fork and contribute" pattern for improvements

**Networking Integrations = Runtime Collaboration**
- Services connect via NATS, gRPC, HTTP in runtime modes
- **Standalone**: Services run independently with local resources
- **Docked**: Services connect to parent infrastructure (TensorZero, NATS, Qdrant)
- **Hybrid**: Services mix local and parent resources

> **Critical**: PMOVES-Wealth hosting PMOVES-DoX as a "hologram" is a NETWORKING integration, not a git submodule relationship.

## Root-Level Submodules (39 Total)

### Core Agent & Orchestration (4)

| Submodule | Purpose | Branch |
|-----------|---------|--------|
| PMOVES-Agent-Zero | Master orchestrator & planner | PMOVES.AI-Edition-Hardened |
| PMOVES-Archon | Knowledge manager with RAG | PMOVES.AI-Edition-Hardened |
| PMOVES-BoTZ | Bot orchestration & MCP gateway | PMOVES.AI-Edition-Hardened |
| PMOVES-BotZ-gateway | MCP gateway for BotZ | PMOVES.AI-Edition-Hardened |

### Knowledge & Research (4)

| Submodule | Purpose | Branch |
|-----------|---------|--------|
| PMOVES-A2UI | Agent-to-User Interface | PMOVES.AI-Edition-Hardened |
| PMOVES-Deep-Serch | Deep search capabilities | PMOVES.AI-Edition-Hardened |
| PMOVES-HiRAG | Hierarchical RAG implementation | PMOVES.AI-Edition-Hardened |
| Pmoves-hyperdimensions | Geometric visualization | PMOVES.AI-Edition-Hardened |

### Agent Training (4)

| Submodule | Purpose | Branch |
|-----------|---------|--------|
| PMOVES-AgentGym | Agent training platform | PMOVES.AI-Edition-Hardened |
| Pmoves-AgentGym-RL | RL-based agent training | PMOVES.AI-Edition-Hardened |
| PMOVES-llama-throughput-lab | LLM throughput testing | PMOVES.AI-Edition-Hardened |
| PMOVES-surf | Web crawling & research | PMOVES.AI-Edition-Hardened |

### E2B Danger Room (5)

| Submodule | Purpose | Branch |
|-----------|---------|--------|
| PMOVES-E2B-Danger-Room | Sandboxed code execution | PMOVES.AI-Edition-Hardened |
| PMOVES-E2B-Danger-Room-Desktop | Desktop sandbox environment | PMOVES.AI-Edition-Hardened |
| pmoves-e2b-mcp-server | MCP server for E2B | PMOVES.AI-Edition-Hardened |
| PMOVES-Danger-infra | Infrastructure for Danger Room | PMOVES.AI-Edition-Hardened |
| PMOVES-E2b-Spells | E2B spells/actions | PMOVES.AI-Edition-Hardened |

### Voice & Speech (4)

| Submodule | Purpose | Branch |
|-----------|---------|--------|
| PMOVES-Pipecat | Audio/video pipeline | PMOVES.AI-Edition-Hardened |
| PMOVES-Pinokio-Ultimate-TTS-Studio | TTS with Pinokio | PMOVES.AI-Edition-Hardened |
| PMOVES-Ultimate-TTS-Studio | Ultimate TTS implementation | PMOVES.AI-Edition-Hardened |
| PMOVES-transcribe-and-fetch | Audio transcription | PMOVES.AI-Edition-Hardened |

### Media & Content (3)

| Submodule | Purpose | Branch |
|-----------|---------|--------|
| PMOVES.YT | YouTube integration | PMOVES.AI-Edition-Hardened |
| PMOVES-Jellyfin | Media server | PMOVES.AI-Edition-Hardened |
| Pmoves-Jellyfin-AI-Media-Stack | AI-powered media processing | PMOVES.AI-Edition-Hardened |

### Knowledge Base (2)

| Submodule | Purpose | Branch |
|-----------|---------|--------|
| PMOVES-Open-Notebook | Note-taking system (fork of lfnovo/open-notebook) | PMOVES.AI-Edition-Hardened |

### Document Processing (2)

| Submodule | Purpose | Branch |
|-----------|---------|--------|
| PMOVES-DoX | Document intelligence platform | PMOVES.AI-Edition-Hardened |
| PMOVES-Creator | Content creation tools | PMOVES.AI-Edition-Hardened |

### Workflow & Automation (2)

| Submodule | Purpose | Branch |
|-----------|---------|--------|
| PMOVES-n8n | Workflow automation | PMOVES.AI-Edition-Hardened |
| PMOVES-crush | Task processing | PMOVES.AI-Edition-Hardened |

### LLM Gateway (1)

| Submodule | Purpose | Branch |
|-----------|---------|--------|
| PMOVES-tensorzero | LLM gateway & orchestration | PMOVES.AI-Edition-Hardened |

### Financial & Health (3)

| Submodule | Purpose | Branch |
|-----------|---------|--------|
| PMOVES-Wealth | Financial management (renamed from PMOVES-Firefly-iii) | PMOVES.AI-Edition-Hardened |
| Pmoves-Health-wger | Health & workout tracking | PMOVES.AI-Edition-Hardened |

### UI & Frontend (1)

| Submodule | Purpose | Branch |
|-----------|---------|--------|
| PMOVES-MAI-UI | Main AI UI | PMOVES.AI-Edition-Hardened |

### Networking & Infrastructure (3)

| Submodule | Purpose | Branch |
|-----------|---------|--------|
| PMOVES-Tailscale | VPN networking | PMOVES.AI-Edition-Hardened |
| PMOVES-Remote-View | Remote access | PMOVES.AI-Edition-Hardened |
| PMOVES-Headscale | Tailscale control server | PMOVES.AI-Edition-Hardened |

### Data Storage (1)

| Submodule | Purpose | Branch |
|-----------|---------|--------|
| PMOVES-ToKenism-Multi | Multi-token storage | PMOVES.AI-Edition-Hardened |

### Integration Links (2)

| Submodule | Purpose | Branch |
|-----------|---------|--------|
| pmoves/integrations/archon | Archon integration | PMOVES.AI-Edition-Hardened |
| PMOVES-supabase | Supabase integration | PMOVES.AI-Edition-Hardened |

## Nested Submodules

### PMOVES-BoTZ Nested Submodules (15)

Located in `PMOVES-BoTZ/.gitmodules`:

| Path | Purpose |
|------|---------|
| pmoves_multi_agent_pro_pack/docling | Document processing |
| pmoves_multi_agent_pro_pack/mcp_gateway/PMOVES-BotZ-gateway | MCP gateway |
| features/cipher/pmoves_cipher | Cipher memory |
| PMOVES-awesome-agent-skills | Agent skills collection |
| features/skills/repos/anthropics-skills | Anthropic skills |
| features/skills/repos/huggingface-skills | HuggingFace skills |
| features/skills/repos/skillcreator-skills | Skill creator tools |
| features/skills/repos/awesome-claude-skills | Claude skills |
| features/skills/repos/d3js-skill | D3.js visualization |
| features/skills/repos/obsidian-plugin-skill | Obsidian integration |
| features/skills/repos/aws-skills | AWS integration |
| features/skills/repos/playwright-skill | Browser automation |
| features/skills/repos/epub-skill | EPUB processing |
| features/skills/repos/skills-marketplace | Skills marketplace |
| tools/claude-code-damage-control | Claude Code tools |

### PMOVES-DoX Nested Submodules (10)

Located in `PMOVES-DoX/.gitmodules`:

| Path | Purpose | Notes |
|------|---------|-------|
| A2UI_reference | PMOVES-A2UI reference | DoX-specific branch |
| PsyFeR_reference | PsyFeR knowledge graph | DoX-specific branch |
| external/Pmoves-Glancer | Glancer tool | DoX-specific branch |
| external/Pmoves-hyperdimensions | Geometric visualization | DoX-specific branch |
| external/conductor | Conductor integration | External repo |
| external/PMOVES-BotZ-gateway | BotZ gateway | Uses root version |
| external/PMOVES-n8n | n8n workflows | DoX-specific branch |
| external/PMOVES-n8n-mcp | n8n MCP integration | DoX-specific branch |
| external/PMOVES-google_workspace_mcp | Google Workspace MCP | DoX-specific branch |
| external/PMOVES-docling | Docling document processing | DoX-specific branch |
| external/PMOVES-postman-mcp-server | Postman MCP | DoX-specific branch |
| external/PMOVES-bentopdf | BentoPDF tool | DoX-specific branch |
| external/PMOVES-supabase | Supabase integration | Uses root version |

### PMOVES-ToKenism-Multi Nested Submodules (0)

**Cleaned**: 2026-02-12

Previously contained invalid absolute path entries that were actually RUNTIME INTEGRATIONS, not git submodules:
- `home/pmoves/PMOVES.AI/integrations-workspace/PMOVES-Wealth` (REMOVED)
- `home/pmoves/PMOVES.AI/integrations-workspace/PMOVES-DoX` (REMOVED)
- `integrations/PMOVES-DoX` (REMOVED)
- `integrations/PMOVES-Wealth` (REMOVED)

These services integrate via:
- NATS pub/sub messaging
- gRPC/HTTP API calls
- Docker networking (bridge modes)

## Circular References Handled

### Removed from PMOVES-DoX (2026-02-12)
- `external/PMOVES-BoTZ` - Now uses root version
- `external/PMOVES-Agent-Zero` - Now uses root version

These were causing circular references since both are already root-level submodules.

## Initialization

### Clone with Submodules

```bash
git clone --recursive https://github.com/POWERFULMOVES/PMOVES.AI.git
cd PMOVES.AI
```

### Update Existing Repository

```bash
git submodule update --init --recursive
```

### Nested Submodules

To include nested submodules (e.g., PMOVES-BoTZ skills):

```bash
git submodule update --init --recursive
```

## Networking Modes

### Standalone Mode
- Services run independently
- Use local Ollama, Cipher, Qdrant
- No parent infrastructure dependency

### Docked Mode
- Services connect to parent PMOVES.AI
- Shared TensorZero, NATS, Qdrant
- Centralized logging and monitoring

### Hybrid Mode
- Mix of local and parent resources
- Service-specific configuration

## Key Files

| File | Purpose |
|------|---------|
| `.gitmodules` | Root submodule configuration |
| `PMOVES-BoTZ/.gitmodules` | BoTZ nested submodules |
| `PMOVES-DoX/.gitmodules` | DoX nested submodules |
| `PMOVES-ToKenism-Multi/.gitmodules` | Empty (runtime integrations only) |

## Troubleshooting

### Submodule Not Initialized

```bash
git submodule update --init <submodule-path>
```

### Submodule in Detached HEAD

This is normal for submodules. To work on a submodule:

```bash
cd <submodule-path>
git checkout <branch>
```

### Circular Reference Errors

If you see circular reference errors, ensure:
1. No submodule contains a parent submodule as a nested submodule
2. PMOVES-DoX does not have `external/PMOVES-BoTZ` or `external/PMOVES-Agent-Zero`
3. PMOVES-ToKenism-Multi .gitmodules is empty

## Branch Strategy

- **main**: Primary development branch
- **PMOVES.AI-Edition-Hardened**: Production-ready hardened branch for all submodules
- **feature/***: Feature branches
- **fix/***: Bug fix branches

All submodules should be on the `PMOVES.AI-Edition-Hardened` branch for production deployment.

## Special Submodule Notes

### PMOVES-Open-Notebook
This is a fork of `lfnovo/open-notebook`. The PMOVES.AI version:
- Stays updated with upstream `lfnovo/open-notebook:main`
- All PRs and customizations go through the POWERFULMOVES fork
- Currently 25 commits ahead and 27 commits behind upstream (as of 2026-02-12)

### PMOVES-Wealth
Previously named `PMOVES-Firefly-iii` - renamed to `PMOVES-Wealth` in 2026 to better reflect its purpose as a comprehensive financial management service.
