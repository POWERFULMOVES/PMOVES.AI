# Codex Home Overlay: Pmoves-AgentGym-RL

Scope:
- Pmoves-AgentGym-RL submodule integration lane alignment for PMOVES hardened release operations.

Core checks:
- `git submodule status -- Pmoves-AgentGym-RL`
- `make -C pmoves submodule-layer-validate-one SUBMODULE=Pmoves-AgentGym-RL`
- `make -C pmoves submodule-branch-policy-check`

Related parity tokens:
- `/worktree:status`
- `/github:checks`
- `/deploy:status`


