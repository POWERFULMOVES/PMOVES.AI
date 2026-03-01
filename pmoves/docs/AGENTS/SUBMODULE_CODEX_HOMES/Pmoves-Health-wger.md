# Codex Home Overlay: Pmoves-Health-wger

Scope:
- Pmoves-Health-wger submodule integration lane alignment for PMOVES hardened release operations.

Core checks:
- `git submodule status -- Pmoves-Health-wger`
- `make -C pmoves submodule-layer-validate-one SUBMODULE=Pmoves-Health-wger`
- `make -C pmoves submodule-branch-policy-check`

Related parity tokens:
- `/worktree:status`
- `/github:checks`
- `/deploy:status`


