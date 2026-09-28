# Pipecat Schooling — the correspondence map (2026-09-15)

**Author:** HERMES-AGENT (elder-melchor) · **Status:** research mapping, per operator direction (DARKXSIDE)
**Lane:** none yet (schooling only — no fork changes, no topology changes in this pass)
**Forks under review:** `Pmoves-pipecat-context-hub`, `Pmoves-pipecat-client-web-transports`

> The operator's framing: *"all flutes need to be avail on tailnet and mesh — that's why
> they're there; that's why pipecat context and transport repos [were] forked; we should
> review like z890 did [the] nats repo."* Same shape as the NATS schooling
> (`nats-schooling-mapping-2026-09-11.md`): study what we forked, map it back onto the fleet,
> name the patterns that eluded us.

---

## 1. Measured now vs designed (the delta)

| Dimension | Fleet reality (measured 2026-09-15) | Fork/spec target |
|---|---|---|
| Flute tailnet publish | **ONE node live** (elder-melchor :8055, this session). All others loopback (`${FLUTE_BIND:-127.0.0.1}` default) — the 10061 fleet-wide fallback failure | Every GPU node's flute reachable at `http://pmoves-<node>:8055` |
| Fleet voice routing | `VOICE_HOST_AFFINITY` exists (compose :5196 — swaps engine URLs to `pmoves-<node>` tailnet hostnames) but **disabled by default**, fail-open | Opt-in per node; no health-aware routing |
| Realtime duplex voice agent | `PIPECAT_ENABLED=false` default; `/v1/voice/agent` (mic→Whisper→LLM→TTS) built but off | Pipecat pipelines as the voice-agent runtime |
| Pipecat libs inside flute | **Bespoke hand-rolled layer** (`flute_pipecat/`: pipelines, processors, `transports/fastapi_ws.py` FastAPI-WS transport) | The forked transports (websocket, small-webrtc, …) |
| Context hub consumption | Registered as an MCP entry via ACP-registry bridge (#3064, merged) — but no agent node has it installed in an MCP config | Every coding agent gets pipecat docs/API/examples retrieval |
| Fork state | Both forks = plain upstream mirrors, last push 2026-09-09, zero PMOVES overlay commits | PMOVES forks with branded context per doctrine |

## 2. The correspondence map — where pipecat maps back onto PMOVES

| Pipecat capability (the forks) | PMOVES pattern it maps to | Status |
|---|---|---|
| **client-web-transports: 7 transports** (websocket, small-webrtc, daily, livekit, moq, gemini-live, openai-realtime) | Hermes desktop voice playback; a2ui/browser voice UIs; room voice surfaces. The websocket-transport is the direct replacement candidate for `flute_pipecat/transports/fastapi_ws.py` | Unused. We hand-rolled what the fork ships maintained. |
| **small-webrtc-transport** (P2P, "simplest low-latency audio") | Fleet voice between nodes over tailnet — WebRTC data/media channels don't need published ports (hole-punching), the exact problem mesh-bind solves for HTTP | Not considered. |
| **livekit / daily transports** | Multi-party rooms (PMOVES rooms already model participants); SFU offload for >2 party voice | Not considered. |
| **context-hub: local-first retrieval** (Chroma + FTS5 + ONNX MiniLM, `search_docs/search_api/search_examples`, one-shot CLI parity) | The "skills-first" doctrine — pipecat docs retrieval without leaving the node; natural MCP companion to the crush/codex harnesses | MCP entry registered (#3064) but not installed on any seat |
| **context-hub: version-aware indexing** (`refresh --framework-version v0.0.96/head`) | Fleet model-distro doctrine (models must live on HF+Ollama) — same discipline for framework versions: pin what you index | Not applied |
| **context-hub: config layering** (env > cwd .env > config.toml, source-parity enforced by test) | The exact `.env.local`/tier-env trap this session hit (shell > env-file precedence silently overriding env.shared) — their pattern (a parity TEST that fails if a new entry point hand-replicates loading) is the fix for our class of defect | Not applied |

## 3. Patterns that eluded us (in the forks, not in any PMOVES doc)

1. **One-shot CLI parity with MCP tools** — every context-hub MCP tool is also a CLI subcommand (same handlers, enforced by test). Our MCP surfaces can't be smoke-tested without a client; theirs can be curl'd. This kills the "healthy facade" trap family (the nats-event-bus lesson) for MCP servers.
2. **Test-enforced config-source parity** — `tests/unit/test_config.py` fails if any entry point loads env differently. Directly applicable to `COMPOSE_ENV_FILES` chain (the `INCLUDE_ENV_LOCAL_IN_COMPOSE` gate that silently skipped `.env.local`).
3. **Version-pinned re-indexing** — index docs at a framework tag, not head. Applies to our skill/prompt versioning.
4. **Transports as a monorepo of small packages** — each transport independently versioned/released (release-please per package). Applies to flute's voice surfaces if they multiply.

## 4. Hardening the surfaces we already got wrong

| Trap (measured this session) | Pipecat-side reinforcement |
|---|---|
| Flute loopback by default → fleet 10061s | Mesh-bind four-gate checklist (skill `pmoves-mesh-bind-publish`): bind var + env-file inclusion flag + firewall + poison-var unset |
| Shell env > env-file precedence broke NATS_URL on recreate | context-hub's source-parity test pattern; also never carry service URLs in the Hermes profile `.env` |
| Fallback flapping (kokoro 10054 ↔ flute 10061) with no health awareness | `VOICE_HOST_AFFINITY` + fleet-nodes list is the designed answer; make it health-aware (probe before routing) using the tailnet healthz now published |
| Bespoke FastAPI-WS transport drifts alone | Adopt/derive from `@pipecat-ai/websocket-transport`; delete `fastapi_ws.py` when parity reached |

## 5. Recommended next lanes (operator calls)

1. **Fleet-wide flute publish** — repeat elder-melchor's four-gate on z890/5090/b850/spark (each node: `.env.local` + recreate + firewall-on-Linux is ufw/nftables + verify cross-node). Then `VOICE_HOST_AFFINITY=1` + `VOICE_FLEET_NODES` on consumer nodes.
2. **Context-hub MCP install on coding seats** — the #3064 entry made it discoverable; installing it gives agents pipecat retrieval during voice work.
3. **Transport convergence lane** — map `flute_pipecat/transports/fastapi_ws.py` against the fork's websocket-transport; adopt or document why bespoke.
4. **Fork overlay commits** — both forks are bare mirrors; per PMOVES fork doctrine they need at minimum a PMOVES README overlay + CHIT provenance stub.

*Grounded in: live fleet sweep 2026-09-15 (all flutes 10061 from mesh pre-fix), compose reading (`FLUTE_BIND` default, `VOICE_HOST_AFFINITY` :5196, `PIPECAT_ENABLED` :5198), fork clones at `$LOCALAPPDATA/Temp/pipecat-schooling/`, PR #3064 ACP-registry wiring.*
