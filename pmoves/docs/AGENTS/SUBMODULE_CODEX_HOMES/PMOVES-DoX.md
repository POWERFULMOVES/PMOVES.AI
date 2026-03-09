# Codex Home Overlay: PMOVES-DoX

Scope:
- PMOVES-DoX submodule integration lane alignment for PMOVES hardened release operations.

Core checks:
- `git submodule status -- PMOVES-DoX`
- `make -C pmoves submodule-layer-validate-one SUBMODULE=PMOVES-DoX`
- `make -C pmoves submodule-branch-policy-check`

Related parity tokens:
- `/worktree:status`
- `/github:checks`
- `/deploy:status`


