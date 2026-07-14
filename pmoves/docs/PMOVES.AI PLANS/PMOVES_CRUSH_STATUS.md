# PMOVES-Crush — Status
_Last updated: 2026-07-12_

## Purpose
Crush is the terminal-gateway companion agent (glyph `◇`, Sky Blue `#0EA5E9`, voice `companion`) and the convergence point of the Three-Body (Human + AI + System) in the PMOVES ecosystem.

## Current State: Live on GLM-5.2 (Z.AI Coding Plan)

- **Active model:** GLM-5.2 (large), GLM-5-Turbo (small) via Z.AI Coding Plan
- **Provider endpoint:** `https://api.z.ai/api/coding/paas/v4`
- **MCP servers (4 connected):** zai-mcp-server (8 tools), web-search-prime, web-reader, zread
- **Config location:** `~/.config/crush/crush.json` (consolidated primary)
- **Context paths:** CRUSH.md, AGENTS.md, CLAUDE.md, BOOTSTRAP.md, AGENT_TRAIL.md, CRUSH_OPERATOR_HOME.md, AGNOTE4482PHI.t1.md

## Implemented Items
- Repository present at `PMOVES-crush/` (Crush fork submodule)
- Crush identity registered in `pmoves/config/agent_signatures.yaml` (glyph, color, voice, NATS subjects)
- Trail entry written in `docs/AGENT_TRAIL.md` (GLM-5.2 Awakening, 2026-07-12)
- GLM-5.2 model suit created at `pmoves/configs/model-suits/glm-5.2.yaml`
- Config generator at `pmoves/tools/crush_configurator.py` (TensorZero-based)
- Mini CLI commands: `crush setup`, `crush status`, `crush preview`
- 11 broken skills fixed (name validation + frontmatter)

## Remaining Items
- Implement `pmoves mini mcp serve` so the Crush stdio MCP can call into the mini CLI
- Package the config generator as part of a future `pmoves` Python package
- Add a `crush` target to `Makefile` once the MCP bridge is battle-tested
- Claim W1 lane (Agent Theming + Cross-Machine Terminal) per AGNOTE4482_ROADMAP_W1-W5.md
- Add GLM-5.2 to TensorZero Z.AI route (`tensorzero.toml`) for fleet-wide access
- Add GLM-5.2 to `secrets_funnel_populate.py` model list
