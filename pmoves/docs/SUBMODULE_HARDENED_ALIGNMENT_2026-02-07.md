# Submodule Hardened Branch Alignment Summary

**Date:** February 7, 2026
**Purpose:** Identify submodules where `main` has commits not yet on `PMOVES.AI-Edition-Hardened`

## Summary

- **Total Submodules:** 40 active
- **Aligned (main = hardened):** 7
- **Needs Review (main ahead):** 30+
- **No Hardened Branch:** 1 (PMOVES-llama-throughput-lab - uses main correctly)

## Aligned Submodules ✅

| Submodule | Status |
|-----------|--------|
| Pmoves-hyperdimensions | ✅ Aligned |
| PMOVES-AgentGym | ✅ Aligned |
| PMOVES-surf | ✅ Aligned |
| PMOVES-Ultimate-TTS-Studio | ✅ Aligned |
| PMOVES-MAI-UI | ✅ Aligned |
| PMOVES-Headscale | ✅ Aligned |
| PMOVES-BotZ-gateway | ✅ Aligned |

## Submodules with main ahead of hardened ⚠️

### Core Services (High Priority)

| Submodule | Hardened | Main | Notes |
|-----------|----------|------|-------|
| PMOVES-Agent-Zero | 0ff60973 | a54768cb | Has persona commits, credential bootstrap |
| PMOVES-Archon | 5fc6ceb5 | 0f818425 | Needs review |
| PMOVES-BoTZ | 1c97c423 | 6c9cae2f | Just merged PR #51, main has newer commits |
| PMOVES-DoX | 6ea52f46 | bdd1f82c | Just merged PR #96, main has newer commits |
| PMOVES-tensorzero | 555a9206 | 6b1bc23f | Upstream TensorZero changes |
| PMOVES-HiRAG | 9671dc17 | 429a692b | Needs review |
| PMOVES-ToKenism-Multi | a17d8a25 | - | Main may be ahead |

### Knowledge & Services

| Submodule | Notes |
|-----------|-------|
| PMOVES-A2UI | Needs review |
| PMOVES-Deep-Serch | Needs review |
| PMOVES-E2B-Danger-Room | Needs review |
| PMOVES-E2B-Danger-Room-Desktop | Needs review |
| pmoves-e2b-mcp-server | Needs review |
| PMOVES-Danger-infra | Needs review |
| PMOVES-E2b-Spells | Needs review |
| PMOVES-Pipecat | Needs review |
| PMOVES-Pinokio-Ultimate-TTS-Studio | Needs review |
| PMOVES-transcribe-and-fetch | **Just created hardened branch** |
| PMOVES.YT | Needs review |
| PMOVES-Jellyfin | Needs review |
| Pmoves-Jellyfin-AI-Media-Stack | Needs review |
| PMOVES-Open-Notebook | Needs review |
| Pmoves-open-notebook | Needs review |
| PMOVES-Creator | Needs review |
| PMOVES-n8n | Needs review |
| PMOVES-crush | Needs review |
| PMOVES-Wealth | Needs review |
| PMOVES-Firefly-iii | Needs review |
| Pmoves-Health-wger | Needs review |
| PMOVES-Tailscale | Needs review |
| PMOVES-Remote-View | Needs review |
| pmoves/integrations/archon | Needs review |
| PMOVES-supabase | Needs review |

## Recommendations

### Immediate Actions

1. **PMOVES-transcribe-and-fetch**
   - ✅ Hardened branch created (976c972c)
   - Update .gitmodules to use hardened branch
   - Verify CI passes

2. **PMOVES-BoTZ, PMOVES-DoX, PMOVES-Agent-Zero**
   - ✅ PRs just merged to hardened
   - Consider syncing latest main commits if they're production-ready

### Review Priorities

**High Priority (Core Services):**
- PMOVES-ToKenism-Multi
- PMOVES-tensorzero
- PMOVES-HiRAG
- PMOVES-Archon

**Medium Priority (Integration Services):**
- PMOVES-YT
- PMOVES-n8n
- PMOVES-supabase
- PMOVES-Tailscale

**Lower Priority (Optional/Peripheral):**
- TTS and Voice services
- Jellyfin integration
- Wealth and Health services

## Process for Syncing main → hardened

For each submodule needing sync:

1. **Review commits** on main not in hardened
2. **Validate CI/CD** passes on main
3. **Create PR** main → PMOVES.AI-Edition-Hardened (if changes are significant)
4. **Or direct merge** (if changes are trivial/bug fixes)
5. **Update submodule** in parent PMOVES.AI repo

## Notes

- The `PMOVES.AI-Edition-Hardened` branch is the production branch
- Not all commits on main need to go to hardened
- Focus on: bug fixes, security updates, validated features
- Skip: experimental features, WIP, breaking changes without testing
