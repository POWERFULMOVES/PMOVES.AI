# Pipecat Fleet Review — voice MCP + realtime agents under hardware constraint

**Status:** REVIEW (2026-09-05) — flute + Pipecat fork family for the constrained-mesh scenario

## The scenario (operator directive)
Elder-Melchor (GTX 1650 4GB) is the hardware floor. The mesh solves GPU: **Jetsons over
Tailscale for the combiner**, E2B danger rooms for elastic sandboxing, cloud LLMs for the
heavy lifting. Voice/realtime must run LOCAL-first on the floor node — that's Pipecat's job.

## Flute (:8055) — the voice gateway (verified from compose + skill)
- 8 providers behind VoiceProvider ABC (synthesize/synthesize_stream/recognize)
- **PIPECAT_ENABLED=false by default** — the realtime duplex agent
  (mic→Whisper→LLM→VibeVoice) is OFF; enabling is the integration point
- Engine topology is Pinokio-native: UTS :7860, OmniVoice :8002, VibeVoice :7860
  via host.docker.internal — engines live on the HOST (Pinokio), flute is the docker shell
- CHIT voice-attribution events to tokenism.geometry.event.v1 built in
- **MCP**: the voice-fabric plan Layer 1 = flute `/mcp` mount (FastMCP) exposing
  voice_synthesize/stream/recognize/personas/engines_list/capabilities → NOT yet verified
  live (flute container stuck Created under docker contention this session)

## The Pipecat fork family — what each is FOR
| Fork | Role in the scenario | State |
|---|---|---|
| `PMOVES-Pipecat` (submodule, pinned a12efa4, NOT inited) | The framework: realtime voice agents (the mic→Whisper→LLM→voice loop flute toggles) | needs shallow init |
| `Pmoves-pipecat-mcp-server` | **Voice/screen MCP server** — exposes voice + screen-capture TOOLS to MCP clients; audio I/O itself rides a transport (Daily WebRTC etc). `agent.py`/`agent_ipc.py`/`bot.py` = an agent harness that can run headless on a Jetson/KVM and be DRIVEN remotely | pushed 2026-02 — needs upstream drift check |
| `Pmoves-pipecat-context-hub` | **Local-first docs/examples/API index** (ChromaDB + SQLite FTS5) as MCP — the exact pattern for "A0 and Archon ingest indexed knowledge": give every agent a citable corpus | pushed TODAY — active |
| `Pmoves-pipecat-client-web-transports` | Browser-side transports: daily, livekit, moq, small-webrtc, websocket, openai-realtime, gemini-live — the **web agent surf** layer (rooms in browser over mesh) | pushed 9/4 — active |

## How the pieces satisfy the scenario
1. **"web agents surf"** → client-web-transports (websocket/small-webrtc from any browser,
   livekit/daily rooms for multi-party) + pipecat-mcp-server agents behind them
2. **"A0 and Archon ingest indexed knowledge"** → context-hub pattern generalized: the hub
   indexes Pipecat docs; PMOVES.YT / Open Notebook / repo corpora get the same
   ChromaDB+FTS5+citations treatment per domain, exposed as MCP for A0/Archon/Hermes
3. **"enough E2B danger rooms for everyone"** → pipecat agents' arbitrary code steps run in
   E2B sandboxes, not on the floor node
4. **"Jetsons over Tailscale for combiner, GPU not a prob"** → pipecat-mcp-server bot.py
   runs headless on a Jetson; MCP client (Hermes/Crush/A0) drives it from anywhere on the
   tailnet; STT/TTS heavy models stay on GPU nodes
5. **"keep the mesh neat / mini lady p"** → context-hub is also the prism: one citable
   knowledge index per domain, fleet-shared via MCP, instead of every agent re-scraping

## Gaps found
- **flute /mcp mount unverified** — Layer 1 of the voice plan; needs live check once flute runs
- **mcp_inventory has ZERO pipecat entries** — context-hub and mcp-server should register
  (stdio local for hermes/crush/a0 clients) once verified
- **PMOVES-Pipecat submodule not initialized** on this node (correct for capacity IF the
  voice agents run on Jetsons instead — decide by where the realtime loop lives)
- mcp-server fork 7 months stale vs upstream pipecat-ai/pipecat-mcp-server — drift check needed
- No engine manifests exist yet for DramaBox/Qwen3 (Gradio TTS on this node's Pinokio)

## Recommended wiring order
1. flute up → verify `/v1/voice/config` + `/mcp` → register flute-voice MCP in inventory
2. context-hub: `uv tool install` → index → register in inventory (hermes + a0 + crush clients)
3. mcp-server: drift-check vs upstream → deploy bot.py to a Jetson/KVM as the headless voice agent
4. PMOVES.YT/Open-Notebook corpora → context-hub-pattern indexes (per-domain MCP)
5. PIPECAT_ENABLED=true on flute once VibeVoice runs (needs pipecat-ai installed)
