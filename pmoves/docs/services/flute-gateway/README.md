# flute-gateway — Service Guide

Status: Implemented (compose)

Overview
- `flute-gateway` is PMOVES.AI's voice gateway for TTS, STT, persona-backed speech flows, and Pipecat streaming.
- It fronts VibeVoice, Ultimate TTS Studio, and ffmpeg-whisper, and can emit CHIT voice attribution events when enabled.

Compose
- Service: `flute-gateway`
- Ports: `8055:8055` (HTTP), `8056:8056` (WebSocket)
- Profiles: `orchestration`, `media`
- Depends on: NATS, Supabase, voice providers such as VibeVoice and/or Ultimate TTS

Environment
- `NATS_URL` — event bus connection
- `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` — persona/config lookups
- `TENSORZERO_URL` — LLM handoff for voice-agent flows
- `DEFAULT_VOICE_PROVIDER` — default voice backend (`vibevoice` by default)
- `FLUTE_API_KEY` — optional API key gate for HTTP routes
- `VIBEVOICE_URL` — VibeVoice endpoint
- `ULTIMATE_TTS_URL` — Ultimate TTS Studio endpoint
- `WHISPER_URL` — ffmpeg-whisper endpoint
- `CHIT_VOICE_ATTRIBUTION`, `CHIT_NAMESPACE`, `CHIT_GEOMETRY_SUBJECT` — CHIT voice event controls

Runbook
- Start the core stack:
  ```bash
  SUPABASE_RUNTIME=cli make -C pmoves up
  ```
- Optional host-run voice provider:
  ```bash
  make -C pmoves up-vibevoice
  ```
- Start Flute and its compose-side voice services:
  ```bash
  docker compose -f pmoves/docker-compose.yml --profile orchestration --profile media up -d flute-gateway ultimate-tts-studio ffmpeg-whisper
  ```
- Local code path:
  ```bash
  cd pmoves/services/flute-gateway
  python -m uvicorn main:app --host 0.0.0.0 --port 8055
  ```

Health & Ops
- Health:
  ```bash
  curl -fsS http://localhost:8055/healthz | jq .
  ```
- Metrics:
  ```bash
  curl -fsS http://localhost:8055/metrics
  ```
- Runtime voice config:
  ```bash
  curl -fsS http://localhost:8055/v1/voice/config | jq .
  ```
- Logs:
  ```bash
  docker compose -f pmoves/docker-compose.yml logs -f flute-gateway
  ```

Current API
- `GET /healthz`
- `GET /metrics`
- `GET /v1/voice/config`
- `POST /v1/voice/synthesize`
- `POST /v1/voice/synthesize/audio`
- `POST /v1/voice/recognize`
- `GET /v1/voice/personas`
- `GET /v1/voice/personas/{persona_id}`
- `WS /v1/voice/stream/tts`

Notes
- The current service implementation exposes `/v1/voice/...` routes. Older docs that point operators at `/tts/prosodic/*` are legacy shorthand and should not be treated as the canonical runtime surface.
- If `FLUTE_API_KEY` is set, send `X-API-Key` with protected calls.

Related Docs
- [.claude/context/flute-gateway.md](../../../.claude/context/flute-gateway.md)
- [FLUTE_PROSODIC_ARCHITECTURE](../../infrastructure/FLUTE_PROSODIC_ARCHITECTURE.md)
