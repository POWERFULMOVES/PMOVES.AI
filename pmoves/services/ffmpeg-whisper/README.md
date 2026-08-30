# ffmpeg-whisper — Audio Transcription Service

GPU-accelerated audio-to-text transcription using OpenAI Whisper, wrapped with FFmpeg preprocessing for arbitrary input formats. Consumes from the YouTube ingestion pipeline and other media sources.

## Quick reference

- **Port**: `:8078` (HTTP) — internal Docker Compose network only
- **Health**: `GET /healthz` → `{"status": "ok"}`
- **Profile**: `gpu` (CUDA, ROCm pending Wave-Phase-C)
- **Team**: `media` per `pmoves/configs/agent-teams.yaml`

## Architecture

```
  Audio source (file / URL / NATS payload)
              │
              ▼
       FFmpeg decode (any → 16kHz mono WAV)
              │
              ▼
       Whisper transcribe (large-v3 by default)
              │
              ▼
       NATS publish: `media.transcript.ready.v1` (planned)
              │                + JSON response over HTTP
              ▼
       PMOVES.YT, Hi-RAG, downstream consumers
```

## API

### `POST /transcribe`

Request:
```json
{
  "source_uri": "s3://bucket/audio.opus",
  "language": "en",         // optional; auto-detect if omitted
  "model_size": "large-v3"  // optional; defaults from env
}
```

Response:
```json
{
  "text": "Transcribed text...",
  "segments": [{"start": 0.0, "end": 4.2, "text": "..."}],
  "language": "en",
  "duration_seconds": 142.3
}
```

## Environment

- `WHISPER_MODEL` — model size (`base`, `small`, `medium`, `large-v3`); default `large-v3`.
- `WHISPER_DEVICE` — `cuda` (default), `rocm` (pending), `cpu` (fallback, slow).
- `NATS_URL` — `nats://nats:pmoves@nats:4222`.
- `MINIO_*` — for fetching/storing audio assets through `presign` service.

## Bringup

Use the canonical Known Road:

```bash
make -C pmoves up-ffmpeg-whisper   # narrower than up-yt
```

`docker compose up ffmpeg-whisper` is blocked by the Wave-0 `known-roads-enforcer.py` hook (when wired). See `.claude/PATTERNS.md` § Known Roads.

## Cross-references

- `pmoves/services/pmoves-yt/` — YouTube ingestion upstream consumer.
- `pmoves/services/voice-relay/` — NATS bridge for the mic chain (use `make -C pmoves up-voice-relay`).
- `pmoves/services/flute-gateway/` — pairing for round-trip voice agents.
- `.claude/CATALOG.md` § Audio / Transcription Services.
