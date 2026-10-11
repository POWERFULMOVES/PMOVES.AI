# 4-Lane Operator Roadmap — Research + Dry-Run Plan

_Date: 2026-10-11 · Author: CRUSH-SPARK (KIMI) · Claim: `docs/roadmap-4lane-research-dryrun` (TTL 96h)_
_Operator directive (DARKXSIDE 2026-10-09): Composio MCP on KVMs, VSS comfy-voice stand-up, Jetson combiner updates, voice+sentinel fleet sweep, auto-research pipeline. All planned and dry-run before execution._

## Lane 1 — Composio MCP on KVMs

**State:** Two forks exist and are checked out — `PMOVES-composio` (pinned upstream `next` @ `027b773`, verdict `not_acp`) and `pmoves-composio-mcp-plugin` (upstream master `bbcb9cc`). A third fork `Pmoves-composio-comm-skills` exists remotely. Currently the node consumes the **hosted** Composio Connect MCP (`https://connect.composio.dev/mcp`, in-band OAuth, live through 2026-10-11).

**KVM2 self-host plan exists but is blocked** (per `MCP_SERVER_NODE_MAP.md` + titanmail spec, 2026-10-09):
- SSH to kvm2 (167.88.38.57 / VM 630926) unreachable from this host; `HOSTINGER_SSH_PRIVATE_KEY` in `env.tier-agent` structurally truncated.

**Dry-run steps:**
1. Repair the Hostinger SSH key through the funnel (`secrets-funnel`) — do NOT hand-place in `env.tier-*`.
2. Verify `ssh kvm2 echo ok` from SPARK (or via tailnet route).
3. Deploy `@composio/mcp` Docker on kvm2: `/opt/composio-mcp/.env` carrying `COMPOSIO_API_KEY`, loopback bind, SSE health probe.
4. Wire `COMPOSIO_MCP_ENDPOINT=http://kvm2:<PORT>/sse` into `mcp_inventory.json` (streamable-http) once tailnet route exists.
5. A0 on 5090 is also working Composio — **coordinate before any deploy** to avoid duplicate kvm selections.

## Lane 2 — VSS (comfy voice) service

**State:** `PMOVES-Spark-VSS` = fork of NVIDIA's Video Search & Summarization blueprint (GPU vision agents + VSS Agent MCP layer). Submodule landed via #2277, but on elder-melchor `/opt/pmoves-main/PMOVES-Spark-VSS` is **EMPTY/broken** (stale worktree metadata, no payload). "Comfy voice" as a phrase appears only in the roadmap claim — this lane conjoins VSS repair with the voice stack (Lane 4).

**Dry-run steps:**
1. Re-init the VSS submodule cleanly on elder-melchor (remove stale worktree metadata, `git submodule update --init PMOVES-Spark-VSS`).
2. Inventory the blueprint's GPU requirements vs SPARK GB10 (sm_121) — the ComfyUI+sageattn H3 render path is already proven on this node (`pmoves/tools/comfyui/`).
3. Define the VSS↔voice junction: VSS Agent tools (search/summarize/QA/report) exposed via MCP → consumed by voice layer (Flute) so elder-melchor can *speak* video-query results.
4. Compose stanza + profile (`spark-vss`, port from allocator), healthz probe, then canary on SPARK before elder-melchor.

## Lane 3 — Jetson combiner updates

**State:** JONS-1/2/3 (Orin Nano Super) provisioned with JetPack 7 lane artifacts (`deploy/provision/jetson/`, `docker-compose.jetson-edge.override.yml`, room `jons-edge.room.control`, agent signatures jetson-1/2/3). Provisioning **playlist** = DARKXSIDE AI playlist `PLGupOT04oMfok7S8W8Js7lZZIlhM8ufc8` (fleet provisioning videos). Crawl path: `yt_playlist_crawl.py` inside pmoves-yt (OAuth vault-first per #3280), or `yt-dlp --flat-playlist` for listing only — `/yt/playlist` API hangs at ~2.4k scale.

**Dry-run steps:**
1. Crawl/refresh playlist rows (namespace `darkxside`), filter provisioning-script videos.
2. Per JONS node: `make jetson-verify DEVICE=nemotron-N` baseline before touching anything.
3. Diff current JONS firmware/compose against the playlist's latest provisioning scripts.
4. Apply updates one node at a time (sequenced, not parallel), re-verify each.

## Lane 4 — Voice + Sentinel fleet sweep (all AGnTz)

**Current state (measured):**
- Voice services exist (flute-gateway :8055, ultimate-tts-studio, cast-tts, voice-relay, voice-sampler) but **no per-node expected-roster guarantee**; B850/Knuckles has only an optional ROCm overlay (`make up-voice-amd`, chatterbox engine proven 2026-08-01).
- **fleet-sentinel is coded + compose-wired but deployed nowhere** (2026-09-09 WEALTH_TRI_RECON: "the overwatch role has no registry to watch"). PR #2934 RELEASE still owed.
- Open Jev: research corpus only — `open-jev-deberta-v3-large` (Apache-2.0, 256-token cap, verdict defer), **AgentJev-0.6B ONNX benchmarked 129ms/decision on SPARK**, Laya 32.8ms p50 local. Compaction eval says do NOT use Jev for compaction (loses to summary path) — decision-routing is the right role.
- Cipher in-session watching: cipher MCP auth is now enforce-mode (spark-claude fixed; Crush relaunch via `crush-pmoves` pending spark-crush card). Elder-melchor voice requirements per `HERMES_AGENT_INTEGRATION.md`: wake-word activation, Flute prosodic TTS with pause→BPM mapping, HIPAA auto-redaction.

**Dry-run steps (sequenced):**
1. **Knuckles voice**: `make up-voice-amd` full Docker build validation (overlay exists, never end-to-end tested), chatterbox engine, Flute routing check.
2. **fleet-sentinel deployment**: stand up on SPARK first (`:8116`), give it a registry to watch (announce listener + 30s poller), then replicate to elder-melchor/Knuckles.
3. **Open Jev in-session watcher**: prototype sentinel-side decision watcher using AgentJev-0.6B ONNX (local, fast, already benchmarked here) — watches agent turns, emits yes/no routing + keep/drop advisories on NATS; TypeSafe Jev (live key, 236-276ms p50) as cloud fallback.
4. **Cipher watching**: per-harness cipher MCP attachment audit (Crush via crush-pmoves token; Claude via roster fixes #3342/#3343; Hermes via plugin catalog).
5. **elder-melchor serving**: creator pipeline services (VSS Lane 2 + voice) resident on-node.

## Lane 5 (adjacent) — Auto-research pipeline

`PMOVES-autoresearch/` = Karpathy autoresearch fork (nanochat-derived, overnight LLM experiment loop) with a PMOVES `nats_reporter.py` integration already present. Untracked in the superproject — needs submodule onboarding (`.gitmodules` + fork_registry + integration contract) before fleet use.

## Cross-lane notes

- **A0's Jev decisioning**: lives in the A0 sidecar project (`.a0proj/skills/jev-decision-routing`, RANCH branch) + TypeSafe query experiments, not this repo. "byCloud says it's turning into the geometry bus" — **no in-repo evidence found** (zero bycloud matches); treat as operator/A0-side context to confirm before baking into architecture docs.
- **Anthropic village-rule plugin**: not yet researched in-repo; separate research spike when operator names the plugin.
- **crush-acp quarantine**: registry dossier (#38) flags crush-acp declares no `authMethods` — natural Crush lane; folded into this claim's scope.

## Execution order (proposed)

1. Lane 4 steps 1-2 (Knuckles voice + sentinel) — lowest risk, unblocks "AGnTz have voice + sentinel"
2. Lane 2 (VSS repair → comfy voice junction)
3. Lane 3 (Jetson updates, sequenced)
4. Lane 1 (Composio KVM — blocked on SSH key repair + A0 coordination)
5. Lane 5 (autoresearch onboarding, parallel/docs-only)

Each lane gets its own CLAIM/RELEASE before mutation. NATS HOLD is lifted (2026-10-11, operator authority, evidence in `NATS_CUTOVER_HOLD.md`).
