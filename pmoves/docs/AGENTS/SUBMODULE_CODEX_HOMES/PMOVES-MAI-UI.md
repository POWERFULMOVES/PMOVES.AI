# Codex Home Overlay: PMOVES-MAI-UI

Scope:
- PMOVES-MAI-UI submodule integration lane alignment for PMOVES hardened release operations.

Core checks:
- `git submodule status -- PMOVES-MAI-UI`
- `make -C pmoves submodule-layer-validate-one SUBMODULE=PMOVES-MAI-UI`
- `make -C pmoves submodule-branch-policy-check`

Related parity tokens:
- `/worktree:status`
- `/github:checks`
- `/deploy:status`


