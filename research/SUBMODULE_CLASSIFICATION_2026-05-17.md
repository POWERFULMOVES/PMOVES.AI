# Submodule Classification — 2026-05-17

## Dirty (`+` prefix — uncommitted working tree changes)
| Submodule | Branch | Action |
|-----------|--------|--------|
| PMOVES-AgentGym | f724cfc (detached) | Discard or commit locally |
| PMOVES-Archon | heads/PMOVES.AI-Edition-Hardened | Stale branch + dirty — advance to v1.9 |
| PMOVES-BoTZ | heads/chore/deps-update | Dirty — likely deps change, commit or discard |
| PMOVES-Headscale | heads/chore/ci-workflow-updates | Dirty — CI workflow change, commit |
| PMOVES-a0-plugins | heads/chore/ci-workflow-updates | Dirty — CI workflow change, commit |
| PMOVES-supabase | heads/chore/ci-workflow-updates | Dirty — CI workflow change, commit |
| PMOVES-tensorzero | heads/chore/ci-workflow-updates | Dirty — CI workflow change, commit |
| PMOVES-transcribe-and-fetch | heads/refactor/cloud-api-provider-agnostic | Dirty — active refactor branch, keep |
| Pmoves-hyperdimensions | heads/main | Dirty — uncommitted on main, commit or discard |
| pmoves/integrations/archon | heads/PMOVES.AI-Edition-Hardened | Stale branch + dirty — advance to v1.9 |

## Not Initialized (`-` prefix)
| Submodule | Action |
|-----------|--------|
| skills/PMOVES-agent-sandbox-skill | `git submodule update --init` |
| skills/PMOVES-awesome-agent-skills | `git submodule update --init` |
| skills/Pmoves-claude-d3js-skill | `git submodule update --init` |
| skills/Pmoves-skills | `git submodule update --init` |
| skills/pmoves-fork-repository-skill | `git submodule update --init` |

## On Stale Branch (`PMOVES.AI-Edition-Hardened` — should advance to v1.9/main)
| Submodule | Current Branch | Action |
|-----------|---------------|--------|
| PMOVES-A2UI | remotes/origin/PMOVES.AI-Edition-Hardened | Advance gitlink to main |
| PMOVES-BotZ-gateway | heads/PMOVES.AI-Edition-Hardened | Advance gitlink (legacy) |
| PMOVES-Creator | heads/PMOVES.AI-Edition-Hardened | Advance gitlink to main |
| PMOVES-Danger-infra | remotes/origin/PMOVES.AI-Edition-Hardened | Advance gitlink to main |
| PMOVES-Deep-Serch | heads/PMOVES.AI-Edition-Hardened | Advance gitlink to main |
| PMOVES-HiRAG | heads/PMOVES.AI-Edition-Hardened | Advance gitlink to main |
| PMOVES-Jellyfin | heads/PMOVES.AI-Edition-Hardened | Advance gitlink to main |
| PMOVES-Open-Notebook | heads/PMOVES.AI-Edition-Hardened | Advance gitlink to main |
| PMOVES-Remote-View | heads/PMOVES.AI-Edition-Hardened | Advance gitlink to main |
| PMOVES-ToKenism-Multi | heads/PMOVES.AI-Edition-Hardened | Advance gitlink to main |
| PMOVES.YT | heads/PMOVES.AI-Edition-Hardened | Advance gitlink to main |
| PMOVES-crush | heads/PMOVES.AI-Edition-Hardened | Advance gitlink to main |
| Pmoves-Health-wger | heads/PMOVES.AI-Edition-Hardened | Advance gitlink to main |
| Pmoves-Jellyfin-AI-Media-Stack | heads/PMOVES.AI-Edition-Hardened | Advance gitlink to main |

## On Stale Feature/Merge Branches
| Submodule | Current Branch | Action |
|-----------|---------------|--------|
| PMOVES-Agent-Zero | remotes/origin/fix/phase-d-hardening-20 | Stale fix branch — advance to main |
| PMOVES-DoX | remotes/origin/feat/unfcu-enterprise-implementations-1 | Stale feature — advance to main |
| PMOVES-Wealth | remotes/origin/merge-tokenism-into-hardened-306 | Stale merge branch — advance to main |
| PMOVES-n8n | remotes/origin/codex/n8n-authoritative-runtime | Evaluate if still relevant |

## Clean / Expected Branches (No Action)
PMOVES-ClawZ, PMOVES-E2B-Danger-Room, PMOVES-E2B-Danger-Room-Desktop, PMOVES-E2b-Spells, PMOVES-MAI-UI, PMOVES-Neo4j (release/5.26.0), PMOVES-Pipecat, PMOVES-Pinokio-Ultimate-TTS-Studio, PMOVES-Tailscale, PMOVES-Ultimate-TTS-Studio, PMOVES-autoresearch (master), PMOVES-llama-throughput-lab (detached), PMOVES-surf, PMOVES-space-agent, Pmoves-AgentGym-RL, Pmoves-cipher, pmoves-e2b-mcp-server

## Summary
| Category | Count | Bulk Action |
|----------|-------|-------------|
| Dirty working tree | 10 | Commit, discard, or advance branch |
| Not initialized | 5 | `git submodule update --init` |
| Stale PMOVES.AI-Edition-Hardened | 14 | Advance gitlink to main/v1.9 |
| Stale feature/merge branches | 4 | Advance gitlink to main |
| Clean / expected | 17 | No action |
| **Total** | **50** | |
