# Codex Home Overlay: PMOVES-Open-Notebook

Scope:
- PMOVES-Open-Notebook submodule integration lane alignment for PMOVES hardened release operations.

Core checks:
- `git submodule status -- PMOVES-Open-Notebook`
- `make -C pmoves submodule-layer-validate-one SUBMODULE=PMOVES-Open-Notebook`
- `make -C pmoves submodule-branch-policy-check`

Related parity tokens:
- `/worktree:status`
- `/github:checks`
- `/deploy:status`


