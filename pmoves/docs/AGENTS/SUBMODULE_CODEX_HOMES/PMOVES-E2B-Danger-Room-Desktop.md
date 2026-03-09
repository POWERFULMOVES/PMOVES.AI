# Codex Home Overlay: PMOVES-E2B-Danger-Room-Desktop

Scope:
- PMOVES-E2B-Danger-Room-Desktop submodule integration lane alignment for PMOVES hardened release operations.

Core checks:
- `git submodule status -- PMOVES-E2B-Danger-Room-Desktop`
- `make -C pmoves submodule-layer-validate-one SUBMODULE=PMOVES-E2B-Danger-Room-Desktop`
- `make -C pmoves submodule-branch-policy-check`

Related parity tokens:
- `/worktree:status`
- `/github:checks`
- `/deploy:status`


