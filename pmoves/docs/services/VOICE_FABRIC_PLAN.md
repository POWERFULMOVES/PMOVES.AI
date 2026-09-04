# Voice Fabric Integration Plan — flute-gateway, MCP, cipher dsh agents, harness extensions

**Status:** PROPOSAL (2026-09-03) — operator asked for: voice update path, engine wiring via
flute + MCP, optimal cipher dsh-agent context per engine, extension-plugin design that stays
harness-portable (Hermes desktop + others).

## Current inventory (measured live 2026-09-03)

### flute-gateway provider registry (services/flute-gateway/providers/)
Abstract base (`base.py`: synthesize / synthesize_stream / recognize ABC) with 8 implementations:
vibevoice, voicebox, omnivoice (current default), whisper (STT), ultimate_tts, kokoro,
cloning (VoiceCloningProvider + CloningSynthesisProvider). REST surface: /v1/voice/{config,
synthesize,synthesize/audio,recognize,personas}. CHIT voice-attribution events built in.

### Fleet voice services (pmoves/services/)
flute-gateway (8055), cast-tts-gateway, kokoro-tts, vibevoice-realtime, voice-relay,
voice-sampler, audio-reprocess, media-audio, ffmpeg-whisper. Pinokio fork carries
pmoves-services + Ultimate TTS Studio (PMOVES-Ultimate-TTS-Studio + Pinokio variant).

### Gap
- Providers are python-class-registered (static imports in providers/__init__.py) — adding an
  engine = code change, not config.
- No MCP surface for voice (nothing in mcp_inventory.json matches voice/tts/flute).
- No cipher dsh-agent context encoding per-engine knowledge.

## Design (three layers, door open for other harnesses)

### Layer 1 — flute-gateway as THE voice MCP server (registry entry, fail-open to clients)
```
key: pmoves-flute-voice
transport: http, endpoint: local, url: http://localhost:8055/mcp
clients: ["hermes"]   # + claude/crush later; fail-closed until live-verified
tools exposed: voice_synthesize, voice_stream, voice_recognize, voice_personas,
               voice_engines_list, voice_engine_capabilities
```
Implementation: FastMCP mount on the existing FastAPI app (`/mcp` path) reusing the provider
registry — no new service, one new file + inventory entry. The MCP tool schema doubles as the
harness-portable contract (any MCP client gets voice without PMOVES-specific code).

### Layer 2 — engine capability manifests (per-engine dsh-agent context)
`pmoves/config/voice/engines/*.yaml` — one manifest per engine: endpoints, auth env names,
voice presets, sample rates, latency class (realtime/batch), strengths (e.g. kokoro=fast-local,
ultimate=quality/cloning, vibevoice=realtime-streaming, whisper=STT), cost class, fallback
chain position. These manifests ARE the cipher dsh-agent context: a voice-router dsh agent
reads the manifests to route synth requests by latency/cost/voice-match — optimal context
lives in DATA, not baked into agent prompts (fresh per decision, compact, citable).

### Layer 3 — dsh voice agents + harness-portable extension
- `voice-router` dsh agent (Archon workflow, a2a-exposed): input text + constraints → engine
  choice + flute call + CHIT-signed attribution event. `inputs:`/`returns:` signature becomes
  the a2a tool schema (same pattern as the fix-github-issue wrap).
- Hermes-extension plugin: thin client over the SAME MCP tools (no private API) — desktop
  pane/commands for speak/listen. Portability rule: **the MCP contract is the only public
  surface**; every harness (Hermes desktop, Pinokio launcher, A0 skill) builds UI on MCP, so
  any MCP-capable harness gets voice for free. No PMOVES-only protocol.

## Sequencing
1. flute `/mcp` mount + `voice_engines_list`/`capabilities` tools + inventory entry (PR — small)
2. engines/*.yaml manifests for the 8 providers (PR — data)
3. voice-router dsh agent wrap (post Archon PR #27 merge)
4. Hermes desktop plugin on MCP tools (hermes-desktop-plugins skill pattern)

## Reconciliation hooks
- README already fixed for omnivoice default (#2907); this plan supersedes nothing —
  provider layering unchanged, only exposed via MCP.
- Pinokio8: pmoves-services launcher already fronts compose stacks; Ultimate TTS Studio
  stays a Pinokio-side engine feeding flute via ULTIMATE_TTS_URL.
