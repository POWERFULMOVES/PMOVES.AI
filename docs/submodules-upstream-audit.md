# PMOVES.AI Submodule Audit Summary

**Date:** 2026-01-29
**Total Submodules:** 37

## Audit Results

### Forked Submodules (Need Upstream Sync + Potential PRs)

| Submodule | Upstream | Sync Status | Action Needed |
|-----------|----------|-------------|---------------|
| **PMOVES-AgentGym** | WooooDyy/AgentGym | ✅ Synced (0/0) | None |
| **PMOVES-Open-Notebook** | lfnovo/open-notebook | ⚠️ **23 ahead** | Consider upstream PR for generic improvements |
| **PMOVES-Wealth** | firefly-iii/firefly-iii | ⚠️ **16 ahead** | Consider upstream PR for generic improvements |
| **PMOVES-transcribe-and-fetch** | frdel/agent-zero | ⚠️ **Misconfigured** | **CRITICAL: Fix origin remote** |
| **Pmoves-AgentGym-RL** | WooooDyy/AgentGym | Needs audit | Check upstream config |

### Open PRs Across Forked Submodules

| Repo | PR | Title | Status |
|------|-----|-------|--------|
| PMOVES-Wealth | #11 | Bump symfony/process (dependabot) | Open - Minor update |

### PMOVES Original Repos (No Upstream)

These are POWERFULMOVES-owned repositories (not forks):

- PMOVES-A2UI, PMOVES-Agent-Zero, PMOVES-Archon
- PMOVES-BoTZ, PMOVES-BotZ-gateway, PMOVES-Creator
- PMOVES-Danger-infra, PMOVES-Deep-Serch, PMOVES-DoX
- PMOVES-E2B-Danger-Room, PMOVES-E2B-Danger-Room-Desktop
- PMOVES-E2b-Spells, PMOVES-HiRAG, PMOVES-Jellyfin
- PMOVES-MAI-UI, PMOVES-Pinokio-Ultimate-TTS-Studio
- PMOVES-Remote-View, PMOVES-Tailscale, PMOVES-ToKenism-Multi
- PMOVES-Ultimate-TTS-Studio, PMOVES-crush, PMOVES-n8n
- pmoves/integrations/archon

### POWERFULMOVES Non-PMOVES Prefix

- PMOVES-Pipecat, PMOVES-surf, PMOVES.YT, Pmoves-Health-wger
- Pmoves-Jellyfin-AI-Media-Stack, Pmoves-hyperdimensions

### External/Vendor

- pmoves/vendor/agentgym, pmoves/vendor/agentgym-rl

## Critical Issues

### 1. PMOVES-transcribe-and-fetch Misconfiguration

The submodule has its `origin` remote pointing to the main PMOVES.AI repository instead of its own fork:

```
Current origin: https://github.com/POWERFULMOVES/PMOVES.AI.git ❌
Should be: https://github.com/POWERFULMOVES/PMOVES-transcribe-and-fetch.git
```

**Fix required:**
```bash
cd PMOVES-transcribe-and-fetch
git remote set-url origin https://github.com/POWERFULMOVES/PMOVES-transcribe-and-fetch.git
git fetch origin
git branch --set-upstream-to=origin/PMOVES.AI-Edition-Hardened PMOVES.AI-Edition-Hardened
```

## Actions Required

| Priority | Action | Submodule |
|----------|--------|-----------|
| **P0** | Fix origin remote | PMOVES-transcribe-and-fetch |
| P1 | Review upstream contribution potential | PMOVES-Open-Notebook (23 ahead) |
| P1 | Review upstream contribution potential | PMOVES-Wealth (16 ahead) |
| P2 | Merge dependabot PR | PMOVES-Wealth #11 |
| P2 | Audit upstream config | Pmoves-AgentGym-RL |

## Documentation PRs

- **PR #556**: docs: Comprehensive security documentation refresh (2026-01-29)
  - https://github.com/POWERFULMOVES/PMOVES.AI/pull/556

## Related Documentation

- [PMOVES Git Organization](./PMOVES_Git_Organization.md)
- [Submodule Sync Script](../pmoves/scripts/sync-upstream-forks.sh)
