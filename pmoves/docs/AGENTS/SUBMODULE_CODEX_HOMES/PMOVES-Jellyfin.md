# Codex Home Overlay: PMOVES-Jellyfin

Scope:
- PMOVES-Jellyfin submodule integration lane alignment for PMOVES hardened release operations.

Core checks:
- `git submodule status -- PMOVES-Jellyfin`
- `make -C pmoves submodule-layer-validate-one SUBMODULE=PMOVES-Jellyfin`
- `make -C pmoves submodule-branch-policy-check`

Related parity tokens:
- `/worktree:status`
- `/github:checks`
- `/deploy:status`


