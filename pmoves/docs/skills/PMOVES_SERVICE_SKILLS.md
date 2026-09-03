# PMOVES Service Skills — Fleet Skill Companion Set

Skills that ship with Hermes fleet nodes so agents stop re-grepping known state.
Each skill encodes: service architecture, verified operational commands, fleet
context, and failure modes — the distilled output of a live session.

## Fleet-critical skills (this set)

| Skill | Service | Key facts encoded |
|-------|---------|-------------------|
| `pmoves-n8n` | n8n self-hosted fabric | 3-layer split: PMOVES-N8N-Auto (source fork) / PMOVES-n8n (workflows-as-code overlay — unrelated histories BY DESIGN) / runtime compose pmoves/n8n:2.1.5-runtime :5678 |
| `pmoves-activepieces` | ActivePieces companion | standalone stack 0.86.3 :8087, flows-as-code git-sync (EE) vs export→commit→import (CE), phase-2 main-compose follow-up |
| `pmoves-e2b-danger-room` | E2B sandboxes | SDK usage, Terraform self-host path (e2b-dev/infra, AWS/GCP), Danger-Room microVM pattern, sibling repos map |
| `pmoves-mcp-gateway` | Docker MCP gateway fork | gateway pattern, secret management, OAuth flows, fleet profile usage (pmoves_5090_web), sync via merge-upstream |
| `jcodemunch` | AST code exploration | MCP server registration (uvx stdio, v1.108.316 verified), index→query workflow, 95% token savings |
| `pmoves-skills-cli` | skills ecosystem CLI | vercel-labs fork, npx skills add across 76+ harnesses |
| `pmoves-pinokio-fork` | Pinokio fork builds | release download + verify (sha512), updater-drift caveat (build.publish still upstream) |
| `pterm` / `gepeto` | Pinokio terminal + scaffolder | control-plane refs pinokio://host:port/api/<id>, app skeleton conventions |
| `archon-dsh-agents` | Archon a2a agents | build loop, CHIT signing wiring (sign_trail + signing cards), skills-to-agents pipeline |

## Conventions

- Skills live in the node's Hermes profile (`~/AppData/Local/hermes/profiles/<profile>/skills/`)
- PMOVES forks over upstream where they exist (grep POWERFULMOVES first)
- Sync status and SHA pins recorded in-skill when verified live
- The `.gitmodules` `path=` key is REQUIRED on this fleet's git build — every
  submodule entry carries it explicitly

## Related

- `mcp_inventory.json` — canonical MCP server registry (PR #2899 adds jcodemunch)
- `AGNOTE4482PHI.t1.md` — lane claim/release register
- Hermes skills are per-profile; mirror across fleet nodes via the skills CLI
