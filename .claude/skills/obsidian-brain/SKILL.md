---
name: brain:obsidian
description: >
  Read and write PMOVES knowledge base notes in Obsidian via the Local REST API MCP.
  Vault: C:\Users\DARKXSIDE\Documents\POWERFULMOVES\POWERFULMOVES (synced to G:\My Drive).
  Operations: search notes, read note content, create/update notes, list vault structure.
  Requires: Obsidian running + Local REST API community plugin enabled.
---

# brain:obsidian — PMOVES 2nd Brain Vault Access

Connects Claude Code to the POWERFULMOVES Obsidian vault via the Local REST API
MCP server. Use this to read context from the knowledge base, write research
summaries back, and cross-reference vault notes with PMOVES repo state.

## Prerequisites

1. **Obsidian must be running** with the vault open:
   - Vault: `C:\Users\DARKXSIDE\Documents\POWERFULMOVES\POWERFULMOVES`
   - Google Drive sync: `G:\My Drive\CataclysmstudiosInc\POWERFULMOVES`

2. **Install "Local REST API" community plugin** in Obsidian:
   - Settings → Community plugins → Browse → search "Local REST API"
   - Enable it → copy the API key to `.env.local` as `OBSIDIAN_API_KEY`
   - Default port: 27123

3. **Verify MCP is connected**:
   ```bash
   curl -sf -H "Authorization: Bearer ${OBSIDIAN_API_KEY}" http://localhost:27123/vault/ | head -20
   ```

## Operations

### Search vault
```
Ask Claude: "Search my Obsidian vault for notes about PMOVES MoF architecture"
→ Uses obsidian MCP: search_notes("MoF architecture")
```

### Read a note
```
Ask Claude: "Read my Obsidian note PMOVES/DARKXSIDE_VISION.md"
→ Uses obsidian MCP: get_note("PMOVES/DARKXSIDE_VISION.md")
```

### Create or update a note
```
Ask Claude: "Write a summary of today's session to my vault at PMOVES/sessions/2026-05-18.md"
→ Uses obsidian MCP: update_note("PMOVES/sessions/2026-05-18.md", content)
```

### List vault structure
```
Ask Claude: "What folders are in my PMOVES Obsidian vault?"
→ Uses obsidian MCP: list_vault("/")
```

## PMOVES 2nd Brain Architecture

```
Obsidian Vault (local + G: Drive sync)
    ↕ Local REST API (port 27123)
    ↕ obsidian MCP server (mcp-obsidian)
Claude Code ←→ Sessions, Research, Architecture notes
    ↓
PMOVES repo (CLAUDE.md, PATTERNS.md, TAC trees)
```

## Vault Folder Conventions

| Folder | Purpose |
|--------|---------|
| `PMOVES/` | Project knowledge base |
| `PMOVES/sessions/` | Session summaries (YYYY-MM-DD.md) |
| `PMOVES/architecture/` | Architecture decisions |
| `PMOVES/models/` | Model catalog notes |
| `PMOVES/rooms/` | Room design notes |
| `CATACLYSM/` | Business/creative layer |

## Notes

- Obsidian must be OPEN and the vault loaded for the REST API to respond
- The Google Drive folder (`G:\My Drive\CataclysmstudiosInc\POWERFULMOVES`) syncs automatically
- For offline use, Claude Code falls back to reading `.claude/context/` docs directly
- See `brain:google` skill for Google Docs/Drive integration
- See `cipher:store` + `cipher:search` for PMOVES Cipher Memory (persistent across restarts)
