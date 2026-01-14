# Ultimate-TTS-Studio - PMOVES.AI Hardened Build

Multi-engine TTS service with all 7 engines pre-installed, following PMOVES.AI security standards.

## Quick Start

```bash
# Build the image
docker compose build ultimate-tts-studio

# Start the service
docker compose up -d ultimate-tts-studio

# Verify health
curl http://localhost:7861/gradio_api/info
```

## Engines Included

| Engine | Description | Use Case |
|--------|-------------|----------|
| KittenTTS | Fast neural TTS | Quick synthesis |
| Kokoro | High-quality Japanese/English | Anime-style voices |
| F5-TTS | Facebook's speech synthesis | Natural prosody |
| VoxCPM | Voice cloning | Custom voice matching |
| Whisper | Speech-to-text | Transcription input |
| espeak-ng | Phoneme generation | Pronunciation control |
| pynini | G2P and phonetic rules | Text normalization |

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Ultimate-TTS-Studio (Port 7861)                        │
│  ┌─────────────────┐ ┌─────────────────┐               │
│  │  Gradio UI      │ │  FastAPI Backend │              │
│  └────────┬────────┘ └────────┬────────┘               │
│           │                   │                         │
│  ┌────────▼───────────────────▼────────┐               │
│  │           TTS Engine Router          │              │
│  │  ┌─────┐┌─────┐┌─────┐┌─────┐┌─────┐│              │
│  │  │Kit  ││Kokor││F5   ││VoxCP││Whisp││              │
│  │  │ten  ││o    ││TTS  ││M    ││er   ││              │
│  │  └─────┘└─────┘└─────┘└─────┘└─────┘│              │
│  └─────────────────────────────────────┘               │
└─────────────────────────────────────────────────────────┘
```

## Security Features

- **Non-root user**: Runs as `pmoves` (UID 65532)
- **Multi-stage build**: Minimal runtime image
- **Health checks**: Gradio API monitoring
- **GPU isolation**: Optional resource reservations

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GRADIO_SERVER_NAME` | `0.0.0.0` | Listen address |
| `GRADIO_SERVER_PORT` | `7861` | HTTP port |

## GPU Configuration

The service automatically uses GPU when available. Configure resource limits in docker-compose.yml:

```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: 1
          capabilities: [gpu]
    limits:
      memory: 8G
```

## Integration with Flute-Gateway

Ultimate-TTS-Studio can serve as a backend for flute-gateway's prosodic TTS:

```python
# In flute-gateway, configure Ultimate-TTS endpoint
ULTIMATE_TTS_URL = "http://ultimate-tts-studio:7861"
```

## Volumes

| Path | Purpose |
|------|---------|
| `/app/checkpoints` | Engine model weights |
| `/app/outputs` | Generated audio files |
| `/app/models` | Voice models |

## Health Check

```bash
# Check service health
curl -f http://localhost:7861/gradio_api/info

# Expected response: {"version": "...", "mode": "..."}
```

## Troubleshooting

### GPU not detected
```bash
# Verify NVIDIA runtime
docker run --rm --gpus all nvidia/cuda:12.4.1-base nvidia-smi
```

### Out of memory
Reduce batch size in TTS settings or limit concurrent requests.

### Slow first request
Model loading occurs on first request. Pre-warm by sending a test synthesis.

## Source Repository

Based on: https://github.com/SUP3RMASS1VE/Ultimate-TTS-Studio-SUP3R-Edition

---
*PMOVES.AI Hardened Build - December 2025*
