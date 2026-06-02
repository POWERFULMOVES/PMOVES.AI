# Flute Gateway

**PMOVES Multimodal Voice Communication Layer**

FastAPI service providing Text-to-Speech (TTS) and Speech-to-Text (STT) capabilities across the PMOVES.AI agent hierarchy.

## Overview

Flute Gateway serves as the unified voice interface for PMOVES.AI, aggregating multiple TTS providers and enabling real-time voice agent pipelines via Pipecat integration.

## Features

- **Multi-Provider TTS**: VibeVoice, Ultimate-TTS-Studio, ElevenLabs
- **STT via Whisper**: Integration with ffmpeg-whisper service
- **Prosodic Synthesis**: Natural boundary-aware text chunking (91% faster TTFS)
- **Pipecat Integration**: Real-time voice agent pipelines
- **CHIT Attribution**: Voice geometry attribution support
- **Prometheus Metrics**: Full observability

## Ports

| Port | Protocol | Purpose |
|------|----------|---------|
| 8055 | HTTP | REST API |
| 8056 | WebSocket | Real-time streaming |

## Configuration

### Core Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `NATS_URL` | `nats://${NATS_USER}:${NATS_PASSWORD}@nats:4222` | NATS server URL (preferred explicit DSN) |
| `NATS_USER` | `nats` | NATS username (used when composing URL) |
| `NATS_PASSWORD` | - | NATS password from env or `NATS_PASSWORD_FILE` |
| `SUPABASE_URL` | `http://localhost:3010` | Supabase REST API |
| `SUPABASE_SERVICE_ROLE_KEY` | - | Service role key |
| `DEFAULT_VOICE_PROVIDER` | `vibevoice` | Default TTS provider |
| `FLUTE_API_KEY` | - | Optional API key auth |

### TTS Provider URLs

| Variable | Default | Description |
|----------|---------|-------------|
| `VIBEVOICE_URL` | `http://host.docker.internal:7860` | VibeVoice endpoint (served by TTS Studio) |
| `ULTIMATE_TTS_URL` | `http://ultimate-tts-studio:7860` | Ultimate TTS endpoint (native: 7860) |
| `WHISPER_URL` | `http://ffmpeg-whisper:8078` | Whisper STT endpoint |

### CHIT Integration

| Variable | Default | Description |
|----------|---------|-------------|
| `CHIT_VOICE_ATTRIBUTION` | `false` | Enable voice geometry attribution (master kill-switch — false skips ALL publishes) |
| `CHIT_NAMESPACE` | `pmoves.voice` | CHIT namespace |
| `CHIT_GEOMETRY_SUBJECT` | `tokenism.geometry.event.v1` | Legacy raw-event NATS subject (unchanged) |
| `CHIT_PASSPHRASE` | _(required for sign)_ | HMAC key for CGP signing. Falls back to `CHIT_SIGNING_KEY` first if set. Without either, the bridge emits unsigned packets + warns. |
| `FLUTE_CGP_SUBJECT` | `geometry.cgp.v1` | Canonical CGP v0.2 NATS subject (#1397) — receives signed packets |
| `FLUTE_GEOMETRY_DUAL_PUBLISH` | `true` | Set to `false`/`0`/`no`/`off` to disable canonical publishes (kill-switch) |

#### Geometry-bus dual-publish (#1397)

When `CHIT_VOICE_ATTRIBUTION=true`, every voice synthesis event triggers
**two** NATS publishes:

1. **Legacy** — flat dict on `CHIT_GEOMETRY_SUBJECT` (default `tokenism.geometry.event.v1`):
   ```json
   {"namespace":"pmoves.voice","modality":"voice_synthesis","provider":"vibevoice","text_length":142,"audio_duration_seconds":8.4,"voice":"alloy","ts":"..."}
   ```
2. **Canonical** — HMAC-SHA256 signed CGP v0.2 packet on `FLUTE_CGP_SUBJECT` (default `geometry.cgp.v1`):
   ```json
   {"spec":"chit.cgp.v0.2","summary":"Voice synthesis event from flute-gateway","created_at":"...","super_nodes":[{"id":"voice-synthesis","label":"Flute Voice Synthesis","constellations":[{"id":"voice-events","points":[{"id":"...","modality":"voice_synthesis","ts":"...","char_len":142,"meta":{...}}]}]}],"sig":{"alg":"HMAC-SHA256","kid":"...","hmac":"..."}}
   ```

The canonical packet conforms to `pmoves/contracts/schemas/geometry/cgp.v2.schema.json` and is signed via a vendored copy of `pmoves.tools.chit_security.sign_cgp` (drift-guarded by `tests/test_geometry_bridge.py::test_sign_byte_equivalence_with_canonical`).

**Rollback:** set `FLUTE_GEOMETRY_DUAL_PUBLISH=false` to disable canonical publishes only — legacy publishes continue. To disable both, unset `CHIT_VOICE_ATTRIBUTION` (or set to `false`).

**Observability:** new Prometheus counter `flute_chit_cgp_published_total{subject="<canonical>"}` increments on every successful canonical publish. Existing `flute_chit_events_failed_total{reason}` gains two label values: `legacy_publish_failed`, `cgp_publish_failed`.

### Pipecat

| Variable | Default | Description |
|----------|---------|-------------|
| `PIPECAT_ENABLED` | `false` | Enable Pipecat pipelines |

## API Endpoints

### Health & Metrics

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/healthz` | GET | Health check |
| `/metrics` | GET | Prometheus metrics |

### TTS Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/voice/synthesize` | POST | Standard TTS synthesis |
| `/tts/prosodic/analyze` | POST | Analyze text for prosodic boundaries |
| `/tts/prosodic/synthesize` | POST | Synthesize with prosodic chunking |

### STT Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/voice/recognize` | POST | Transcribe audio file |

## Prosodic Synthesis

Boundary-aware text chunking for natural speech:

```json
POST /tts/prosodic/analyze
{
  "text": "Hello world. How are you today?"
}

Response:
{
  "chunks": [
    {"text": "Hello world.", "boundary": "SENTENCE", "pause_ms": 500},
    {"text": "How are you today?", "boundary": "SENTENCE", "pause_ms": 500}
  ]
}
```

### Boundary Types

| Type | Pause | Example |
|------|-------|---------|
| `SENTENCE` | 500ms | Period, exclamation, question |
| `CLAUSE` | 300ms | Comma, semicolon |
| `PHRASE` | 150ms | Conjunctions |
| `BREATH` | 100ms | Optimal breath points |

## Pipecat Voice Agents

When `PIPECAT_ENABLED=true`, Flute provides voice agent pipeline support:

```python
from pipecat.pipelines import Pipeline
from flute_gateway.pipecat.processors import (
    WhisperSTTProcessor,
    TensorZeroLLMProcessor,
    VibeVoiceTTSProcessor,
)

pipeline = Pipeline([
    transport.input(),
    stt_processor,      # WhisperSTTProcessor
    llm_processor,      # TensorZeroLLMProcessor
    tts_processor,      # VibeVoiceTTSProcessor
    transport.output(),
])
```

## Docker

```yaml
flute-gateway:
  build: ./services/flute-gateway
  ports:
    - "8055:8055"
    - "8056:8056"
  environment:
    - NATS_URL=nats://${NATS_USER}:${NATS_PASSWORD}@nats:4222
    - NATS_USER=${NATS_USER}
    - NATS_PASSWORD=${NATS_PASSWORD}
    - VIBEVOICE_URL=${VIBEVOICE_URL}
    - ULTIMATE_TTS_URL=http://ultimate-tts-studio:7860
    - WHISPER_URL=http://ffmpeg-whisper:8078
    - SUPABASE_URL=${SUPABASE_URL}
    - SUPABASE_SERVICE_ROLE_KEY=${SUPABASE_SERVICE_ROLE_KEY}
    - PIPECAT_ENABLED=${PIPECAT_ENABLED:-false}
  networks:
    - api_tier
    - app_tier
    - bus_tier
  depends_on:
    - nats
```

## Development

```bash
# Install dependencies
pip install -r requirements.txt

# Optional: Pipecat dependencies
pip install -r requirements-pipecat.txt

# Run locally
export VIBEVOICE_URL="http://localhost:3000"
export WHISPER_URL="http://localhost:8078"
python -m uvicorn main:app --host 0.0.0.0 --port 8055
```

## Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `flute_requests_total` | Counter | Total requests by endpoint/status |
| `flute_tts_duration_seconds` | Histogram | TTS synthesis duration |
| `flute_stt_duration_seconds` | Histogram | STT transcription duration |

## Related Services

- **VibeVoice** - Real-time TTS (host-run via Pinokio)
- **Ultimate-TTS-Studio** - Multi-engine TTS (port 7860 native, 7861 Docker)
- **ffmpeg-whisper** - GPU-accelerated Whisper STT
- **TensorZero** - LLM gateway for voice agent responses
- **NATS** - Event bus for CHIT geometry events

## Network Tier

- **API Tier** (172.30.1.0/24) - External voice API
- **App Tier** (172.30.2.0/24) - Internal TTS providers
- **Bus Tier** (172.30.3.0/24) - NATS connectivity

## See Also

- `pmoves/docs/FLUTE_PROSODIC_ARCHITECTURE.md` - Prosodic synthesis details
- `.claude/context/flute-gateway.md` - API reference
- `pmoves/docs/PMOVES.AI-Edition-Hardened-Full.md` - Full deployment guide
