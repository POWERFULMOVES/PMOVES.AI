# feat(hermes-infra): registry + room + TAC tree integration

**Status**: MERGED (commits pushed to main -- retrospective PR for review)
**Commits**: 3
**Total lines**: ~150

## Commits

| SHA | Message |
|-----|---------|
| 83bdd79ae | feat(hermes-room): add hermes-agent gateway room to catalog |
| 118d2289d | feat(hermes-registry): add hermes-agent to agent taxonomy |
| 70927b09f | feat(hermes-tac): add 10-phase integration roadmap + operator skills |

## What Changed

- **Room manifest** (`hermes-agent.room.control.json`): Gateway room with apps on port 7700, stage=rehearsal, suits=[hermes-gateway, mcp-bridge, skill-curator].
- **Agent registry** (`agent_registry.yaml` + `agent_signatures.yaml`): Added `hermes_agent` with glyph ★, color #047857, node affinity for all 8 fleet nodes.
- **TAC tree** (`node-hermes-agent.tac.yaml`): 10-phase roadmap (Identity → Registry → Profiles → NATS → Gateway → Skills → Security → Docs → Fleet Context → Practice Integration). Post-PR follow-ups for provider review, Docker MCP, HF/Unsloth, Ageless Beauty.

## Impact Assessment

- Low risk: all changes are additive. No existing entries modified.
- Identity separation: `hermes-agent` (framework) distinct from `hermes` (LLM model persona).

## Testing

- Registry YAML validation: PASS
- Room manifest JSON validation: PASS
- TAC tree YAML validation: PASS

---
*Review requested by: elder-melchor*
