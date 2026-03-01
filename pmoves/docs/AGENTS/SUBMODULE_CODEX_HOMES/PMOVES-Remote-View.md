# Codex Home Overlay: PMOVES-Remote-View

Scope:
- PMOVES-Remote-View submodule integration lane alignment for PMOVES hardened release operations.

Core checks:
- `git submodule status -- PMOVES-Remote-View`
- `make -C pmoves submodule-layer-validate-one SUBMODULE=PMOVES-Remote-View`
- `make -C pmoves submodule-branch-policy-check`

Related parity tokens:
- `/worktree:status`
- `/github:checks`
- `/deploy:status`


