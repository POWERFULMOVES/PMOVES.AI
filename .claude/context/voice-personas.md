# Voice Persona System

**Last Updated:** December 2025
**Service:** Flute-Gateway

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

### Ultimate-TTS-Studio

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

### ElevenLabs

```json
{
    "elevenlabs": {
        "voice_id": "EXAVITQu4vr4xnSDxMaL",
        "stability": 0.5,
        "similarity_boost": 0.75,
        "style": 0.0,
        "use_speaker_boost": true
    }
}
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

Pre-configured personas available out-of-box:

| Slug | Name | Provider | Use Case |
|------|------|----------|----------|
| `agent-zero-default` | Agent Zero | Ultimate-TTS | Main orchestrator |
| `archon-narrator` | Archon Narrator | VibeVoice | Knowledge delivery |
| `assistant-friendly` | Friendly Assistant | ElevenLabs | Customer-facing |
| `pmoves-crush` | PMOVES Crush | Ultimate-TTS | CLI agent |

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

- `pmoves/docs/FLUTE_PROSODIC_ARCHITECTURE.md` - Prosodic sidecar details
- `.claude/context/flute-gateway.md` - Flute API reference
- `pmoves/docs/PERSONAS.md` - Full persona framework (325+ personas)
- `.claude/context/nats-subjects.md` - Voice NATS subjects
