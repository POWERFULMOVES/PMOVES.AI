# Codex Home Overlay: PMOVES-llama-throughput-lab

Scope:
- PMOVES-llama-throughput-lab submodule integration lane alignment for PMOVES hardened release operations.

Core checks:
- `git submodule status -- PMOVES-llama-throughput-lab`
- `make -C pmoves submodule-layer-validate-one SUBMODULE=PMOVES-llama-throughput-lab`
- `make -C pmoves submodule-branch-policy-check`

Related parity tokens:
- `/worktree:status`
- `/github:checks`
- `/deploy:status`


