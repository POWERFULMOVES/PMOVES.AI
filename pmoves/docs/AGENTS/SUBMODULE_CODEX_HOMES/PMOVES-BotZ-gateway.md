# Codex Home Overlay: PMOVES-BotZ-gateway

Scope:
- PMOVES-BotZ-gateway submodule integration lane alignment for PMOVES hardened release operations.

Core checks:
- `git submodule status -- PMOVES-BotZ-gateway`
- `make -C pmoves submodule-layer-validate-one SUBMODULE=PMOVES-BotZ-gateway`
- `make -C pmoves submodule-branch-policy-check`

Related parity tokens:
- `/worktree:status`
- `/github:checks`
- `/deploy:status`


