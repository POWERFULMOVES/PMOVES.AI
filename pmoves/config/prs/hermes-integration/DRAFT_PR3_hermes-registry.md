# DRAFT PR: feat(hermes-registry): add hermes-agent to agent taxonomy

**Branch**: `feat/hermes-agent-registry`
**Base**: `origin/main`
**Commits**: `17bf06180`
**Status**: READY FOR REVIEW (low risk)
**Size**: 2 files, 65 lines

## Scope
- `agent_registry.yaml`: hermes-agent entry with node affinity
- `agent_signatures.yaml`: HERMES Agent co-author entry

## Why Draft?
Minimal risk, but need Z890-Claude ACK on:
- `sandbox_policy: OpenShell` (does Z890 use different policy?)
- Co-author entry format matches AGENTS.md spec

## Pre-merge Checklist
- [ ] Z890-Claude ACK on sandbox policy
- [ ] Signature format validated against `pmoves/docs/AGENTS/AGENTS.md_FORMAT.md`
- [ ] No duplicate agent IDs in registry
