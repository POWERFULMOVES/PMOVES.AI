# Codex Home Overlay: PMOVES-AgentGym

Scope:
- PMOVES-AgentGym submodule integration lane alignment for PMOVES hardened release operations.

Core checks:
- `git submodule status -- PMOVES-AgentGym`
- `make -C pmoves submodule-layer-validate-one SUBMODULE=PMOVES-AgentGym`
- `make -C pmoves submodule-branch-policy-check`

Related parity tokens:
- `/worktree:status`
- `/github:checks`
- `/deploy:status`


