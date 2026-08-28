# Voice Persona System

**Last Updated:** March 2026
**Service:** Flute-Gateway + Ultimate-TTS-Studio (14 engines)
**Capability Registry:** `pmoves/configs/tts-engine-capabilities.yaml`

---

## Overview

Voice personas define how agents sound when speaking. Each persona combines:
- TTS engine and voice model selection
- Speaking rate and pitch modifications
- Personality traits for prosodic emphasis
- Language and locale preferences

---

## Database Schema

### `voice_persona` Table

```sql
CREATE TABLE public.voice_persona (
    id                       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    slug                     text NOT NULL UNIQUE,
    name                     text NOT NULL,
    agent_id                 uuid REFERENCES pmoves_core.agent(id),
    avatar_id                bigint REFERENCES public.persona_avatar(id),

    -- Provider configuration
    voice_provider           text NOT NULL DEFAULT 'vibevoice',
    voice_model              text,
    voice_sample_uri         text,  -- MinIO: assets/voice-samples/{slug}.wav
    voice_config             jsonb NOT NULL DEFAULT '{}'::jsonb,

    -- Personality
    personality_traits       text[] DEFAULT '{}',
    language                 text NOT NULL DEFAULT 'en',
    speaking_rate            float DEFAULT 1.0,
    pitch_shift              float DEFAULT 0.0,

    -- Status
    is_active                boolean NOT NULL DEFAULT true,
    created_at               timestamptz NOT NULL DEFAULT now(),
    updated_at               timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_voice_persona_agent ON public.voice_persona(agent_id);
CREATE INDEX idx_voice_persona_provider ON public.voice_persona(voice_provider);
```

### `voice_session` Table

```sql
CREATE TABLE public.voice_session (
    id                       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id                 uuid REFERENCES pmoves_core.agent(id),
    session_id               uuid,  -- Links to claude_sessions
    voice_persona_id         uuid REFERENCES public.voice_persona(id),

    -- State machine
    state                    text CHECK (state IN (
        'idle', 'listening', 'processing', 'speaking'
    )),

    -- Metrics
    total_tts_requests       int DEFAULT 0,
    total_stt_requests       int DEFAULT 0,
    total_audio_seconds      float DEFAULT 0,

    started_at               timestamptz NOT NULL DEFAULT now(),
    ended_at                 timestamptz
);
```

---

## Voice Configuration JSONB

Provider-specific settings stored in `voice_config`:

### VibeVoice

```json
{
    "vibevoice": {
        "cfg": 1.5,
        "steps": 8,
        "voice_preset": "default"
    }
}
```

### Ultimate-TTS-Studio (14 Engines)

All engines run natively via Pinokio at `http://127.0.0.1:7860` (CUDA, conda tts_env).
See `pmoves/configs/tts-engine-capabilities.yaml` for machine-readable expressive dimensions.

| engine_id | Engine Name | Category | Strengths | Best For |
|-----------|-------------|----------|-----------|----------|
| `kitten_tts` | KittenTTS | preset-voices | Ultra-fast, 8 pre-trained voices | Low-latency synthesis, real-time |
| `kokoro` | Kokoro TTS | preset-voices | Multilingual ONNX, CPU-friendly | Warm narration, host voice |
| `higgs` | Higgs Audio | preset-voices | Pre-cached model, streaming-capable | Streaming synthesis |
| `f5_tts` | F5-TTS | voice-cloning | High-quality voice cloning, natural prosody | GRAMS narration, beat-sync |
| `fish` | Fish Speech | voice-cloning | Zero-shot voice cloning | Quick cloning demos |
| `fish_s2` | Fish Speech S2 Pro | voice-cloning | Zero-shot clone, 13 languages | Agent card voice profiles |
| `voxcpm` | VoxCPM | voice-cloning | Voice cloning + transcription (dual-purpose) | Clone + verify |
| `indextts` | IndexTTS | voice-cloning | Fast indexing-based synthesis | Batch synthesis |
| `indextts2` | IndexTTS2 | emotion-control | 8-dim emotion vectors (happy/angry/sad/calm/...) | ClawZ reveals, emotion-driven |
| `chatterbox` | ChatterboxTTS | multilingual | Exaggeration/temperature control | Expressive narration |
| `chatterbox_turbo` | Chatterbox Turbo | multilingual | Fast exaggeration control | Fast expressive synthesis |
| `chatterbox_multilingual` | Chatterbox Multilingual | multilingual | 17 languages + exaggeration control | Multi-language synthesis |
| `qwen` | Qwen3 TTS | multilingual | Voice design + clone modes, Base/Small variants | Chinese + multilingual |
| `vibevoice` | VibeVoice | podcast | Multi-speaker podcast generation | Podcast-style content |

```json
{
    "ultimate_tts": {
        "engine": "kokoro",
        "speaker_id": 0,
        "emotion": "neutral",
        "speed": 1.0,
        "pitch": 0,
        "energy": 1.0
    }
}
```

Engine-specific voice_config examples:

```json
// KittenTTS — uses voice preset
{"ultimate_tts": {"engine": "kitten_tts", "voice": "expr-voice-2-f"}}

// IndexTTS2 — emotion vector
{"ultimate_tts": {"engine": "indextts2", "emotion": "happy", "temperature": 0.8}}

// Chatterbox Turbo — exaggeration control
{"ultimate_tts": {"engine": "chatterbox_turbo", "exaggeration": 0.5, "temperature": 0.8}}

// Fish Speech S2 Pro — zero-shot clone
{"ultimate_tts": {"engine": "fish_s2"}}

// Higgs Audio — voice preset + streaming
{"ultimate_tts": {"engine": "higgs", "voice_preset": "EMPTY", "temperature": 1.0}}
```

---

## Persona Creation Workflow

### 1. Create Base Persona

```bash
curl -X POST http://localhost:8055/v1/voice/personas \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $FLUTE_API_KEY" \
  -d '{
    "slug": "agent-zero-default",
    "name": "Agent Zero",
    "voice_provider": "ultimate_tts",
    "voice_model": "kokoro-en-v1",
    "language": "en",
    "speaking_rate": 1.0,
    "personality_traits": ["professional", "calm", "helpful"],
    "voice_config": {
        "ultimate_tts": {
            "engine": "kokoro",
            "emotion": "neutral"
        }
    }
}'
```

### 2. Upload Voice Sample (for cloning)

```bash
curl -X POST http://localhost:8055/v1/voice/personas/agent-zero-default/sample \
  -H "Authorization: Bearer $FLUTE_API_KEY" \
  -F "audio=@voice_sample.wav" \
  -F "description=Agent Zero reference voice"
```

### 3. Preview Voice

```bash
curl -X POST http://localhost:8055/v1/voice/personas/agent-zero-default/preview \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello, I am Agent Zero."}'
```

### 4. Associate with Agent

```bash
curl -X PATCH http://localhost:8055/v1/voice/personas/agent-zero-default \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "uuid-of-agent-zero"}'
```

---

## Voice Parameter Mapping

| Parameter | Range | Default | Effect |
|-----------|-------|---------|--------|
| `speaking_rate` | 0.5-2.0 | 1.0 | Speech speed multiplier |
| `pitch_shift` | -12 to +12 | 0.0 | Semitone adjustment |
| `cfg` (VibeVoice) | 1.0-3.0 | 1.5 | Classifier-free guidance |
| `stability` (ElevenLabs) | 0.0-1.0 | 0.5 | Voice consistency |
| `energy` (Ultimate-TTS) | 0.5-1.5 | 1.0 | Expression intensity |

---

## Personality Traits

Personality traits influence prosodic behavior:

| Trait | Prosodic Effect |
|-------|-----------------|
| `calm` | Longer pauses, lower energy |
| `energetic` | Shorter pauses, higher pitch variance |
| `professional` | Measured pace, clear enunciation |
| `friendly` | Warmer tone, more breath sounds |
| `authoritative` | Slower pace, stronger emphasis |
| `playful` | Higher pitch variance, shorter sentences |

---

## Default Personas

Pre-configured personas available out-of-box (see `pmoves/configs/tts-engine-capabilities.yaml` for full dimension map):

| Slug | Name | Provider | Engine | Expressive Dimensions Used | Use Case |
|------|------|----------|--------|---------------------------|----------|
| `agent-zero-default` | Agent Zero | Ultimate-TTS | kokoro | speed + punctuation engineering | Main orchestrator |
| `archon-narrator` | Archon Narrator | Ultimate-TTS | f5_tts | speed + voice cloning + cross_fade | Knowledge delivery |
| `clawz-reveal` | ClawZ Reveal | Ultimate-TTS | indextts2 | 8-dim emotion vectors + emo_alpha | Agent identity reveals |
| `pmoves-crush` | PMOVES Crush | Ultimate-TTS | kitten_tts | voice preset (ultra-fast) | CLI agent |
| `grams-narrator` | GRAMS Narrator | Ultimate-TTS | f5_tts | speed + voice cloning + cross_fade | Story narration, beat-sync |
| `agent-card-voice` | Agent Card Voice | Ultimate-TTS | fish_s2 | temperature + top_p + cloning | Zero-shot persona profiles |
| `multilingual-agent` | Multilingual Agent | Ultimate-TTS | chatterbox_turbo | exaggeration + temperature + cfg | Fast expressive synthesis |
| `streaming-agent` | Streaming Agent | Ultimate-TTS | higgs | voice_preset + temperature + top_p | Real-time streaming TTS |
| `expressive-narrator` | Expressive Narrator | Ultimate-TTS | chatterbox | exaggeration + temperature + cfg | Theatrical narration |
| `polyglot-agent` | Polyglot Agent | Ultimate-TTS | chatterbox_multilingual | language + exaggeration + temp | 17-language synthesis |
| `voice-designer` | Voice Designer | Ultimate-TTS | qwen | mode + speaker + language | Voice design/cloning |
| `quick-clone` | Quick Clone | Ultimate-TTS | fish | temperature + top_p + cloning | Fast cloning demos |
| `batch-synth` | Batch Synth | Ultimate-TTS | indextts | temperature (lightweight) | Bulk synthesis |
| `clone-verify` | Clone Verify | Ultimate-TTS | voxcpm | cfg_value + timesteps + denoise | Clone + transcription |
| `podcast-host` | Podcast Host | Ultimate-TTS | vibevoice | multi-speaker (separate endpoint) | Podcast generation |
| `announcer-broadcast` | Broadcast Announcer | Ultimate-TTS | kokoro | speed 0.9 + am_adam voice | System announcements, PR events, Cast speakers |

### Service Runner Personas

These personas are mapped to always-on or on-demand TTS service runners (see `pmoves/configs/tts-engine-capabilities.yaml` → `service_runners`):

| Role | Persona | Engine | Latency | Use Case |
|------|---------|--------|---------|----------|
| `cli-voice` | pmoves-crush | KittenTTS | <100ms | CLI notifications, terminal gateway |
| `announcer` | announcer-broadcast | Kokoro | <500ms | System events, Cast speakers, deploy alerts |
| `narrator` | grams-narrator | F5-TTS | ~1-3s | Story narration, documentation read-aloud |
| `streaming` | streaming-agent | Higgs | <500ms | Real-time WebSocket streaming |
| `podcast` | podcast-host | VibeVoice | ~3-5s | Multi-speaker podcast (separate endpoint) |
| `expressive` | clawz-reveal | IndexTTS2 | ~1-3s | Emotion-driven reveals, dramatic narration |

---

## NATS Events

### Persona Events

```
voice.persona.created.v1
  Payload: { persona_id, slug, name, provider }

voice.persona.updated.v1
  Payload: { persona_id, changes }

voice.persona.cloned.v1
  Payload: { source_sample_uri, new_persona_id, quality_score }
```

### Session Events

```
agent.voice.speaking.v1
  Payload: { agent_id, session_id, text, persona_id }

agent.voice.listening.v1
  Payload: { agent_id, session_id, duration_limit }

agent.voice.mode_changed.v1
  Payload: { session_id, voice_enabled, persona_id }
```

---

## API Endpoints

### List Personas

```
GET /v1/voice/personas
Response: {
    "personas": [
        {
            "id": "uuid",
            "slug": "agent-zero-default",
            "name": "Agent Zero",
            "voice_provider": "ultimate_tts",
            "is_active": true
        }
    ]
}
```

### Get Persona

```
GET /v1/voice/personas/{id_or_slug}
Response: {
    "id": "uuid",
    "slug": "agent-zero-default",
    "name": "Agent Zero",
    "voice_provider": "ultimate_tts",
    "voice_model": "kokoro-en-v1",
    "voice_config": {...},
    "personality_traits": ["professional", "calm"],
    "language": "en",
    "speaking_rate": 1.0,
    "pitch_shift": 0.0
}
```

### Create Persona

```
POST /v1/voice/personas
Request: { slug, name, voice_provider, ... }
Response: { id, slug, name, ... }
```

### Update Persona

```
PATCH /v1/voice/personas/{id}
Request: { name?, speaking_rate?, ... }
Response: { id, slug, name, ... }
```

### Delete Persona

```
DELETE /v1/voice/personas/{id}
Response: { success: true }
```

---

## Storage

### Voice Samples

Voice samples stored in MinIO:
- Bucket: `assets`
- Path: `voice-samples/{persona_slug}/{filename}.wav`
- Access: Via presigned URLs (1 hour expiry)

### Synthesized Audio

Generated audio stored temporarily:
- Bucket: `outputs`
- Path: `voice-renders/{session_id}/{timestamp}.wav`
- Retention: 24 hours

---

## Integration with CHIT Attribution

Voice personas integrate with CHIT for attribution tracking:

```
Persona Synthesis
       ↓
   CGP Packet
       ↓
geometry.packet.encoded.v1
       ↓
   Hi-RAG v2
       ↓
Shape Store (Supabase + Qdrant)
```

Each synthesis can be attributed:
- **Who spoke**: `voice_persona_id`
- **What was said**: `text_content`
- **Geometric signature**: `cgp_packet_id`
- **Attribution weights**: Dirichlet distribution across contributors

---

## Related Documentation

- **Engine Capability Registry:** `pmoves/configs/tts-engine-capabilities.yaml` — Machine-readable per-engine expressive dimensions
- **Per-Engine Test:** `/tts:test-engine <id> --metrics` — Test single engine with GPU VRAM tracking
- **Hardware Templates:** `pmoves/docs/AGENTS/HARDWARE_TTS_REQUIREMENTS.md` — All 14 engine prosodic templates
- `pmoves/docs/FLUTE_PROSODIC_ARCHITECTURE.md` - Prosodic sidecar details
- `.claude/context/flute-gateway.md` - Flute API reference
- `pmoves/docs/PERSONAS.md` - Full persona framework (325+ personas)
- `.claude/context/nats-subjects.md` - Voice NATS subjects
