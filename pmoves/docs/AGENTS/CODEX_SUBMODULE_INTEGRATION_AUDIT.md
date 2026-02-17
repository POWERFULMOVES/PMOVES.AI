# Codex Submodule Integration Audit
_Generated: 2026-02-14_

## Summary
- Total submodules scanned: **41**
- Submodules with Claude context assets: **3**
- Submodules with Codex artifacts or references: **10**
- Focus modules (CHIT/Geometry/Agentic stack): **8**
- Focus modules with Codex coverage: **8**

## Focus Alignment (PMOVES priorities)
- CHIT Geometry Bus, EvoSwarm, Flute, Gateway, and BotZ modules are prioritized.
- Modules marked `high` need Codex-facing guidance next.

## Matrix
| Submodule | Claude | AGENTS | Codex Artifacts | Focus Terms | Priority | Recommendation |
| --- | --- | --- | --- | --- | --- | --- |
| `PMOVES-Archon` | yes | yes | `PMOVES-Archon/.codex` | 141 | `good` | Keep Codex + Claude docs aligned; no immediate action. |
| `PMOVES-BoTZ` | yes | yes | `PMOVES-BoTZ/config/codex` | 66 | `good` | Keep Codex + Claude docs aligned; no immediate action. |
| `PMOVES-ToKenism-Multi` | yes | no | `PMOVES-ToKenism-Multi/.codex` | 33 | `good` | Keep Codex + Claude docs aligned; no immediate action. |
| `PMOVES-A2UI` | no | no | - | 26 | `low` | No immediate action required unless this module becomes active. |
| `PMOVES-AgentGym` | no | no | - | 0 | `low` | No immediate action required unless this module becomes active. |
| `PMOVES-Danger-infra` | no | no | - | 0 | `low` | No immediate action required unless this module becomes active. |
| `PMOVES-Deep-Serch` | no | no | - | 0 | `low` | No immediate action required unless this module becomes active. |
| `PMOVES-DoX` | no | no | - | 0 | `low` | No immediate action required unless this module becomes active. |
| `PMOVES-E2B-Danger-Room` | no | no | - | 0 | `low` | No immediate action required unless this module becomes active. |
| `PMOVES-E2B-Danger-Room-Desktop` | no | no | - | 0 | `low` | No immediate action required unless this module becomes active. |
| `PMOVES-E2b-Spells` | no | no | - | 0 | `low` | No immediate action required unless this module becomes active. |
| `PMOVES-Headscale` | no | no | - | 0 | `low` | No immediate action required unless this module becomes active. |
| `PMOVES-Jellyfin` | no | no | - | 0 | `low` | No immediate action required unless this module becomes active. |
| `PMOVES-MAI-UI` | no | no | - | 0 | `low` | No immediate action required unless this module becomes active. |
| `PMOVES-Open-Notebook` | no | no | - | 0 | `low` | No immediate action required unless this module becomes active. |
| `PMOVES-Pinokio-Ultimate-TTS-Studio` | no | no | - | 0 | `low` | No immediate action required unless this module becomes active. |
| `PMOVES-Remote-View` | no | no | - | 0 | `low` | No immediate action required unless this module becomes active. |
| `PMOVES-Tailscale` | no | no | - | 0 | `low` | No immediate action required unless this module becomes active. |
| `PMOVES-Ultimate-TTS-Studio` | no | no | - | 0 | `low` | No immediate action required unless this module becomes active. |
| `PMOVES-crush` | no | no | - | 0 | `low` | No immediate action required unless this module becomes active. |
| `PMOVES-llama-throughput-lab` | no | no | - | 0 | `low` | No immediate action required unless this module becomes active. |
| `PMOVES-n8n` | no | no | - | 0 | `low` | No immediate action required unless this module becomes active. |
| `PMOVES-supabase` | no | no | - | 0 | `low` | No immediate action required unless this module becomes active. |
| `PMOVES-surf` | no | no | - | 0 | `low` | No immediate action required unless this module becomes active. |
| `PMOVES-tensorzero` | no | no | - | 0 | `low` | No immediate action required unless this module becomes active. |
| `PMOVES-transcribe-and-fetch` | no | yes | - | 14 | `medium` | Security remediation in progress (3 CRITICAL fixed). Rotate Supabase JWT and Langfuse keys before public release. |
| `PMOVES.YT` | no | no | - | 0 | `low` | No immediate action required unless this module becomes active. |
| `Pmoves-AgentGym-RL` | no | no | - | 0 | `low` | No immediate action required unless this module becomes active. |
| `Pmoves-Health-wger` | no | no | - | 0 | `low` | No immediate action required unless this module becomes active. |
| `Pmoves-Jellyfin-AI-Media-Stack` | no | no | - | 0 | `low` | No immediate action required unless this module becomes active. |
| `Pmoves-hyperdimensions` | no | no | - | 0 | `low` | No immediate action required unless this module becomes active. |
| `Pmoves-open-notebook` | no | no | - | 0 | `low` | No immediate action required unless this module becomes active. |
| `pmoves-e2b-mcp-server` | no | no | - | 7 | `low` | No immediate action required unless this module becomes active. |
| `pmoves/integrations/archon` | no | no | - | 0 | `low` | No immediate action required unless this module becomes active. |
| `PMOVES-Agent-Zero` | no | no | `PMOVES-Agent-Zero/.codex` | 102 | `medium` | DoX branch reset (PR #5). Validate Codex docs are complete and linked from module README. |
| `PMOVES-BotZ-gateway` | no | no | `PMOVES-BotZ-gateway/.codex` | 179 | `medium` | Validate Codex docs are complete and linked from module README. |
| `PMOVES-Creator` | no | no | `PMOVES-Creator/.codex` | 0 | `medium` | Validate Codex docs are complete and linked from module README. |
| `PMOVES-HiRAG` | no | no | `PMOVES-HiRAG/.codex` | 0 | `medium` | Validate Codex docs are complete and linked from module README. |
| `PMOVES-Pipecat` | no | no | `PMOVES-Pipecat/.codex` | 6 | `medium` | Validate Codex docs are complete and linked from module README. |
| `PMOVES-Wealth` | no | yes | `PMOVES-Wealth/.codex` | 13 | `medium` | Validate Codex docs are complete and linked from module README. |
| `Pmoves-cipher` | no | no | - | 46 | `medium` | Validate Codex docs are complete and linked from module README. |

## Update Log

### 2026-02-16 — Branch Consolidation & Security Audit
- PRs merged to Hardened: #640 (Agent Zero audit), #641 (branch strategy docs),
  #643 (submodule sync targets), #645 (Known Roads infra), #646 (CI sudo fix)
- PRs fixed, CI re-running: #633 (eval+cipher), #634 (hf-mcp security),
  #642 (integration-gate), #644 (namespace publishing)
- Agent Zero DoX branch reset: PR #4 closed, PR #5 created (Hardened + 3 DoX commits)
- transcribe-and-fetch security audit: 3 CRITICAL, 6 HIGH, 8 MEDIUM findings
- PMOVES-transcribe-and-fetch promoted from `low` → `medium` priority (planned public release)

### 2026-02-16 — PR #634 Gitlink Sync
- PR #634 synced 16 submodule gitlinks to their latest upstream commits
- Fork architecture documented in `pmoves/docs/SUBMODULE_FORK_ARCHITECTURE.md`
- Remaining Lane D work: integration contract check baseline, legacy `pmoves/vendor/` migration

## Recommended Next Steps
1. Add Codex quickstart sections to all `high` priority modules.
2. Reuse shared Codex runbooks for CHIT, EvoSwarm, Flute, and Gateway workflows.
3. Keep module-level `AGENTS.md` and Codex docs in sync whenever interfaces change.
4. Re-run this audit after submodule syncs and release cuts.
5. Validate `make -C pmoves integration-contract-check-baseline` against updated gitlinks.

