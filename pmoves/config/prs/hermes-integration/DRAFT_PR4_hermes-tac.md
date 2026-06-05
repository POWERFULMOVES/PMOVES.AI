# DRAFT PR: feat(hermes-tac): add 10-phase integration roadmap + operator skills

**Branch**: `feat/hermes-tac-roadmap`
**Base**: `origin/main`
**Commits**: `ba136120b`
**Status**: DRAFT -- skills need live test after HERMES installed on target nodes
**Size**: 4 files, 1,056 lines

## Scope
- `node-hermes-agent.tac.yaml`: 10-phase roadmap + post-PR tasks
- `hermes-agent-integration/SKILL.md`: operator skill
- `hermes-pr-workflow/SKILL.md`: atomic commit PR skill
- `hermes-agent.md`: agent definition

## Why Draft?
Skills are **theoretical** -- they describe Hermes commands but haven't been tested:
- `hermes skill install` path may differ on Windows vs Linux nodes
- `hermes init` creates profiles in `~/.local/share/hermes/` not `AppData\Local\hermes` on Linux
- `hermes gateway start` may need different env vars on SPARK (Jetson GB10)

## Pre-merge Checklist
- [ ] Skill tested on Elder-Melchor (Hermes Agent v0.15.1)
- [ ] Skill path reviewed for cross-platform compatibility
- [ ] Agent definition validated against `.claude/CLAUDE.md` agent schema
- [ ] TAC tree post-PR tasks updated after SPARK/B850 context gathered
