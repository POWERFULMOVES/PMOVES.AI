# Codex Home Overlay: PMOVES-Creator

Scope:
- PMOVES-Creator submodule integration lane alignment for PMOVES hardened release operations.

Core checks:
- `git submodule status -- PMOVES-Creator`
- `make -C pmoves submodule-layer-validate-one SUBMODULE=PMOVES-Creator`
- `make -C pmoves submodule-branch-policy-check`

Related parity tokens:
- `/worktree:status`
- `/github:checks`
- `/deploy:status`


