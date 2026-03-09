# Codex Home Overlay: PMOVES-A2UI

Scope:
- PMOVES-A2UI submodule integration lane alignment for PMOVES hardened release operations.

Core checks:
- `git submodule status -- PMOVES-A2UI`
- `make -C pmoves submodule-layer-validate-one SUBMODULE=PMOVES-A2UI`
- `make -C pmoves submodule-branch-policy-check`

Related parity tokens:
- `/worktree:status`
- `/github:checks`
- `/deploy:status`


