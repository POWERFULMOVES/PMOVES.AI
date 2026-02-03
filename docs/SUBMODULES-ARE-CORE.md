# PMOVES.AI Submodules - Core Components Architecture

**Last Updated:** 2026-02-03
**Branch:** PMOVES.AI-Edition-Hardened

## Critical Principle

**ALL PMOVES.AI SUBMODULES ARE CORE COMPONENTS**

> **NONE ARE OPTIONAL** - Every submodule listed in `.gitmodules` is a required service
> that must be initialized and running for full PMOVES.AI functionality.

### Production Requirements

In production environments, ALL submodules must be:
- Initialized: `git submodule update --init --recursive`
- Updated: `git submodule update --remote --recursive`
- Running: Each service/container deployed and operational

### `ignore = all` is PROHIBITED

The `ignore = all` directive in `.gitmodules` was historically used to skip
submodule updates. This has been **REMOVED** from all submodule entries because:

1. **All services are core** - None are optional or "nice-to-have"
2. **Automation requires current commits** - CI/CD needs latest submodule SHAs
3. **Deployment consistency** - All services must be synchronized

---

## Submodule Branch Strategy

### Primary Branch: `PMOVES.AI-Edition-Hardened`

All PMOVES forks use the `PMOVES.AI-Edition-Hardened` branch as the primary integration branch.

### Nested Submodules

Many PMOVES submodules contain their own nested submodules. These nested references follow a pattern:

```
PMOVES-DoX/
├── .gitmodules
└── external/PMOVES-BoTZ (nested submodule)
    └── Points to: PMOVES-BoTZ.git @ PMOVES.AI-Edition-Hardened
```

### Nested Submodule Resolution Rules

When a submodule contains another submodule as a nested reference:

1. **PMOVES Fork Available**: Use `PMOVES.AI-Edition-Hardened` branch
   - Example: `PMOVES-DoX` → `external/PMOVES-BoTZ` → `PMOVES.AI-Edition-Hardened`

2. **Upstream Only (No PMOVES Fork)**: Use upstream `main` branch
   - Example: Third-party libraries without PMOVES forks

3. **Nested Submodules in Nested Submodules**: Recursively apply the same rules
   - Example: `PMOVES-ToKenism-Multi` → `integrations/PMOVES-DoX` → `external/PMOVES-BoTZ`

---

## Complete Submodule Inventory

### Core Agent & Orchestration Services

| Submodule | Nested Submodules | Purpose |
|-----------|-------------------|---------|
| PMOVES-Agent-Zero | None | Agent orchestrator with MCP bridge |
| PMOVES-Archon | PMOVES-Agent-Zero, PMOVES-BoTZ, PMOVES-Deep-Serch, PMOVES-HiRAG, PMOVES-BotZ-gateway, PMOVES-tensorzero, docling | Knowledge management & persona service |
| PMOVES-BoTZ | None | Multi-agent MCP platform |
| PMOVES-BotZ-gateway | None | MCP gateway for BoTZ |

### Knowledge & Research Services

| Submodule | Nested Submodules | Purpose |
|-----------|-------------------|---------|
| PMOVES-A2UI | None | PMOVES fork of Google ADK demo |
| PMOVES-Deep-Serch | None | Multimodal holographic deep research |
| PMOVES-HiRAG | None | Hybrid RAG (vectors + graph + full-text) |
| Pmoves-hyperdimensions | None | High-dimensional visualization |

### Agent Training & Research Platforms

| Submodule | Nested Submodules | Purpose |
|-----------|-------------------|---------|
| PMOVES-AgentGym | None | Agent evaluation framework |
| Pmoves-AgentGym-RL | None | RL training for agents |
| PMOVES-llama-throughput-lab | None | LLM performance testing |
| PMOVES-surf | None | Standalone web application |

### E2B Danger Room - Sandboxed Code Execution

| Submodule | Nested Submodules | Purpose |
|-----------|-------------------|---------|
| PMOVES-E2B-Danger-Room | None | E2B core - code execution environment |
| PMOVES-E2B-Danger-Room-Desktop | None | Desktop GUI integration |
| pmoves-e2b-mcp-server | None | MCP server for E2B |
| PMOVES-Danger-infra | packages with Dockerfiles | Infrastructure for Danger Room |
| PMOVES-E2b-Spells | None | E2B spell/cookbook examples |
| pmoves/vendor/e2b | Vendor copy of PMOVES-E2B-Danger-Room | Legacy vendor path |
| pmoves/vendor/e2b-desktop | Vendor copy of PMOVES-E2B-Danger-Room-Desktop | Legacy vendor path |
| pmoves/vendor/e2b-infra | Vendor copy of PMOVES-Danger-infra | Legacy vendor path |
| pmoves/vendor/e2b-mcp-server | Vendor copy of pmoves-e2b-mcp-server | Legacy vendor path |
| pmoves/vendor/e2b-spells | Vendor copy of PMOVES-E2b-Spells | Legacy vendor path |
| pmoves/vendor/e2b-surf | Vendor copy of PMOVES-surf | Legacy vendor path |

### Voice & Speech Services

| Submodule | Nested Submodules | Purpose |
|-----------|-------------------|---------|
| PMOVES-Pipecat | None | Voice communication (Pipecat framework) |
| PMOVES-Pinokio-Ultimate-TTS-Studio | None | TTS with Pinokio integration |
| PMOVES-Ultimate-TTS-Studio | None | Ultimate TTS (7 engines: Kokoro, F5-TTS, etc.) |
| PMOVES-transcribe-and-fetch | None | Media transcription pipeline |

### Media & Content Services

| Submodule | Nested Submodules | Purpose |
|-----------|-------------------|---------|
| PMOVES.YT | None | YouTube ingestion & download |
| PMOVES-Jellyfin | None | Media server / streaming |
| Pmoves-Jellyfin-AI-Media-Stack | None | Jellyfin AI integration stack |

### Knowledge Base & Notes

| Submodule | Nested Submodules | Purpose |
|-----------|-------------------|---------|
| PMOVES-Open-Notebook | None | SurrealDB note-taking (external repo) |
| Pmoves-open-notebook | None | SurrealDB note-taking (PMOVES fork) |

### Document Processing

| Submodule | Nested Submodules | Purpose |
|-----------|-------------------|---------|
| PMOVES-DoX | external/PMOVES-BoTZ | Document CLI processor with nested BoTZ |
| PMOVES-Creator | None | Content creation tools |

### Workflow & Automation

| Submodule | Nested Submodules | Purpose |
|-----------|-------------------|---------|
| PMOVES-n8n | None | Workflow automation platform |
| PMOVES-crush | None | Data processing pipeline |

### LLM Gateway & Model Services

| Submodule | Nested Submodules | Purpose |
|-----------|-------------------|---------|
| PMOVES-tensorzero | None | LLM gateway with observability |

### Financial Management

| Submodule | Nested Submodules | Purpose |
|-----------|-------------------|---------|
| PMOVES-Wealth | None (uses Firefly-iii internally) | Personal finance manager |
| PMOVES-Firefly-iii | None | Firefly III backend (forked) |
| Pmoves-Health-wger | None | Health & fitness tracker |

### UI & Frontend Services

| Submodule | Nested Submodules | Purpose |
|-----------|-------------------|---------|
| PMOVES-MAI-UI | None | Multi-Agent Interface UI |

### Networking & Infrastructure

| Submodule | Nested Submodules | Purpose |
|-----------|-------------------|---------|
| PMOVES-Tailscale | None | VPN / mesh networking |
| PMOVES-Remote-View | None | Remote viewing capability |

### Tokenism & Geometry

| Submodule | Nested Submodules | Purpose |
|-----------|-------------------|---------|
| PMOVES-ToKenism-Multi | integrations/PMOVES-DoX → external/PMOVES-BoTZ | Token simulation with DoX nesting |

### Integration Links

| Submodule | Purpose |
|-----------|---------|
| pmoves/integrations/archon | Archon integration link |

---

## Nested Submodule Examples

### Example 1: PMOVES-DoX Nested Structure

```
PMOVES-DoX/.gitmodules:
[submodule "external/PMOVES-BoTZ"]
    path = external/PMOVES-BoTZ
    url = https://github.com/POWERFULMOVES/PMOVES-BoTZ.git
    branch = PMOVES.AI-Edition-Hardened
```

### Example 2: PMOVES-ToKenism-Multi Double Nesting

```
PMOVES-ToKenism-Multi/.gitmodules:
[submodule "integrations/PMOVES-DoX"]
    path = integrations/PMOVES-DoX
    url = ../PMOVES-DoX  # Relative path to sibling submodule

PMOVES-ToKenism-Multi/integrations/PMOVES-DoX/.gitmodules:
[submodule "external/PMOVES-BoTZ"]
    path = external/PMOVES-BoTZ
    url = https://github.com/POWERFULMOVES/PMOVES-BoTZ.git
    branch = PMOVES.AI-Edition-Hardened
```

### Example 3: PMOVES-Archon Multiple Nested Submodules

```
PMOVES-Archon/.gitmodules:
[submodule "external/PMOVES-Agent-Zero"]
[submodule "external/PMOVES-BoTZ"]
[submodule "external/PMOVES-HiRAG"]
[submodule "external/PMOVES-Deep-Serch"]
[submodule "pmoves_multi_agent_pro_pack/PMOVES-BotZ-gateway"]
[submodule "pmoves_multi_agent_pro_pack/PMOVES-tensorzero"]
[submodule "pmoves_multi_agent_pro_pack/docling"]
```

---

## Initialization Commands

### Full Recursive Initialization

```bash
# Initialize ALL submodules including nested ones
git submodule update --init --recursive

# Update ALL submodules to latest PMOVES.AI-Edition-Hardened
git submodule update --remote --recursive --merge

# Clone PMOVES.AI with all submodules
git clone --recursive https://github.com/POWERFULMOVES/PMOVES.AI.git
```

### Checking Submodule Status

```bash
# Show all submodule statuses
git submodule status --recursive

# List submodules with branch information
git submodule foreach -q 'echo "$(basename $t) : $(git branch --show-current)"'
```

---

## Integration Workspace

The `/home/pmoves/PMOVES.AI/integrations-workspace/` directory contains
submodule clones that are used for cross-submodule development and testing.

Services in integrations-workspace:
- PMOVES-Agent-Zero
- PMOVES-Archon
- PMOVES-Firefly-iii (alias for PMOVES-Wealth integration)
- PMOVES-Ultimate-TTS-Studio
- PMOVES-crush
- PMOVES-jellyfin (alias for PMOVES-Jellyfin)
- PMOVES.YT
- Pmoves-Health-wger
- Pmoves-open-notebook

---

## Maintenance Notes

### Adding a New Submodule

1. Fork the upstream repository to POWERFULMOVES organization
2. Create `PMOVES.AI-Edition-Hardened` branch
3. Add to `.gitmodules` with proper branch specification
4. Document in this file with nested submodule structure if applicable
5. Run `git submodule update --init <new-submodule>`

### Updating Submodule References

When updating submodule SHAs, ensure all nested submodules are also updated:

```bash
# Update main submodule
git submodule update --remote <submodule>

# Update nested submodules within
git -C <submodule> submodule update --remote --recursive
```

### CI/CD Integration

All CI/CD pipelines must:
1. Initialize all submodules recursively
2. Verify nested submodule integrity
3. Check out `PMOVES.AI-Edition-Hardened` branch for all PMOVES forks

---

**Document Version:** 2.0
**Status:** All submodules are CORE components - none optional
