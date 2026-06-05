# HERMES Integration PRs (Ready for Review)

## PR 1: feat(hermes-profile): elder-melchor + Docker MCP Gateway

**Commits**: d1251c8a5, c3cbd7e72, baac9449b, 16896afa0, d3b3c8546
**Files**:
- `pmoves/config/profiles/hermes/elder-melchor.yaml` (main profile)
- `pmoves/config/profiles/hermes/elder-melchor-system-specs.json` (cleaned)
- `pmoves/config/mcp/docker-mcp-gateway.md` (documentation)
- `pmoves/config/mcp/pmoves-ai-profile.yaml` (MCP profile)
- `pmoves/config/profiles/hermes/z890-glances.conf` (Glances config)
- `pmoves/config/nats/hermes/elder-melchor-nats.yaml` (NATS bridge)
- `pmoves/config/nats/hermes/test-nats-bridge.py` (test script)
- `pmoves/config/nats/hermes/test-nats-bridge.bat` (Windows test)
- `pmoves/config/pinokio/hermes-elder-melchor.pinokio.json` (Pinokio launcher)
- `pmoves/config/prs/hermes-integration/DRAFT_PR1_hermes-profiles.md`

**Size**: ~200 lines (profile) + docs
**Security**: All IPs/hostnames masked with placeholders
**Testing**: Hermes doctor passes, MCP server listed

## PR 2: feat(hermes-infra): registry + room + TAC tree

**Commits**: 83bdd79ae, 118d2289d, 70927b09f
**Files**:
- `pmoves/config/agent_registry.yaml`
- `pmoves/config/agent_signatures.yaml`
- `pmoves/config/rooms/hermes-agent.room.control.json`
- `pmoves/config/rooms/catalog.json`
- `pmoves/configs/tac_trees/node-hermes-agent.tac.yaml`
- `.claude/agents/hermes-agent.md`
- `.claude/skills/hermes-agent-integration/SKILL.md`
- `.claude/skills/hermes-pr-workflow/SKILL.md`

**Size**: ~150 lines
**Impact**: Low risk (additive only, no existing entries modified)

## PR 3: docs(hermes): integration spec + research

**Commits**: e84155799, 00ea97528, a03f3eb61
**Files**:
- `pmoves/docs/AGENTS/HERMES_AGENT_INTEGRATION.md`
- `pmoves/docs/AGENTS/HERMES_ATOMIC_COMMITS.md`
- `pmoves/docs/AGENTS/AGNOTE4482.md`
- `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md`
- `pmoves/docs/AGENTS/AGNOTE4482_SIGNOFF_CHECKLIST.md`
- `pmoves/docs/AGENTS/AGNOTE4482_SITREP.md`
- `pmoves/research/RESEARCH_Hermes_Agent_Deep_Dive.md`
- `pmoves/research/RESEARCH_Neotron3_Ultra.md`
- `pmoves/research/youtube_hermes_transcript.txt`
- `pmoves/research/youtube_spark_transcript.txt`
- `pmoves/scripts/hermes/init-ageless-beauty-submodules.sh`
- `pmoves/scripts/hermes/init-ageless-beauty-submodules.bat`
- `pmoves/config/prs/hermes-integration/DRAFT_PR2_hermes-room.md` through `DRAFT_PR6_hermes-research.md`

**Size**: ~800 lines (mostly docs)
**Impact**: Documentation only, no runtime code
