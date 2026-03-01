# Codex Home Overlay: PMOVES-supabase

Scope:
- PMOVES-supabase submodule integration lane alignment for PMOVES hardened release operations.

Core checks:
- `git submodule status -- PMOVES-supabase`
- `make -C pmoves submodule-layer-validate-one SUBMODULE=PMOVES-supabase`
- `make -C pmoves submodule-branch-policy-check`

Related parity tokens:
- `/worktree:status`
- `/github:checks`
- `/deploy:status`


