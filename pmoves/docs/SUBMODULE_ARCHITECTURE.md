# PMOVES.AI Submodule Architecture

## Overview

PMOVES.AI contains 32 submodules organized into core, integration, vendor, and research categories. All submodules track the `PMOVES.AI-Edition-Hardened` branch (or variant for nested submodules).

## Submodule Inventory

### Core Submodules (4)

These are initialized git submodules with branch configuration:

| Submodule | Expected Branch | Purpose | Status |
|-----------|-----------------|---------|--------|
| PMOVES-Agent-Zero | PMOVES.AI-Edition-Hardened | General AI assistant with MCP | Initialized |
| PMOVES-BoTZ | PMOVES.AI-Edition-Hardened | BoTZ ecosystem integration | Initialized |
| PMOVES-ToKenism-Multi | PMOVES.AI-Edition-Hardened | Multi-agent Tokenism | Initialized |
| PMOVES-crush | PMOVES.AI-Edition-Hardened | Data processing | Initialized |

### Integration Submodules (17)

These are local clones (not git submodules) that need to be converted:

| Submodule | Expected Branch | Purpose | Network |
|-----------|-----------------|---------|---------|
| PMOVES-Archon | PMOVES.AI-Edition-Hardened | Agent orchestration | pmoves_app |
| PMOVES-Creator | PMOVES.AI-Edition-Hardened | Content creation | pmoves_app |
| PMOVES-Deep-Serch | PMOVES.AI-Edition-Hardened | Deep search capabilities | pmoves_api |
| PMOVES-HiRAG | PMOVES.AI-Edition-Hardened | Hierarchical RAG | pmoves_api |
| PMOVES.Jellyfin | PMOVES.AI-Edition-Hardened | Media integration | pmoves_app |
| Pmoves-Jellyfin-AI-Media-Stack | PMOVES.AI-Edition-Hardened | AI media processing | pmoves_app |
| PMOVES-Open-Notebook | PMOVES.AI-Edition-Hardened | Notebook integration | pmoves_app |
| Pmoves-Health-wger | PMOVES.AI-Edition-Hardened | Health tracking | pmoves_app |
| PMOVES-Wealth | PMOVES.AI-Edition-Hardened | Financial tracking | pmoves_app |
| PMOVES-DoX | PMOVES.AI-Edition-Hardened | Document intelligence | pmoves_app |
| PMOVES-Remote-View | PMOVES.AI-Edition-Hardened | Remote viewing | pmoves_app |
| PMOVES-Tailscale | PMOVES.AI-Edition-Hardened | VPN integration | pmoves_app |
| PMOVES-n8n | PMOVES.AI-Edition-Hardened | Workflow automation | pmoves_app |
| PMOVES-Pipecat | PMOVES.AI-Edition-Hardened | Pipeline framework | pmoves_app |
| PMOVES-Ultimate-TTS-Studio | PMOVES.AI-Edition-Hardened | Text-to-speech | pmoves_app |
| PMOVES-Pinokio-Ultimate-TTS-Studio | PMOVES.AI-Edition-Hardened | TTS integration | pmoves_app |
| PMOVES-tensorzero | PMOVES.AI-Edition-Hardened | LLM gateway | pmoves_bus |
| PMOVES.YT | PMOVES.AI-Edition-Hardened | YouTube integration | pmoves_app |

### Vendor Submodules (8)

Third-party dependencies:

| Submodule | Purpose |
|-----------|---------|
| pmoves/integrations/archon | Archon integration copy |
| pmoves/vendor/agentgym-rl | Agent Gym RL |
| pmoves/vendor/e2b | E2B core |
| pmoves/vendor/e2b-desktop | E2B desktop |
| pmoves/vendor/e2b-infra | E2B infrastructure |
| pmoves/vendor/e2b-mcp-server | E2B MCP server |
| pmoves/vendor/e2b-spells | E2B spells |
| pmoves/vendor/e2b-surf | E2B surf |

### Research Submodules (3)

Experimental and reference implementations:

| Submodule | Purpose |
|-----------|---------|
| research/A2UI | A2UI research |
| Pmoves-hyperdimensions | Mathematical visualization |
| pmoves/integrations/workspace | Integration workspace |

## Nested Submodules

### PMOVES-DoX

PMOVES-DoX contains its own nested submodules:

| Nested Submodule | Expected Branch | Purpose |
|------------------|-----------------|---------|
| A2UI_reference | PMOVES.AI-Edition-Hardened | A2UI reference |
| PsyFeR_reference | main | Byterover Cipher memory |
| external/Pmoves-Glancer | PMOVES.AI-Edition-Hardened | Data glancer |
| external/Pmoves-hyperdimensions | PMOVES.AI-Edition-Hardened | Math visualization |
| external/conductor | v0.1.1 | Google Conductor |
| external/PMOVES-Agent-Zero | PMOVES.AI-Edition-Hardened-DoX | Agent Zero (DoX variant) |
| external/PMOVES-BoTZ | PMOVES.AI-Edition-Hardened | BoTZ integration |
| external/PMOVES-BotZ-gateway | main | BoTZ gateway |

**Note**: `PMOVES.AI-Edition-Hardened-DoX` is a variant branch for the nested Agent Zero submodule.

## Docking Requirements by Submodule

### PMOVES-DoX

**Standalone Mode**:
- Database: SQLite (`backend/db.sqlite3`)
- Search: FAISS or NumPy fallback
- Ports: Backend 8000, Frontend 3001
- No MCP exposure

**Docked Mode**:
- Database: Supabase (`DB_BACKEND=supabase`)
- Search: Shared Qdrant via Hi-RAG
- Network: `pmoves_app`, `pmoves_bus`
- MCP: Exposes search, tag extraction, POML export
- NATS: Geometry bus for real-time updates

### PMOVES-Agent-Zero

**Standalone Mode**:
- Web UI: `http://localhost:50051`
- LLM: Direct to providers (Anthropic, OpenAI, etc.)
- MCP: Disabled

**Docked Mode**:
- Web UI: `http://pmoves-agent-zero:50051`
- LLM: Via TensorZero Gateway
- MCP: `http://pmoves-agent-zero:50051/mcp/t-{token}/sse`
- Tools: `send_message`, `finish_chat`

### PMOVES-HiRAG

**Standalone Mode**:
- Vector DB: Local Qdrant
- Search: Local Meilisearch
- Ports: Gateway 8086, GPU variant 8087

**Docked Mode**:
- Vector DB: Shared Qdrant (`pmoves-qdrant:6333`)
- Search: Shared Meilisearch (`pmoves-meilisearch:7700`)
- Network: `pmoves_api`, `pmoves_data`

### PMOVES-tensorzero

**Standalone Mode**:
- ClickHouse: Local
- Models: Direct to providers

**Docked Mode**:
- ClickHouse: Shared (`pmoves-clickhouse:8123`)
- Models: Via tier-llm env
- Network: `pmoves_bus`

## Migration Path: Local Clones to Git Submodules

Currently, 17 submodules are local clones that should be converted to proper git submodules.

### Conversion Steps

1. **Remove local clone**:
   ```bash
   mv PMOVES-Archon PMOVES-Archon.backup
   ```

2. **Add as git submodule**:
   ```bash
   git submodule add -b PMOVES.AI-Edition-Hardened \
     https://github.com/POWERFULMOVES/PMOVES-Archon.git \
     PMOVES-Archon
   ```

3. **Verify alignment**:
   ```bash
   cd PMOVES-Archon
   git branch --show-current  # Should be PMOVES.AI-Edition-Hardened
   ```

## Alignment Verification Script

```bash
#!/bin/bash
# scripts/verify-submodules.sh

REPO_ROOT="/home/pmoves/PMOVES.AI"
EXPECTED_BRANCH="PMOVES.AI-Edition-Hardened"

echo "=== Verifying submodule alignment ==="

# Core submodules (git submodules)
for submodule in PMOVES-Agent-Zero PMOVES-BoTZ PMOVES-ToKenism-Multi PMOVES-crush; do
  if [ -d "$REPO_ROOT/$submodule/.git" ]; then
    branch=$(cd "$REPO_ROOT/$submodule" && git branch --show-current)
    if [ "$branch" = "$EXPECTED_BRANCH" ]; then
      echo "✅ $submodule: $branch"
    else
      echo "❌ $submodule: $branch (expected $EXPECTED_BRANCH)"
    fi
  fi
done

# Integration submodules (local clones)
for submodule in PMOVES-Archon PMOVES-Creator PMOVES-Deep-Serch PMOVES-HiRAG \
  PMOVES-DoX PMOVES-n8n PMOVES-tensorzero PMOVES-Pipecat; do
  if [ -d "$REPO_ROOT/$submodule/.git" ]; then
    branch=$(cd "$REPO_ROOT/$submodule" && git branch --show-current)
    if [ "$branch" = "$EXPECTED_BRANCH" ]; then
      echo "✅ $submodule: $branch"
    else
      echo "❌ $submodule: $branch (expected $EXPECTED_BRANCH)"
    fi
  fi
done

# Check nested submodule in PMOVES-DoX
if [ -d "$REPO_ROOT/PMOVES-DoX/external/PMOVES-Agent-Zero/.git" ]; then
  branch=$(cd "$REPO_ROOT/PMOVES-DoX/external/PMOVES-Agent-Zero" && git branch --show-current)
  if [ "$branch" = "PMOVES.AI-Edition-Hardened-DoX" ]; then
    echo "✅ PMOVES-DoX/PMOVES-Agent-Zero: $branch"
  else
    echo "❌ PMOVES-DoX/PMOVES-Agent-Zero: $branch (expected PMOVES.AI-Edition-Hardened-DoX)"
  fi
fi
```

## Best Practices

1. **Always verify branch** before making changes to a submodule
2. **Test standalone first** before testing docked integration
3. **Document docking requirements** in each submodule's CLAUDE.md
4. **Use variant branches** for nested submodules (e.g., `-DoX` suffix)
5. **Keep submodules updated** with parent repository changes
6. **Dual-write during migration** when switching from standalone to docked

## References

- [DOCKING_ARCHITECTURE.md](DOCKING_ARCHITECTURE.md) - Detailed docking patterns
- [ENVIRONMENT_SETUP.md](ENVIRONMENT_SETUP.md) - Environment configuration
- [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) - Migration procedures
