# Codex Home Overlay: PMOVES-Headscale

Scope:
- PMOVES-Headscale submodule integration lane alignment for PMOVES hardened release operations.

Core checks:
- `git submodule status -- PMOVES-Headscale`
- `make -C pmoves submodule-layer-validate-one SUBMODULE=PMOVES-Headscale`
- `make -C pmoves submodule-branch-policy-check`

Related parity tokens:
- `/worktree:status`
- `/github:checks`
- `/deploy:status`


