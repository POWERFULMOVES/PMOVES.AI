# Codex Home Overlay: PMOVES-ToKenism-Multi

Scope:
- PMOVES-ToKenism-Multi submodule integration lane alignment for PMOVES hardened release operations.

Core checks:
- `git submodule status -- PMOVES-ToKenism-Multi`
- `make -C pmoves submodule-layer-validate-one SUBMODULE=PMOVES-ToKenism-Multi`
- `make -C pmoves submodule-branch-policy-check`

Related parity tokens:
- `/worktree:status`
- `/github:checks`
- `/deploy:status`


