# TAC Tree: Voice Production Readiness Review

**Status:** Active review (Session 11)
**Owner:** 5090-claude / voice lane
**Last updated:** 2026-04-13
**Scope:** End-to-end voice pipeline: TTS engines → Flute-Gateway → creator services

GRAPHITI_MARK: `VOICE-PROD-REVIEW-2026-04-13`

## Context

Session 11 validated 12/14 TTS engines and 4 cloning engines via Flute-Gateway production HTTP. Voice pipeline has CHIT CGP events publishing to `tokenism.geometry.event.v1`. This document consolidates what's verified, what's stub, what's gap, and what can be delegated to existing Pinokio apps rather than reinvented.

## Phase 1: Engine Validation Status

| Engine | Load | Synth | Cloning | Sample Rate | Synth Time | Notes |
|--------|------|-------|---------|-------------|-----------|-------|
| Kokoro | ✅ | ✅ | — | 24kHz | 2.6s | Fast baseline |
| KittenTTS | ✅ | ✅ | — | 24kHz | 1.7s | Ultra-fast |
| IndexTTS | ✅ | ✅ | — | 24kHz | 3.4s | Reliable |
| IndexTTS2 | ✅ | ✅ | ✅ ref_audio | 22kHz | 266.7s | Slow but emotion vectors work |
| F5-TTS | ✅ | ✅ | ✅ ref_audio | 24kHz | 3.3s (clone) | 8.5x real-time, best cloning |
| VoxCPM | ✅ | ✅ | ✅ ref_audio | 44.1kHz | 22.9s (clone) | Highest fidelity |
| ChatterboxTTS | ✅ | ✅ | — | 24kHz | 4.2s | Expressive |
| Chatterbox Turbo | ✅ | ✅ | — | 24kHz | 2.1s | Fast multilingual |
| Chatterbox MTL | ✅ | ✅ | — | 24kHz | 5.2s | 17 languages |
| Fish Speech S1 | ✅ | ✅ | ✅ | 44.1kHz | 9.5s | Zero-shot |
| Fish Speech S2 Pro | ✅ | ✅ | ✅ | 44.1kHz | 17.7s | 13-language, user-verified UI |
| Qwen Voice Clone | ✅ | ✅ | ✅ ref_audio | 24kHz | 17.5s | VoiceDesign model base |
| VibeVoice | ✅ | ⚠️ | — | — | — | Loads but uses separate endpoint (not unified) |
| **Higgs Audio** | ❌ | ❌ | — | — | — | **Upstream bug** (see Phase 4) |

## Phase 2: Pinokio App Inventory & Consolidation Strategy

PMOVES had been treating Ultimate-TTS-Studio as the only TTS backend. Recon found **5 voice apps** in the local Pinokio installation:

| App | State | Engines | Voice Cloning | API | PMOVES Integration |
|-----|-------|---------|---------------|-----|-------------------|
| **Voicebox** | 🟢 Running :17493 | 5 (Qwen3-TTS, LuxTTS, Chatterbox, Chatterbox Turbo, HumeAI) | ✅ 2-10s samples | **FastAPI + OpenAPI** | **Not integrated** |
| **Ultimate-TTS-Studio SUP3R** | 🟡 On-demand | 14 consolidated | ✅ F5, Fish S2, VoxCPM, Qwen | Gradio | Currently primary (Flute `UltimateTTSProvider`) |
| **VoxForge Pro** | 🔴 Never launched | 2 (Kokoro, Chatterbox) | ✅ | Gradio | — |
| **Qwen3-TTS** | 🔴 Offline | 1 (Qwen3-TTS standalone) | ✅ | Gradio | Duplicate of Voicebox backend |
| **VibeVoice Realtime** | 🔴 Never launched | 1 (VibeVoice 0.5B streaming) | — | **WebSocket** | — |

### Consolidation Plan

**DO NOT reinvent.** Strategy:
1. **Voicebox as primary production backend** — Add `VoiceboxProvider` to Flute-Gateway (parallel to `UltimateTTSProvider`). 22 voice endpoints, OpenAPI spec, proper profile/history/effects architecture. Targets `/generate` with `profile_id` + `text`.
2. **Ultimate-TTS-Studio as experimental backend** — Keep for the 14-engine menagerie and emotion-vector/BPM experimentation.
3. **VibeVoice Realtime for streaming** — When real-time WebSocket TTS is needed (Pipecat voice pipeline).
4. **VoxForge Pro** — Ignore unless user explicitly wants the 47 premium voices.

## Phase 3: Creator Pipeline Integration Map

```
Flute-Gateway (synthesize)
    ├─→ tokenism.geometry.event.v1 (CHIT attribution) ✅ NEW
    └─→ REST/WebSocket clients

Agent Zero Task (meta.voice_mode=true)
    └─→ agentzero.task.result.v1
        └─→ voice-relay (:8121) [filter & transform]
            └─→ voice.agent.response.v1 (schema-validated NATS)
                ├─→ voice_follow_agent (host TTS player) ✅
                ├─→ voice_follow_cast_agent (Google Cast) ✅
                └─→ publisher-discord (NATS subscriber) ✅
                    └─→ Discord webhook (.wav attachment, 8MB limit)
```

**Status by edge:**
- Flute → CHIT: ✅ Live (Session 11 fix — `_publish_chit_voice_event` wired into prosodic)
- Agent Zero → voice-relay: ✅ Shipped
- voice-relay → voice.agent.response.v1: ✅ Shipped
- Publisher-Discord audio attachment: ✅ Wired (base64 → .wav attachment)
- **Voice → PMOVES.YT**: ❌ NOT WIRED — no voice consumer in YT publisher
- **Skill pairings**: ❌ No voice-synthesis pairing in `skill-pairings.yaml`

## Phase 4: Known Bugs

### Higgs Audio: `Padding_idx must be within num_embeddings`

**Error:**
```
❌ Failed to initialize Higgs Audio engine: Padding_idx must be within num_embeddings
🔄 Attempting CPU fallback...
❌ CPU fallback also failed: Padding_idx must be within num_embeddings
```

**Root cause:** Vocab/embedding mismatch in the Higgs integration inside Ultimate-TTS-Studio-SUP3R-Edition. The model checkpoint's embedding matrix was saved with a smaller vocab size than what the tokenizer currently exposes, OR a special token (like `<pad>`) was added without calling `model.resize_token_embeddings()`.

**Fix location:** Ultimate-TTS-Studio-SUP3R-Edition upstream repo (NOT PMOVES). Likely in `app/handlers/higgs_handler.py` or similar.

**Workaround:** Skip Higgs. VoxCPM, F5-TTS, and Fish S2 cover its use cases.

**Upstream action:** File issue at `SUP3RMASS1VE/Ultimate-TTS-Studio-SUP3R-Edition` with the reproduction steps.

### VibeVoice: Separate endpoint (not unified)

VibeVoice uses `/handle_vibevoice_generation`, not `/generate_unified_tts`. Current test script skips it (`synth_kwargs: None`). Requires dedicated test harness.

## Phase 5: Skill Gap — pterm / gepeto / pinokio

PMOVES has ZERO formal skills for pterm, gepeto, or pinokio management despite heavy use of `D:/pinokio/bin/npm/pterm.cmd`. Recommended additions:

| Skill | Priority | Purpose |
|-------|----------|---------|
| `/pinokio:app-search` | **High** | `pterm search` with JSON parsing, ready-state filter |
| `/pinokio:app-start` | **High** | `pterm start` with retry + health poll |
| `/pinokio:app-stop` | **High** | `pterm stop` with clean shutdown verification |
| `/pterm:script-runner` | Medium | Execute arbitrary pterm with Windows UTF-8 encoding |
| `/pinokio:monitor` | Medium | Watch running Pinokio processes, emit NATS events |
| `/gepeto:scaffold` | Medium | Generate 1-click launcher from GitHub URL |
| `/gepeto:validate` | Low | Lint Pinokio launcher scripts |

**Guide exists** at `D:\pinokio\api\hermes-agent.pinokio.git\temp_pmoves\pmoves\docs\AGENTS\gepeto-SKILL.md` (480 lines) — content for skill creation is already written.

## Phase 6: Execution Checklist

- [x] Full 14-engine sweep (12/14 operational)
- [x] Voice cloning 4/4 engines (F5, VoxCPM, IndexTTS2, Qwen)
- [x] Expressive intents sweep 4/4 (narrate, dramatic, multilingual, agent)
- [x] Prosodic synthesis with CHIT CGP events
- [x] Voicebox API surface mapped (22 TTS endpoints)
- [ ] **VibeVoice separate endpoint test** (`/handle_vibevoice_generation`)
- [ ] **Voicebox provider integration** into Flute-Gateway (`VoiceboxProvider` class)
- [ ] **Creator pipeline test**: synthesize → Discord webhook with .wav attachment
- [ ] **Pterm/pinokio skill stubs** in `.claude/commands/pinokio/`
- [ ] **Voice-synthesis skill pairing** in `pmoves/configs/skill-pairings.yaml`
- [ ] **PMOVES.YT voice integration** (stretch goal — new consumer)
- [ ] **Higgs upstream issue filed** (housekeeping)

## Phase 7: NATS Subjects Catalog (Voice Lane)

| Subject | Publisher | Consumer | Schema |
|---------|-----------|----------|--------|
| `tokenism.geometry.event.v1` | flute-gateway | tokenism simulator, hi-rag indexer | `{namespace, modality, provider, text_length, audio_duration_seconds, voice, ts}` |
| `agentzero.task.result.v1` | agent-zero | voice-relay | Agent Zero task completion |
| `voice.agent.response.v1` | voice-relay | voice_follow_agent, voice_follow_cast_agent, publisher-discord | `{text, audio_uri?, voice_mode, meta}` |
| `voice.training.request.v1` | flute-gateway (cloning) | training worker (planned) | Voice cloning training trigger |

## Critical Files

| File | Purpose |
|------|---------|
| `pmoves/services/flute-gateway/main.py` | Flute-Gateway FastAPI app + `_publish_chit_voice_event` |
| `pmoves/services/flute-gateway/providers/ultimate_tts.py` | UltimateTTSProvider (Gradio client) |
| `pmoves/services/flute-gateway/providers/cloning.py` | Voice cloning provider (RVC scaffold) |
| `pmoves/services/flute-gateway/prosodic/bpm_encoder.py` | BPM → CGP encoding |
| `pmoves/services/publisher-discord/main.py` | Discord publisher + audio attachment handler |
| `pmoves/services/voice-relay/main.py` | Agent Zero → voice.agent.response.v1 transformer |
| `pmoves/services/cast-tts-gateway/` | Google Cast TTS gateway (consumes Flute) |
| `pmoves/configs/tts-engine-expressions.yaml` | 9 expressive intents |
| `pmoves/configs/tts-engine-capabilities.yaml` | Engine specs, VRAM, latency |
| `pmoves/tools/test_all_tts_engines.py` | Production engine sweep harness |
| `pmoves/tools/voicebox_probe.py` | Voicebox OpenAPI spec probe |
| `pmoves/tools/cgp_sub_probe.py` | NATS CGP subscriber (verification) |

## Verification Commands

```bash
# Engine sweep
python -X utf8 pmoves/tools/test_all_tts_engines.py --engine <id>

# Production path via Flute-Gateway
curl -X POST http://localhost:8055/v1/voice/synthesize \
  -d '{"text":"...","provider":"ultimate_tts","intent":"narrate"}'

# Prosodic + CHIT CGP verification
curl -X POST http://localhost:8055/v1/voice/synthesize/prosodic \
  -d '{"text":"...","engine":"kokoro","provider":"ultimate_tts"}'
MSYS_NO_PATHCONV=1 docker exec pmoves-flute-gateway-1 python /tmp/cgp_sub_probe.py

# Voicebox API surface
python pmoves/tools/voicebox_probe.py voicebox_openapi_spec.json

# Pinokio app discovery
D:/pinokio/bin/npm/pterm.cmd search "voice"
```

## Handoff Fields

- graphiti_mark: `VOICE-PROD-REVIEW-2026-04-13`
- branch: main
- pr_numbers: [session-11-voice]
- scope: voice production readiness, Pinokio consolidation, skill gap documentation
- risks: Higgs upstream bug (non-blocking), Voicebox integration is new work
- next_actions: integrate VoiceboxProvider, create pinokio skill stubs, test creator pipeline end-to-end
- agent_signature: `ACK::CLAUDE-OPUS::VOICE-PROD-REVIEW-2026-04-13`
