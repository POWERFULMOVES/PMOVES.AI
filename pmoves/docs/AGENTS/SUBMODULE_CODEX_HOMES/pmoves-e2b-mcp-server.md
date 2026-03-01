# Codex Home Overlay: pmoves-e2b-mcp-server

Scope:
- pmoves-e2b-mcp-server submodule integration lane alignment for PMOVES hardened release operations.

Core checks:
- `git submodule status -- pmoves-e2b-mcp-server`
- `make -C pmoves submodule-layer-validate-one SUBMODULE=pmoves-e2b-mcp-server`
- `make -C pmoves submodule-branch-policy-check`

Related parity tokens:
- `/worktree:status`
- `/github:checks`
- `/deploy:status`


