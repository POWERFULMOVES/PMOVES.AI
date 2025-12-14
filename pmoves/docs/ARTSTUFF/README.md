# ARTSTUFF (Operator Notes)

`pmoves/docs/ARTSTUFF/` is a **scratchpad of operator runbooks and installers** for creative tooling (ComfyUI nodes/models) and realtime demo servers (VibeVoice, WAN, Qwen image edit).

These assets are **not** part of the default PMOVES Docker stack unless explicitly wired in.

## What is expected to be “running”

- **PMOVES services (Docker)**: Flute Gateway, ffmpeg-whisper, publisher, etc. are started via `make -C pmoves up` / `make -C pmoves up-agents-ui`.
- **Realtime model demos (usually host/Pinokio/Runpod)**:
  - `pmoves/docs/ARTSTUFF/realtime/README.md` describes a **Pinokio** launcher for VibeVoice Realtime.
  - The Windows `.bat` scripts here install ComfyUI Manager nodes/models into an existing ComfyUI install.

## How this connects to PMOVES

- `services/flute-gateway` can use VibeVoice for realtime TTS via `VIBEVOICE_URL`.
  - Default is `http://host.docker.internal:3000` (host-gateway) in `pmoves/docker-compose.yml`.
  - Configure in `pmoves/env.shared` or `pmoves/.env.local`:
    - `VIBEVOICE_URL=http://host.docker.internal:<PORT>`
    - `DEFAULT_VOICE_PROVIDER=vibevoice`

If VibeVoice is not running, Flute Gateway will still start, but VibeVoice provider calls will fail (health will report provider down).

## If you want it containerized

This repo ships an **optional** VibeVoice service under `pmoves/docker-compose.voice.yml` (compose profile: `voice`).

- Bring it up: `make -C pmoves up-vibevoice` (binds `:${VIBEVOICE_HOST_PORT:-3000}`; downloads model weights on first run).
- Flute can reach it either:
  - via host gateway: `VIBEVOICE_URL=http://host.docker.internal:${VIBEVOICE_HOST_PORT:-3000}` (works even if VibeVoice is run outside Docker), or
  - via service DNS (preferred when containerized): `VIBEVOICE_URL=http://vibevoice:3000`
