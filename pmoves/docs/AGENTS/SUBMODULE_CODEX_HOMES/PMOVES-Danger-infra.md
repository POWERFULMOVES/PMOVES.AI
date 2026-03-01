# Codex Home Overlay: PMOVES-Danger-infra

Scope:
- PMOVES-Danger-infra submodule integration lane alignment for PMOVES hardened release operations.

Core checks:
- `git submodule status -- PMOVES-Danger-infra`
- `make -C pmoves submodule-layer-validate-one SUBMODULE=PMOVES-Danger-infra`
- `make -C pmoves submodule-branch-policy-check`

Related parity tokens:
- `/worktree:status`
- `/github:checks`
- `/deploy:status`


