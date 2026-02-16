# Worktree + Submodule Audit SITREP
_Generated: 2026-02-16 03:01:59Z_

## Summary
- Worktrees discovered: **8**
- Dirty worktrees: **2**
- `.gitmodules` entries: **49**
- Submodule clean rows: **49**
- Submodule uninitialized (`-`): **0**
- Submodule drifted (`+`): **0**
- Submodule conflicts (`U`): **0**
- Recursive submodule status exit: **128**

## Worktree Status
- `C:/Users/russe/Documents/GitHub/PMOVES.AI` [codex/layered-local-prod-audit] dirty=10
  - ` M .gitignore`
  - ` m PMOVES-Archon`
  - ` m PMOVES-HiRAG`
  - ` M pmoves/Makefile`
  - ` M pmoves/docs/AGENTS/PRODUCTION_AUDIT_SUBAGENT_PLAN.md`
  - `A  pmoves/tools/submodule_integrity.py`
  - `AM pmoves/tools/submodule_sitrep.py`
  - `?? pmoves/docs/AGENTS/WORKTREE_SUBMODULE_AUDIT_SITREP_2026-02-16.md`
  - `?? pmoves/docs/SUBMODULE_ALIGNMENT_SITREP_2026-02-16.md`
  - `?? pmoves/tools/worktree_sitrep.py`
- `C:/Users/russe/Documents/GitHub/PMOVES.AI-hardened-audit` [detached] dirty=0
- `C:/Users/russe/Documents/GitHub/PMOVES.AI-hardened-ci` [pr/hardened-ghcr-standardize] dirty=0
- `C:/Users/russe/Documents/GitHub/PMOVES.AI-main-audit` [fix/main-audit-tooling-submodule-integrity] dirty=30
  - ` M PMOVES-Creator`
  - ` M PMOVES-Danger-infra`
  - ` M PMOVES-DoX`
  - ` M PMOVES-E2B-Danger-Room`
  - ` M PMOVES-E2B-Danger-Room-Desktop`
  - ` M PMOVES-E2b-Spells`
  - ` M PMOVES-HiRAG`
  - ` M PMOVES-Pinokio-Ultimate-TTS-Studio`
  - ` M PMOVES-Pipecat`
  - ` M PMOVES-Remote-View`
  - ` M PMOVES-Tailscale`
  - ` M PMOVES-Ultimate-TTS-Studio`
  - ` M PMOVES-Wealth`
  - ` M PMOVES-crush`
  - ` M PMOVES-llama-throughput-lab`
  - ` M PMOVES-supabase`
  - ` M PMOVES-surf`
  - ` M PMOVES-tensorzero`
  - ` M PMOVES-transcribe-and-fetch`
  - ` M PMOVES.YT`
- `C:/Users/russe/Documents/GitHub/PMOVES.AI-pr624-clean` [codex/layered-local-prod-audit-clean] dirty=0
- `C:/Users/russe/Documents/GitHub/PMOVES.AI-slice-ci-ghcr` [pr/ci-ghcr-auth-hardening] dirty=0
- `C:/Users/russe/Documents/GitHub/PMOVES.AI-slice-cipher` [pr/cipher-mcp-bridge] dirty=0
- `C:/Users/russe/Documents/GitHub/PMOVES.AI-submodule-audit` [feat/submodule-layer-deterministic-validation] dirty=0

## Recursive Submodule Error
`fatal: no submodule mapping found in .gitmodules for path 'PMOVES-E2B-Danger-Room-Deskdesktop'
fatal: failed to recurse into submodule 'PMOVES-A2UI'`

## Operator Guidance
1. Run this report before cleanup: `make -C pmoves worktree-sitrep`.
2. If recursive exit is non-zero, fix nested `.gitmodules` mapping before pointer cleanup.
3. Clean only one wave at a time:
   - Wave A: root worktree + active feature worktree.
   - Wave B: main-audit/reference worktrees.
   - Wave C: detached/archive worktrees.
