# Codex Home Overlay: PMOVES-Deep-Serch

Scope:
- PMOVES-Deep-Serch submodule integration lane alignment for PMOVES hardened release operations.

Core checks:
- `git submodule status -- PMOVES-Deep-Serch`
- `make -C pmoves submodule-layer-validate-one SUBMODULE=PMOVES-Deep-Serch`
- `make -C pmoves submodule-branch-policy-check`

Related parity tokens:
- `/worktree:status`
- `/github:checks`
- `/deploy:status`


