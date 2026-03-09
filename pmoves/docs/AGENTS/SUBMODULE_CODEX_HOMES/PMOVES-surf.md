# Codex Home Overlay: PMOVES-surf

Scope:
- PMOVES-surf submodule integration lane alignment for PMOVES hardened release operations.

Core checks:
- `git submodule status -- PMOVES-surf`
- `make -C pmoves submodule-layer-validate-one SUBMODULE=PMOVES-surf`
- `make -C pmoves submodule-branch-policy-check`

Related parity tokens:
- `/worktree:status`
- `/github:checks`
- `/deploy:status`


