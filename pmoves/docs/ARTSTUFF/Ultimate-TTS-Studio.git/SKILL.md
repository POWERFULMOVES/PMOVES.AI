---
name: Ultimate TTS Studio
description: Multi-engine text-to-speech synthesis with 10 engines including Kokoro, F5-TTS, KittenTTS, VoxCPM
keywords: tts, speech, voice, synthesis, kokoro, f5, kitten, voxcpm, voice-cloning, prosodic
version: 1.0.0
category: Voice/Synthesis
---

# Ultimate TTS Studio

**Category**: Voice/Synthesis
**Version**: 1.0.0
**Status**: Stable

## Overview

Multi-engine text-to-speech synthesis studio with 10 engines, voice cloning, and prosodic control. GPU-accelerated (CUDA 12.4) with Gradio web interface. Accessible via Pinokio at port 7861.

## Capabilities

- 10 TTS engines: Kokoro, F5-TTS, KittenTTS, VoxCPM, MaskGCT, IndexTTS, Spark, CosyVoice, Dia, FishSpeech
- Voice cloning from reference audio
- Multi-language support (English, Chinese, Japanese, Korean, and more)
- Batch synthesis for long texts
- Prosodic control (emphasis, pauses, speed)
- Real-time streaming output

## Trigger Phrases

| Natural Language Phrase | Action | Engine |
|-------------------------|--------|--------|
| "speak hello" | Synthesize with default engine | Kokoro |
| "say this in Japanese" | Language-specific synthesis | Kokoro/F5 |
| "clone this voice" | Voice cloning from sample | F5-TTS |
| "read this document" | Long-form batch synthesis | Kokoro |
| "synthesize with emotion" | Prosodic synthesis | CosyVoice |

## API Endpoints

### Gradio Predict API

Base URL: `http://localhost:7861/gradio_api`

**Quick synthesis (Kokoro engine):**
```bash
curl -X POST http://localhost:7861/gradio_api/call/kokoro_predict \
  -H "Content-Type: application/json" \
  -d '{"data": ["Hello world", "af_heart", 1.0]}'
```

**F5-TTS with voice cloning:**
```bash
curl -X POST http://localhost:7861/gradio_api/call/f5_predict \
  -H "Content-Type: application/json" \
  -d '{"data": ["Text to speak", "<reference_audio_path>", "Reference transcript"]}'
```

**List available endpoints:**
```bash
curl http://localhost:7861/gradio_api/info
```

### Available Predict Endpoints

| Endpoint | Engine | Parameters |
|----------|--------|------------|
| `/gradio_api/call/kokoro_predict` | Kokoro | text, voice, speed |
| `/gradio_api/call/f5_predict` | F5-TTS | text, ref_audio, ref_text |
| `/gradio_api/call/kitten_predict` | KittenTTS | text, voice |
| `/gradio_api/call/voxcpm_predict` | VoxCPM | text, style |
| `/gradio_api/call/maskgct_predict` | MaskGCT | text, ref_audio |
| `/gradio_api/call/indextts_predict` | IndexTTS | text, ref_audio |
| `/gradio_api/call/spark_predict` | Spark | text, voice |
| `/gradio_api/call/cosyvoice_predict` | CosyVoice | text, voice, emotion |
| `/gradio_api/call/dia_predict` | Dia | text, style |
| `/gradio_api/call/fish_predict` | FishSpeech | text, ref_audio |

## Health Check

```bash
curl http://localhost:7861/gradio_api/info
```

## Cross-Machine Access

Via Tailscale mesh: `http://100.x.x.x:7861`
Via Pinokio Caddy proxy: `https://7861.localhost` or `http://localhost:42XXX`

**Note:** TTS bind address is controlled by `${TTS_BIND:-0.0.0.0}:7861`. Verify active bind mode before assuming mesh reachability — current TAC status may record remote access as blocked when TTS is localhost-bound. Use Caddy proxy or confirm `TTS_BIND=0.0.0.0` in env.shared for mesh access.

## Integration Points

- **Flute-Gateway**: `http://localhost:8055` routes prosodic synthesis through TTS engines
- **Cast TTS**: `http://localhost:8060` for Google Home speaker output
- **NATS Subject**: `voice.tts.request.v1` (via Flute-Gateway)
- **Prometheus**: Metrics via Flute-Gateway `/metrics`

## See Also

- [Flute-Gateway](../../../../.claude/context/flute-gateway.md)
- [Voice Pipeline TAC](../../../../pmoves/configs/tac_trees/voice-agents.tac.yaml)
