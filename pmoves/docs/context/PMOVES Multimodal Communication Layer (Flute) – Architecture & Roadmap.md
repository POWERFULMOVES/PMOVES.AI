# PMOVES Multimodal Communication Layer ("Flute") – Architecture & Roadmap

**Created**: December 9, 2025
**Status**: Design Phase
**Version**: 1.0

---

## 1. Vision

**Flute** is PMOVES.AI's multimodal communication layer that establishes voice as a first-class citizen across the entire agent hierarchy. Named for its ability to produce harmonious output from multiple inputs, Flute orchestrates Text-to-Speech (TTS), Speech-to-Text (STT), and voice personas across all agent tiers.

### Design Principles

1. **Hierarchy-Aware**: Voice capabilities scale appropriately from CLI agents to full orchestrators
2. **Provider-Agnostic**: Supports multiple TTS/STT providers (VibeVoice, Ultimate TTS, Whisper, ElevenLabs)
3. **Persona-Driven**: Voice characteristics are tied to agent personas, stored in Supabase
4. **Event-Sourced**: All voice events flow through NATS for observability and replay
5. **Streaming-First**: WebSocket-based real-time audio for low-latency interaction

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           PMOVES Agent Hierarchy                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Level 4: Archon (Port 8091)                                               │
│  ├── Full voice persona management UI                                       │
│  ├── Voice cloning workflows                                                │
│  └── Multi-agent voice coordination                                         │
│                                                                             │
│  Level 3: Agent Zero (Port 8080)                                           │
│  ├── Session-level voice mode                                               │
│  ├── Subordinate voice delegation                                           │
│  └── NATS voice event publishing                                            │
│                                                                             │
│  Level 2: BoTZ Gateway (Port 8054)                                         │
│  ├── Voice capability registration                                          │
│  ├── Skill-level voice routing                                              │
│  └── CLI voice command proxy                                                │
│                                                                             │
│  Level 1: CLI Agents (pmoves-crush, claude-code)                           │
│  ├── Text output → TTS synthesis                                            │
│  ├── Audio input → STT transcription                                        │
│  └── Voice persona selection                                                │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Flute Gateway (Ports 8055/8056)                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  HTTP REST API (Port 8055)          WebSocket Streaming (Port 8056)        │
│  ├── /healthz                       ├── /v1/voice/stream/tts               │
│  ├── /v1/voice/synthesize           ├── /v1/voice/stream/stt               │
│  ├── /v1/voice/recognize            └── /v1/voice/stream/duplex            │
│  ├── /v1/voice/personas                                                     │
│  └── /v1/voice/clone                                                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Voice Provider Layer                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│  │   VibeVoice     │  │  Ultimate TTS   │  │    Whisper      │             │
│  │  (GPU Realtime) │  │   (SUP3R Ed.)   │  │   (STT Only)    │             │
│  │   24kHz PCM16   │  │  Multi-voice    │  │  via ffmpeg-    │             │
│  │   Port varies   │  │   Port varies   │  │  whisper:8078   │             │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘             │
│                                                                             │
│  ┌─────────────────┐  ┌─────────────────┐                                  │
│  │   ElevenLabs    │  │  Ollama Voice   │                                  │
│  │   (External)    │  │   (Future)      │                                  │
│  │   API Key Req.  │  │  Local LLM TTS  │                                  │
│  └─────────────────┘  └─────────────────┘                                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Event & Storage Layer                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  NATS JetStream                    Supabase                                 │
│  ├── voice.tts.request.v1          ├── voice_persona (personas)            │
│  ├── voice.tts.chunk.v1            ├── voice_session (sessions)            │
│  ├── voice.stt.completed.v1        └── pmoves_core.agent (link)            │
│  ├── voice.persona.created.v1                                               │
│  └── agent.voice.speaking.v1       MinIO                                    │
│                                    ├── assets/voice-samples/               │
│                                    └── outputs/voice-renders/              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Integration Points

### 3.1 Level 1: CLI Agents (PMOVES-BoTZ)

CLI agents can register voice capabilities via the BoTZ Gateway:

```python
# CLI → BoTZ Gateway → Flute
{
    "botz_id": "pmoves-crush-01",
    "capabilities": {
        "voice_input": true,
        "voice_output": true,
        "preferred_persona": "creative-artist"
    }
}
```

**Voice Output Flow**:
1. CLI generates text response
2. Calls `POST /v1/voice/synthesize` or opens WebSocket
3. Audio streamed back to CLI terminal (via speaker or saved file)

**Voice Input Flow**:
1. CLI captures microphone input
2. Streams to `WS /v1/voice/stream/stt`
3. Receives transcription for processing

### 3.2 Level 2: BoTZ Gateway (Port 8054)

Adds voice routing endpoints:

```
POST /v1/botz/{id}/voice/speak
  - Request body: { "text": "...", "persona": "agent-zero-default" }
  - Response: Audio stream or MinIO URI

POST /v1/botz/{id}/voice/listen
  - Request body: Audio stream (multipart)
  - Response: { "transcription": "...", "confidence": 0.95 }
```

### 3.3 Level 3: Agent Zero (Port 8080)

Session-level voice mode integration:

```
POST /v1/sessions/{id}/voice
  - Enable/disable voice mode for session
  - Set voice persona

POST /v1/sessions/{id}/speak
  - Request: { "message_id": "...", "text": "..." }
  - Response: { "audio_uri": "minio://outputs/voice-renders/..." }
```

**Subordinate Voice Delegation**:
```yaml
# In subordinate config
voice:
  enabled: true
  persona: pmoves-log-analyzer
  auto_speak: false  # Only speak when explicitly requested
```

### 3.4 Level 4: Archon (Port 8091)

Full voice persona management via UI (Port 3737):

- Create/edit voice personas
- Upload voice samples for cloning
- Preview voice before saving
- Associate personas with agents
- Manage voice sample storage in MinIO

---

## 4. Data Model

### 4.1 Voice Persona

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
```

### 4.2 Voice Session

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

### 4.3 Voice Config (JSONB)

```json
{
    "vibevoice": {
        "cfg": 1.5,
        "steps": 8,
        "voice_preset": "default"
    },
    "ultimate_tts": {
        "speaker_id": 0,
        "emotion": "neutral",
        "speed": 1.0
    },
    "elevenlabs": {
        "voice_id": "...",
        "stability": 0.5,
        "similarity_boost": 0.75
    }
}
```

---

## 5. API Specification

### 5.1 REST Endpoints (Port 8055)

#### Health Check
```
GET /healthz
Response: { "status": "healthy", "providers": ["vibevoice", "whisper"] }
```

#### Discover Voices
```
GET /v1/voice/config
Response: {
    "providers": ["vibevoice", "ultimate_tts", "whisper", "elevenlabs"],
    "default_provider": "vibevoice",
    "sample_rate": 24000,
    "format": "pcm16"
}
```

#### Synthesize Speech (Batch)
```
POST /v1/voice/synthesize
Request: {
    "text": "Hello from PMOVES!",
    "persona_id": "uuid-or-slug",
    "provider": "vibevoice",  // optional
    "output_format": "wav"    // wav, mp3, pcm
}
Response: {
    "audio_uri": "minio://outputs/voice-renders/...",
    "duration_seconds": 1.5,
    "sample_rate": 24000
}
```

#### Recognize Speech (Batch)
```
POST /v1/voice/recognize
Request: multipart/form-data with audio file
Response: {
    "transcription": "Hello from PMOVES!",
    "confidence": 0.95,
    "language": "en"
}
```

#### Manage Personas
```
GET    /v1/voice/personas           - List all personas
POST   /v1/voice/personas           - Create persona
GET    /v1/voice/personas/{id}      - Get persona
PATCH  /v1/voice/personas/{id}      - Update persona
DELETE /v1/voice/personas/{id}      - Delete persona
POST   /v1/voice/personas/{id}/preview - Preview voice sample
```

#### Clone Voice
```
POST /v1/voice/clone
Request: multipart/form-data with voice sample + metadata
Response: {
    "persona_id": "new-cloned-persona-id",
    "quality_score": 0.85,
    "estimated_similarity": 0.90
}
```

### 5.2 WebSocket Endpoints (Port 8056)

#### Real-time TTS Streaming
```
WS /v1/voice/stream/tts?persona={slug}&format=pcm16
← { "type": "text", "content": "Hello!" }
→ Binary audio chunks (PCM16, 24kHz)
→ { "type": "done", "duration": 1.5 }
```

#### Real-time STT Streaming
```
WS /v1/voice/stream/stt?language=en
← Binary audio chunks (PCM16, 16kHz)
→ { "type": "partial", "text": "Hel" }
→ { "type": "partial", "text": "Hello" }
→ { "type": "final", "text": "Hello!", "confidence": 0.95 }
```

#### Duplex Voice Conversation
```
WS /v1/voice/stream/duplex?persona={slug}&session={id}
← Binary audio (user speaking)
→ { "type": "user_text", "text": "What's the weather?" }
→ { "type": "agent_text", "text": "Checking weather..." }
→ Binary audio (agent speaking)
```

---

## 6. NATS Subjects

### 6.1 TTS Events

```
voice.tts.request.v1
  - Payload: { session_id, persona_id, text, priority }

voice.tts.started.v1
  - Payload: { request_id, provider, estimated_duration }

voice.tts.chunk.v1
  - Payload: { request_id, chunk_index, audio_b64, is_last }

voice.tts.completed.v1
  - Payload: { request_id, audio_uri, duration_seconds, tokens_used }

voice.tts.failed.v1
  - Payload: { request_id, error_code, error_message }
```

### 6.2 STT Events

```
voice.stt.request.v1
  - Payload: { session_id, audio_uri, language }

voice.stt.partial.v1
  - Payload: { request_id, partial_text, confidence }

voice.stt.completed.v1
  - Payload: { request_id, final_text, confidence, language }
```

### 6.3 Persona Events

```
voice.persona.created.v1
  - Payload: { persona_id, slug, name, provider }

voice.persona.updated.v1
  - Payload: { persona_id, changes }

voice.persona.cloned.v1
  - Payload: { source_sample_uri, new_persona_id, quality_score }
```

### 6.4 Agent Voice Events

```
agent.voice.speaking.v1
  - Payload: { agent_id, session_id, text, persona_id }

agent.voice.listening.v1
  - Payload: { agent_id, session_id, duration_limit }

agent.voice.mode_changed.v1
  - Payload: { session_id, voice_enabled, persona_id }
```

---

## 7. Voice Provider Integrations

### 7.1 VibeVoice Realtime (Primary TTS)

**Source**: Microsoft VibeVoice (Pinokio launcher in ARTSTUFF)

**Specifications**:
- Model: `microsoft/VibeVoice-Realtime-0.5B`
- Sample Rate: 24 kHz
- Format: PCM16 (Int16)
- Latency: ~100ms first chunk

**WebSocket API**:
```
WS /stream?text={text}&cfg=1.5&steps=8&voice={preset}
← Binary audio chunks
```

**Integration**:
```python
# flute-gateway/providers/vibevoice.py
class VibeVoiceProvider:
    def __init__(self, base_url: str):
        self.ws_url = f"ws://{base_url}/stream"

    async def synthesize_stream(self, text: str, voice: str = "default"):
        async with websockets.connect(
            f"{self.ws_url}?text={text}&voice={voice}"
        ) as ws:
            async for chunk in ws:
                if isinstance(chunk, bytes):
                    yield chunk
```

### 7.2 Ultimate TTS Studio (Alternate TTS)

**Source**: SUP3R Edition (Pinokio launcher in ARTSTUFF)

**Specifications**:
- Multi-voice synthesis
- RVC voice conversion support
- Multiple output formats

### 7.3 Whisper (Primary STT)

**Source**: Existing `ffmpeg-whisper` service (Port 8078)

**Specifications**:
- Model: small (faster-whisper)
- Sample Rate: 16 kHz input
- Languages: Auto-detect or specified

**Integration**:
```python
# flute-gateway/providers/whisper.py
class WhisperProvider:
    def __init__(self, base_url: str = "http://ffmpeg-whisper:8078"):
        self.base_url = base_url

    async def recognize(self, audio_file: str) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/transcribe",
                files={"audio": open(audio_file, "rb")}
            )
            return resp.json()
```

### 7.4 ElevenLabs (External TTS)

**Specifications**:
- Requires API key (`ELEVENLABS_API_KEY`)
- High-quality voices
- Voice cloning available

---

## 8. Roadmap

### Phase 12a: Foundation (Week 1)
- [ ] Create Flute architecture document (this file)
- [ ] Create database migrations for `voice_persona`, `voice_session`
- [ ] Implement `flute-gateway` service skeleton
- [ ] Add VibeVoice provider integration
- [ ] Add Whisper provider integration
- [ ] Basic health check and config endpoints

### Phase 12b: Agent Integration (Week 2)
- [ ] Add voice endpoints to BoTZ Gateway
- [ ] Add session voice mode to Agent Zero
- [ ] Create 3 default voice personas
- [ ] Implement NATS voice events
- [ ] End-to-end CLI → TTS test

### Phase 12c: WebSocket Streaming (Week 3)
- [ ] Implement `/v1/voice/stream/tts`
- [ ] Implement `/v1/voice/stream/stt`
- [ ] Implement `/v1/voice/stream/duplex`
- [ ] Add streaming to Archon UI

### Phase 12d: Voice Cloning & Advanced (Week 4)
- [ ] Implement voice cloning endpoint
- [ ] Add ElevenLabs provider
- [ ] Add Ultimate TTS provider
- [ ] Voice persona management UI in Archon
- [ ] ComfyUI node integration

---

## 9. Security Considerations

### 9.1 Voice Sample Storage
- Voice samples stored in MinIO bucket `assets/voice-samples/`
- Access controlled via presigned URLs (expires: 1 hour)
- No public access to raw voice samples

### 9.2 API Authentication
- REST API: Bearer token (Supabase JWT or service key)
- WebSocket: Initial handshake requires token
- NATS: Internal service mesh only

### 9.3 Rate Limiting
- TTS: 100 requests/minute per client
- STT: 50 requests/minute per client
- WebSocket: 10 concurrent connections per client

### 9.4 Voice Data Privacy
- Transcriptions logged to `voice_session` (can be disabled)
- Audio not stored unless explicitly requested
- Cloned voices require user consent confirmation

---

## 10. Dependencies

### Required Services
- **NATS** (Port 4222) - Event bus
- **Supabase** (Port 3010) - Persona storage
- **MinIO** (Port 9000) - Audio file storage
- **ffmpeg-whisper** (Port 8078) - STT backend

### Optional Services
- **VibeVoice Realtime** - Primary TTS (Pinokio)
- **Ultimate TTS Studio** - Alternate TTS (Pinokio)
- **ElevenLabs API** - External TTS

### Environment Variables
```bash
# Required
NATS_URL=nats://nats:4222
SUPABASE_URL=http://supabase:3010
SUPABASE_SERVICE_ROLE_KEY=...
MINIO_ENDPOINT=minio:9000

# Voice Providers
# If Flute is running in Docker, do NOT use localhost (it points at the container).
# Use host-gateway for a Pinokio/host-run VibeVoice, or set it to the docker service URL when applicable.
VIBEVOICE_URL=http://host.docker.internal:3000  # Pinokio/host-run VibeVoice (from Docker)
WHISPER_URL=http://ffmpeg-whisper:8078
ELEVENLABS_API_KEY=...  # Optional

# Flute Gateway
FLUTE_HTTP_PORT=8055
FLUTE_WS_PORT=8056
```

---

## 11. Related Documentation

- `pmoves/docs/ARTSTUFF/VibeVoice-RealtimeREADME.md` - VibeVoice Pinokio launcher
- `pmoves/docs/ARTSTUFF/Ultimate-TTS-Studio-SUP3R-EditionREADME.md` - Ultimate TTS launcher
- `.claude/context/services-catalog.md` - Service port reference
- `.claude/context/nats-subjects.md` - NATS subject catalog
- `pmoves/services/ffmpeg-whisper/` - Existing STT service

---

## 12. Changelog

| Date | Version | Changes |
|------|---------|---------|
| 2025-12-09 | 1.0 | Initial architecture document |
