# Codex Home Overlay: PMOVES.YT

Scope:
- PMOVES.YT submodule integration lane alignment for PMOVES hardened release operations.

Core checks:
- `git submodule status -- PMOVES.YT`
- `make -C pmoves submodule-layer-validate-one SUBMODULE=PMOVES.YT`
- `make -C pmoves submodule-branch-policy-check`

Related parity tokens:
- `/worktree:status`
- `/github:checks`
- `/deploy:status`


