# Flute-Gateway: Voice Communication Layer

**Reference documentation for the flute-gateway multimodal voice service.**

Based on PR #332 (Pipecat integration) - December 2025.

---

## Overview

Flute-Gateway provides a unified voice communication layer with:
- **Prosodic TTS** - Natural speech synthesis with intelligent pausing
- **Real-time streaming** - WebSocket-based audio I/O
- **Multiple backends** - VibeVoice, Ultimate-TTS-Studio, Whisper
- **Pipecat integration** - Pipeline-based audio processing

---

## Service Endpoints

| Port | Protocol | Purpose |
|------|----------|---------|
| 8055 | HTTP | REST API endpoints |
| 8056 | WebSocket | Real-time audio streaming |

---

## API Reference

### Health Check
```bash
curl http://localhost:8055/healthz
```

**Response:**
```json
{
  "status": "healthy",
  "providers": {
    "vibevoice": true,
    "whisper": true,
    "ultimate_tts": true
  },
  "nats": "connected",
  "supabase": "connected"
}
```

### Prosodic Text Analysis
```bash
curl -X POST http://localhost:8055/v1/voice/analyze/prosodic \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello, this is a test."}'
```

**Response:**
```json
{
  "chunks": [
    {
      "text": "Hello, this",
      "boundary_after": "NONE",
      "pause_ms": 0,
      "is_first": true,
      "is_final": false,
      "estimated_syllables": 3
    },
    {
      "text": "is a test.",
      "boundary_after": "SENTENCE",
      "pause_ms": 350,
      "is_first": false,
      "is_final": true,
      "estimated_syllables": 3
    }
  ],
  "total_chunks": 2,
  "estimated_ttfs_benefit": "~80% faster TTFS"
}
```

### Prosodic TTS Synthesis
```bash
curl -X POST http://localhost:8055/v1/voice/synthesize/prosodic \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $FLUTE_API_KEY" \
  -d '{
    "text": "Hello, this is a test.",
    "voice": "default",
    "format": "wav"
  }'
```

### Create Voice Session (WebSocket)
```bash
curl -X POST http://localhost:8055/v1/sessions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $FLUTE_API_KEY" \
  -d '{
    "mode": "duplex",
    "tts_engine": "ultimate-tts",
    "stt_engine": "whisper"
  }'
```

**Response:**
```json
{
  "session_id": "sess_abc123",
  "websocket_url": "ws://localhost:8056/sessions/sess_abc123",
  "expires_at": "2025-12-19T23:00:00Z"
}
```

---

## Prosodic Synthesis

Prosodic synthesis improves time-to-first-speech (TTFS) by:
1. Analyzing text for natural break points
2. Chunking at breath boundaries and sentence ends
3. Streaming audio as each chunk completes

**Boundary Types:**
| Type | Pause (ms) | Description |
|------|------------|-------------|
| `NONE` | 0 | No pause, continue speaking |
| `BREATH` | 100-150 | Natural breath pause |
| `CLAUSE` | 200-250 | Comma or clause boundary |
| `SENTENCE` | 300-400 | Period, question, exclamation |

---

## WebSocket Protocol

### Connection
```javascript
const ws = new WebSocket('ws://localhost:8056/sessions/sess_abc123');

ws.onopen = () => console.log('Connected');
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  // Handle audio data or transcription
};
```

### Message Types

**Audio Input (STT):**
```json
{
  "type": "audio",
  "data": "<base64-encoded-audio>",
  "format": "pcm16",
  "sample_rate": 16000
}
```

**Text Input (TTS):**
```json
{
  "type": "text",
  "text": "Hello, world!",
  "voice": "default"
}
```

**Audio Output:**
```json
{
  "type": "audio_chunk",
  "data": "<base64-encoded-audio>",
  "chunk_index": 0,
  "is_final": false
}
```

**Transcription Output:**
```json
{
  "type": "transcription",
  "text": "Hello, world!",
  "is_final": true,
  "confidence": 0.95
}
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `FLUTE_API_KEY` | (none) | API authentication key |
| `FLUTE_HTTP_PORT` | 8055 | HTTP API port |
| `FLUTE_WS_PORT` | 8056 | WebSocket port |
| `ULTIMATE_TTS_URL` | `http://host.docker.internal:7861` | TTS backend |
| `VIBEVOICE_URL` | `http://host.docker.internal:3000` | Alternative TTS |
| `WHISPER_URL` | `http://ffmpeg-whisper:8078` | STT backend |
| `DEFAULT_VOICE_PROVIDER` | `vibevoice` | Default TTS provider |

---

## Integration with Ultimate-TTS-Studio

Flute-Gateway connects to Ultimate-TTS-Studio for high-quality synthesis:

```
┌─────────────────┐     HTTP      ┌──────────────────────┐
│  Flute-Gateway  │──────────────▶│  Ultimate-TTS-Studio │
│   (Port 8055)   │               │     (Port 7861)      │
└─────────────────┘               └──────────────────────┘
        │
        │ WebSocket (8056)
        │
        ▼
   Client Audio I/O
```

---

## Slash Commands

| Command | Description |
|---------|-------------|
| `/tts:synthesize` | Generate TTS audio |
| `/tts:status` | Check TTS service health |
| `/tts:voices` | List available voices |
| `/pipecat:status` | Check Pipecat layer health |
| `/pipecat:connect` | Create voice session |

---

## Troubleshooting

### Service Not Responding
```bash
# Check container status
docker ps --filter "name=flute"

# View logs
docker logs pmoves-flute-gateway-1 --tail 50
```

### WebSocket Connection Failed
- Verify port 8056 is exposed
- Check CORS settings if connecting from browser
- Ensure session exists before connecting

### TTS Quality Issues
- Try different TTS engine (ultimate-tts vs vibevoice)
- Adjust voice parameters
- Check GPU availability for Ultimate-TTS

---

*Last Updated: December 2025*
*PR Reference: #332 (Pipecat Integration)*
