# Codex Home Overlay: PMOVES-E2B-Danger-Room

Scope:
- PMOVES-E2B-Danger-Room submodule integration lane alignment for PMOVES hardened release operations.

Core checks:
- `git submodule status -- PMOVES-E2B-Danger-Room`
- `make -C pmoves submodule-layer-validate-one SUBMODULE=PMOVES-E2B-Danger-Room`
- `make -C pmoves submodule-branch-policy-check`

Related parity tokens:
- `/worktree:status`
- `/github:checks`
- `/deploy:status`


