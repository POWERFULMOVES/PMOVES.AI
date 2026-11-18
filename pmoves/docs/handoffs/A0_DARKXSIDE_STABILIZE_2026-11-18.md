# Handoff: 5090-CLAUDE → a0-DARKXSIDE — node stabilization (2026-11-18)

**From:** 5090-CLAUDE (Claude Code on node 5090, signing card `5090-claude`)
**To:** a0-DARKXSIDE (Agent Zero Launcher instance; `docker ps` names the container `a0-inst-PMOVES-AGInTZeR0-DARKXSIDE-mufqkw20`, and `pmoves/docker-compose.agent-zero-instances.yml` registers the same usr dir as compose service `pmoves-agent-zero-darkxside-inst`)
**Lane:** `fix/a0-config-reaches-instances-2026-11-18` (register CLAIM 2026-11-18T18:07Z)
**Channel:** the instance connector API requires an instance session, and the token available to my session belongs to the compose A0, so this handoff travels as a file. The operator pastes this path into the a0-DARKXSIDE chat (the instance has Host access to the GitHub folder). Reply by writing `A0_DARKXSIDE_STABILIZE_2026-11-18.REPLY.md` beside this file.

## What 5090-CLAUDE measured about this instance (2026-11-08 → 2026-11-18)

1. **Crash loop fixed on 2026-11-08, container-local.** `[program:signal_bridge]` in `/etc/supervisor/conf.d/supervisord.conf` now has `autostart=false` (backup `supervisord.conf.bak-20261108`). The upstream image's supervisor event listener kills PID 1 on any program FATAL, and the unconfigured Signal bridge went FATAL every five minutes. Plugin toggles do not edit supervisord program blocks. The fix is lost whenever the image is replaced.
2. **Startup gap of 6–8 minutes.** `run_ui.py` blocks on `initialize_chats().result_sync()` before uvicorn listens. `/a0/usr/chats` holds 94 chats, 2,867 files, 262 MB over the Windows bind mount. Heaviest chat ids: `RrUOe5kN` (28 MB), `GORMW3Kt` (22 MB), `etOeaPDG` (19 MB), `IuhJIh40` (16 MB), `qVRyjiGA` (12 MB), `dl9okoIl` (12 MB). A Launcher restart inside that window resets the clock and looks like "down".
3. **Time Travel snapshots failing.** `/a0/usr/projects/pmoves_ai/research/models` holds about 2.7 GB of untracked weights (deberta-v3-large safetensors 1.6 GB, agentjev onnx 1.0 GB). The plugin's `git add -f -A` exceeds its 20 s timeout and strands `repo.git/index.lock`; the retention sweep clears it every 6 h and it re-strands. The plugin has no per-project opt-out.
4. **Memory consolidation timeouts.** 37 timeouts against 6 successes under the 60 s cap hard-coded in `_memory/helpers/memory_consolidation.py`; the utility model is glm-5.3-flash via the zai_coding provider.
5. **Plaintext provider keys** sit in `/a0/usr/projects/pmoves_ai/.a0proj/mcp_servers.json` (the composio key already returns "Invalid API key"; coinbase and composio_platform return 401; the titanmail MCP on loopback port 8765 is not running). These belong in Agent Zero secrets placeholders and must be rotated through the PMOVES secrets funnel. Never paste a value into chat, a file, or a reply. This file names the location only until the keys are rotated; drop the path from the reply once they are.
6. **Model presets.** This instance holds six presets (Default, Efficiency, Power, PMOVES, Agentic, Voice). The PMOVES repo generator (`make -C pmoves a0-model-sync`) is drifted and feeds only the compose A0's usr directory. Do not let it be pointed at this instance until the registry path is healthy.

## Asks for a0-DARKXSIDE (inside the container, in order, each with evidence)

- [ ] **A. Archive the six heaviest chats.** Export each one (UI export or a copy of its folder into `/a0/usr/downloads/chat-archive-2026-11-18/`), then delete it through the UI or the connector's `chat_delete`. Do not move chat folders out from under a running instance; the loaded contexts would re-persist them. Report before/after chat count and total size, and the next boot's gap between "Initializing Agent Zero components" and "Starting UI/API server" in the container log.
- [ ] **B. Move the model weights out of the project tree** to `/a0/usr/downloads/models/`, leave a two-line README at the old location pointing there, and confirm the next Time Travel snapshot completes with no `index.lock` left after 30 minutes.
- [ ] **C. Replace the plaintext keys** in `.a0proj/mcp_servers.json` with secrets placeholders and list, by name only, which keys the operator must rotate.
- [ ] **D. Leave supervisord and the Signal plugin alone.** If Signal is wanted, say so in the reply; the bridge gets configured first.
- [ ] **E. Write the reply file** with what changed, what was refused, and any measurement that contradicts the above.

## What 5090-CLAUDE is doing in the same lane

- Docs: Launcher instances versus the compose service, upstream-versus-fork Launcher provenance, env overrides, the supervisord fix, and the startup gap (`pmoves/docs/operations/AGENT_ZERO_API.md`, `pmoves/services/agent-zero/README.md`).
- A pull request on `POWERFULMOVES/PMOVES-a0-launcher` that merges upstream v1.10 and points publish and content at the fork so a fork build can exist. Tagging, releasing, and installing stay the operator's call.
- Submodule pin promotion stays MAVIS's lane; no gitlink is touched here.

Three-body: delivery = 5090-CLAUDE and a0-DARKXSIDE, control = DARKXSIDE (operator), memory = this file plus the register row.
