# Codex Home Overlay: Pmoves-Jellyfin-AI-Media-Stack

Scope:
- Pmoves-Jellyfin-AI-Media-Stack submodule integration lane alignment for PMOVES hardened release operations.

Core checks:
- `git submodule status -- Pmoves-Jellyfin-AI-Media-Stack`
- `make -C pmoves submodule-layer-validate-one SUBMODULE=Pmoves-Jellyfin-AI-Media-Stack`
- `make -C pmoves submodule-branch-policy-check`

Related parity tokens:
- `/worktree:status`
- `/github:checks`
- `/deploy:status`


