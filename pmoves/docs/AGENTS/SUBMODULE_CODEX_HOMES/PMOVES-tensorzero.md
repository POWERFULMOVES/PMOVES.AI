# Codex Home Overlay: PMOVES-tensorzero

Scope:
- PMOVES-tensorzero submodule integration lane alignment for PMOVES hardened release operations.

Core checks:
- `git submodule status -- PMOVES-tensorzero`
- `make -C pmoves submodule-layer-validate-one SUBMODULE=PMOVES-tensorzero`
- `make -C pmoves submodule-branch-policy-check`

Related parity tokens:
- `/worktree:status`
- `/github:checks`
- `/deploy:status`


