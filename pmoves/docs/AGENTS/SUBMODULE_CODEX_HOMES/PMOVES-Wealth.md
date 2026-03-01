# Codex Home Overlay: PMOVES-Wealth

Scope:
- PMOVES-Wealth submodule integration lane alignment for PMOVES hardened release operations.

Core checks:
- `git submodule status -- PMOVES-Wealth`
- `make -C pmoves submodule-layer-validate-one SUBMODULE=PMOVES-Wealth`
- `make -C pmoves submodule-branch-policy-check`

Related parity tokens:
- `/worktree:status`
- `/github:checks`
- `/deploy:status`


