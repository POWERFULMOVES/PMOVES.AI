# Codex Home Overlay: PMOVES-n8n

Scope:
- PMOVES-n8n submodule integration lane alignment for PMOVES hardened release operations.

Core checks:
- `git submodule status -- PMOVES-n8n`
- `make -C pmoves submodule-layer-validate-one SUBMODULE=PMOVES-n8n`
- `make -C pmoves submodule-branch-policy-check`

Related parity tokens:
- `/worktree:status`
- `/github:checks`
- `/deploy:status`


