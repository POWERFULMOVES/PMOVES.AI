# Voice Chain — End-to-End Architecture

**Status:** Authoritative — Session 12 reference for the full voice pipeline
**Last updated:** 2026-04-14
**Scope:** Producer surfaces → bus → consumer surfaces, including the
explicit decision that PMOVES.YT is intentionally **not** in the voice chain.

This document is the single picture of the voice pipeline. It cross-links to:
- `pmoves/docs/architecture/voice-agent-response-relay.md` (voice-relay deep dive)
- `pmoves/docs/TAC/TAC_VOICE_PRODUCTION.md` (production readiness review, Phase 7)
- `pmoves/services/flute-gateway/providers/` (provider implementations)
- `pmoves/configs/skill-pairings.yaml:158-205` (voice-synthesis pairing)

---

## TL;DR

```
PRODUCER LAYER                   BUS LAYER                       CONSUMER LAYER
──────────────                   ─────────                       ──────────────

Flute-Gateway :8055              tokenism.geometry.event.v1  →   tokenism simulator
  ├─ UltimateTTSProvider                                         hi-rag indexer
  ├─ VibeVoiceProvider           agentzero.task.result.v1    →   voice-relay :8121
  ├─ VoiceboxProvider (NEW)               │
  ├─ WhisperProvider                      ▼ filter+transform
  ├─ CloningProvider             voice.agent.response.v1     →   voice_follow_agent (host TTS)
  └─ Pipecat processors                                           voice_follow_cast_agent (Google Cast)
     (flute-gateway/pipecat/)

                                 voice.training.request.v1   →   training worker (planned)
```

**The voice chain bypasses media-ingestion services by design.** PMOVES.YT,
PMOVES.YT-Sync, FFmpeg-Whisper, and similar ingestion services publish to
`ingest.*` subjects but do not consume from `voice.*`. Voice is a producer-side
concern (text → audio) handled at the agent layer, not a media-pipeline
concern.

---

## Producer Layer

### Flute-Gateway (`:8055`)

The voice production gateway. Aggregates multiple TTS/STT providers behind a
unified HTTP API. Source: `pmoves/services/flute-gateway/`.

| Provider | Class | Source | Upstream | Notes |
|----------|-------|--------|----------|-------|
| Ultimate-TTS-Studio | `UltimateTTSProvider` | `providers/ultimate_tts.py` | Gradio 4.x SSE polling | 14 engines: KittenTTS, Kokoro, F5-TTS, IndexTTS, IndexTTS2, Fish S1/S2, ChatterboxTTS variants, VoxCPM, Higgs, Qwen, VibeVoice, Chatterbox MTL |
| VibeVoice Realtime | `VibeVoiceProvider` | `providers/vibevoice.py` | WebSocket (`/stream`) | 24kHz PCM16, custom busy/no-audio errors, retry logic |
| **Voicebox** | **`VoiceboxProvider`** | **`providers/voicebox.py`** | **HTTP (`/generate/stream`)** | **NEW Session 12 Lane 1 — Pinokio-managed at host :17493, profile-based, blocked on first-run profile creation** |
| Whisper STT | `WhisperProvider` | `providers/whisper.py` | HTTP multipart | Wraps ffmpeg-whisper service |
| Voice cloning | `VoiceCloningProvider`, `CloningSynthesisProvider` | `providers/cloning.py` | HTTP | RVC scaffold |

### Pipecat Processors

Higher-level pipeline composition layer. Source: `pmoves/services/flute-gateway/pipecat/`.

| Component | File | Purpose |
|-----------|------|---------|
| `VibeVoiceTTSProcessor` | `pipecat/processors/vibevoice.py` | Wraps the WebSocket VibeVoice provider as a Pipecat `TextFrame → TTSAudioRawFrame` processor |
| `TensorZeroLLMProcessor` | `pipecat/processors/tensorzero.py` | LLM inference processor routing through TensorZero gateway |
| `WhisperProcessor` | `pipecat/processors/whisper.py` | STT processor |
| `FluteFastAPIWebsocketTransport` | `pipecat/transports/fastapi_ws.py` | WebSocket transport binding |
| `build_voice_agent_pipeline` | `pipecat/pipelines/voice_agent.py` | End-to-end voice agent pipeline builder |

The Pipecat processors are **not** exposed as a separate MCP server. The
`.claude/commands/pipecat/connect.md` and `.claude/commands/pipecat/status.md`
slash commands wrap the Flute-Gateway HTTP API directly. Building a Pipecat
MCP server was considered in Session 12 and explicitly deferred — the slash
commands already cover the intended surface, and an MCP wrapper would
duplicate the HTTP API without adding value.

---

## Bus Layer (NATS)

| Subject | Producer | Consumer | Schema | Notes |
|---------|----------|----------|--------|-------|
| `tokenism.geometry.event.v1` | flute-gateway (CHIT attribution) | tokenism simulator, hi-rag indexer | `{namespace, modality, provider, text_length, audio_duration_seconds, voice, ts}` | Best-effort publish; failures tracked via `flute_chit_events_failed_total` Prometheus counter |
| `agentzero.task.result.v1` | agent-zero | voice-relay | Agent Zero task completion envelope | Configurable via `VOICE_RELAY_INPUT_SUBJECT` |
| `voice.agent.response.v1` | voice-relay | voice_follow_agent, voice_follow_cast_agent | See `pmoves/contracts/schemas/voice/agent.response.v1.schema.json` | Configurable via `VOICE_RELAY_OUTPUT_SUBJECT` |
| `voice.training.request.v1` | flute-gateway (cloning) | training worker (planned) | Voice cloning training trigger | Listed in cgp_sub_probe.py for forward compatibility |
| `geometry.cgp.v1`, `geometry.>`, `tokenism.>` | various CHIT-aware services | CGP consumers | CGP packet format | Wildcard subjects covered by `cgp_sub_probe.py` |

NATS authentication: `nats://nats:pmoves@nats:4222` (always use the
authenticated form per CLAUDE.md convention).

### voice-relay Service

See `pmoves/docs/architecture/voice-agent-response-relay.md` for the deep
dive. In one sentence: **voice-relay subscribes to
`agentzero.task.result.v1`, filters for `meta.voice_mode == true`,
transforms the payload to the `voice.agent.response.v1` schema, and
republishes.** Source at `pmoves/services/voice-relay/main.py`, port 8121.

---

## Consumer Layer

| Consumer | Listens on | Output | Source |
|----------|------------|--------|--------|
| `voice_follow_agent` | `voice.agent.response.v1` | Host TTS speaker (via `voice-speaker` daemon on `:8120`) | host-side daemon, started by `make -C pmoves voice-follow-start` |
| `voice_follow_cast_agent` | `voice.agent.response.v1` | Google Cast device | host-side daemon |
| `publisher-discord` | `ingest.file.added.v1`, `ingest.transcript.ready.v1`, `ingest.summary.ready.v1`, `ingest.chapters.ready.v1`, `content.published.v1`, `tokenism.*` | Discord webhook notifications (file delivery via `POST /publish` API) | `pmoves/services/publisher-discord/` |
| `voice-speaker` | HTTP `:8120` | Local audio playback | host-side daemon, started by `make -C pmoves voice-speaker-start` |

The consumer set is intentionally **host-side and Discord-side**. There is no
container-side consumer for `voice.agent.response.v1` because the audio needs
to reach a real speaker or chat channel — both are at the edge of the
deployment, not in the middle of it.

---

## The PMOVES.YT Decision

**PMOVES.YT is intentionally NOT in the voice chain.**

### Investigation (Session 12)

The Session 12 exploration confirmed:

- PMOVES.YT publishes `ingest.file.added.v1` and `ingest.transcript.ready.v1` only
- PMOVES.YT does **not** consume any NATS subjects (no `nats.subscribe`,
  `js.subscribe`, `JetStream.consume`, or similar patterns found anywhere in
  the submodule)
- PMOVES.YT has no voice-related branches, stashes, worktrees, or uncommitted work
- The voice chain (voice-relay → consumers) targets host-side TTS playback
  and Discord — neither is something PMOVES.YT can deliver

### Why not wire it?

A naive "complete the picture" instinct would add a NATS consumer to PMOVES.YT
that subscribes to `voice.agent.response.v1` and attaches generated audio to
YouTube content. This is a **bad idea** for three reasons:

1. **Direction mismatch.** PMOVES.YT is an *ingestion* service — it pulls
   YouTube content INTO PMOVES, transcribes it, and publishes events. Voice
   synthesis is *outbound* — it sends audio to humans. Mixing these into one
   service breaks the producer/consumer separation that lets each scale and
   fail independently.

2. **No clear audience.** The voice pipeline produces TTS audio for a human
   listener (host speaker, Cast device, Discord channel). YouTube uploads are
   a different medium with different requirements (titles, descriptions,
   thumbnails, monetization). Audio attached to a YouTube video is part of the
   video itself, not a separate notification — so it'd need to flow into the
   video composition pipeline, not directly into YT publishing.

3. **No audience asking for it.** No production agent currently requests
   "synthesize voice for a YouTube video." Building infrastructure for a
   missing requirement is speculative work.

### If PMOVES.YT *does* need voice in the future

If a future requirement emerges (e.g., "auto-generate audio descriptions for
PMOVES-uploaded YouTube videos"), the right shape is **not** to bolt a voice
consumer onto PMOVES.YT. It is to:

1. **Define the requirement first.** What's the audience? What does "audio"
   mean here — a soundtrack? a voiceover? captions? an audio description for
   accessibility?

2. **Pick the contract.** What NATS subject does PMOVES.YT consume? Probably
   something new like `media.audio.attach.v1`, not `voice.agent.response.v1`
   (which is for human-listener TTS, not video-bound audio).

3. **Identify the producer.** What service generates the video-bound audio?
   It's almost certainly **not** voice-relay. More likely: a new media
   composition service that takes a video reference and produces a synced
   audio track via Voicebox or similar.

4. **Coordinate with `pmoves_announcer/`.** This is the closest existing
   consumer-shaped module in PMOVES.YT — any new NATS consumer should follow
   its patterns or be co-located.

This is **a future Session 13 design question**, not a Session 12 implementation
gap. The plan that produced this document explicitly defers this work.

---

## End-to-End Test

Session 12 Lane 3 ships the following verification tools:

1. **`pmoves/tools/voice_to_discord_test.py`** — end-to-end test for the
   voice→Discord delivery path. Supports `--synthetic` (bus-only, no
   synthesis) and `--live` (full chain through Flute-Gateway).

2. **`pmoves/tools/cgp_sub_probe.py`** — subscribes to CGP/geometry NATS
   subjects and reports attribution events arriving on the bus.

3. **`pmoves/services/flute-gateway/tests/test_gateway.py`** — hermetic unit
   tests for the Flute-Gateway, including VibeVoice provider initialization,
   synthesis calls, health checks, and persona management.

4. **`pmoves/tools/voice_chain_e2e_test.py`** (planned) — will publish a
   synthetic `agentzero.task.result.v1` and wait for the relay to republish on
   `voice.agent.response.v1`, validating payload transformation and
   publish-to-republish latency. Not yet implemented.

5. **`pmoves/services/flute-gateway/tests/test_vibevoice_realtime.py`**
   (planned) — functional WebSocket harness against a live VibeVoice realtime
   server. Not yet implemented.

Run the full producer→bus→consumer chain manually:

```bash
# 1. Bring up the bus + relay + flute
make -C pmoves up-flute-gateway
make -C pmoves up-vibevoice
# voice-relay should be up via its profile (`make -C pmoves up-voice-relay` if available)

# 2. Verify the bus chain (planned — voice_chain_e2e_test.py not yet implemented)
# python pmoves/tools/voice_chain_e2e_test.py

# 3. Verify a producer end-to-end through Discord
python pmoves/tools/voice_to_discord_test.py --synthetic   # bus + Discord, no synthesis
python pmoves/tools/voice_to_discord_test.py --live        # full chain through Flute

# 4. Verify CGP attribution events arrive on the bus
python pmoves/tools/cgp_sub_probe.py
```

---

## Cross-references

- `pmoves/docs/architecture/voice-agent-response-relay.md` — voice-relay deep dive (schema, metrics, resilience)
- `pmoves/docs/TAC/TAC_VOICE_PRODUCTION.md` — production readiness review (engine status, Pinokio app inventory, Phase 6 checklist)
- `pmoves/docs/issues/higgs-upstream-embedding-bug.md` — known Higgs bug (Session 12 Lane 2 stub)
- `pmoves/configs/skill-pairings.yaml:158-205` — `voice-synthesis` skill pairing chain
- `pmoves/services/flute-gateway/providers/` — provider implementations (base, ultimate_tts, vibevoice, voicebox, whisper, cloning)
- `pmoves/services/flute-gateway/pipecat/` — Pipecat processors and pipelines
- `pmoves/services/voice-relay/main.py` — voice-relay implementation
- `pmoves/contracts/schemas/voice/agent.response.v1.schema.json` — voice.agent.response.v1 schema
