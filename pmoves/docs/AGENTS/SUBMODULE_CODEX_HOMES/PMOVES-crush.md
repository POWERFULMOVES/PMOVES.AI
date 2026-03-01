# Codex Home Overlay: PMOVES-crush

Scope:
- PMOVES-crush submodule integration lane alignment for PMOVES hardened release operations.

Core checks:
- `git submodule status -- PMOVES-crush`
- `make -C pmoves submodule-layer-validate-one SUBMODULE=PMOVES-crush`
- `make -C pmoves submodule-branch-policy-check`

Related parity tokens:
- `/worktree:status`
- `/github:checks`
- `/deploy:status`


