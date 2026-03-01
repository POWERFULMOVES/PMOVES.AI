# Codex Home Overlay: PMOVES-Ultimate-TTS-Studio

Scope:
- PMOVES-Ultimate-TTS-Studio submodule integration lane alignment for PMOVES hardened release operations.

Core checks:
- `git submodule status -- PMOVES-Ultimate-TTS-Studio`
- `make -C pmoves submodule-layer-validate-one SUBMODULE=PMOVES-Ultimate-TTS-Studio`
- `make -C pmoves submodule-branch-policy-check`

Related parity tokens:
- `/worktree:status`
- `/github:checks`
- `/deploy:status`


