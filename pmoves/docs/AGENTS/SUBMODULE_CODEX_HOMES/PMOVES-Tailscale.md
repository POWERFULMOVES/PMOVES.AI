# Codex Home Overlay: PMOVES-Tailscale

Scope:
- PMOVES-Tailscale submodule integration lane alignment for PMOVES hardened release operations.

Core checks:
- `git submodule status -- PMOVES-Tailscale`
- `make -C pmoves submodule-layer-validate-one SUBMODULE=PMOVES-Tailscale`
- `make -C pmoves submodule-branch-policy-check`

Related parity tokens:
- `/worktree:status`
- `/github:checks`
- `/deploy:status`


