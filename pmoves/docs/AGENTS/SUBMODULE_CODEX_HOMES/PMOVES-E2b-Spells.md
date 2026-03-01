# Codex Home Overlay: PMOVES-E2b-Spells

Scope:
- PMOVES-E2b-Spells submodule integration lane alignment for PMOVES hardened release operations.

Core checks:
- `git submodule status -- PMOVES-E2b-Spells`
- `make -C pmoves submodule-layer-validate-one SUBMODULE=PMOVES-E2b-Spells`
- `make -C pmoves submodule-branch-policy-check`

Related parity tokens:
- `/worktree:status`
- `/github:checks`
- `/deploy:status`


