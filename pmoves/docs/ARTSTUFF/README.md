# ARTSTUFF (Operator Notes)

`pmoves/docs/ARTSTUFF/` is a **scratchpad of operator runbooks and installers** for creative tooling (ComfyUI nodes/models) and realtime demo servers (VibeVoice, WAN, Qwen image edit).

These assets are **not** part of the default PMOVES Docker stack unless explicitly wired in.

## What is expected to be “running”

- **PMOVES services (Docker)**: Flute Gateway, ffmpeg-whisper, publisher, etc. are started via `make -C pmoves up` / `make -C pmoves up-agents-ui`.
- **Realtime model demos (usually host/Pinokio/Runpod)**:
  - `pmoves/docs/ARTSTUFF/realtime/README.md` describes a **Pinokio** launcher for VibeVoice Realtime.
  - The Windows `.bat` scripts here install ComfyUI Manager nodes/models into an existing ComfyUI install.

## Ultimate TTS Studio (SUP3R Edition) UI

The repo `SUP3RMASS1VE/Ultimate-TTS-Studio-SUP3R-Edition` is a **creator-workstation Gradio UI** that bundles multiple voice engines (including VibeVoice).

- Recommended runtime: **Pinokio / Windows creator workstation** (matches upstream assumptions; GPU-heavy).
- Entry docs:
  - `pmoves/docs/ARTSTUFF/Ultimate-TTS-Studio-SUP3R-EditionREADME.md` (quick pointer)
  - `pmoves/docs/ARTSTUFF/Ultimate-TTS-Studio-SUP3R-EditionREADMECLAUDE.md` (operational notes)

How it feeds PMOVES:
- Generate audio assets locally, then either:
  - upload to S3/MinIO via the Creator pipeline and trigger the `vibevoice-to-cgp` webhook in n8n, or
  - post a `studio_board` row directly (advanced) and let the publish pipeline pick it up.

Docker option (preferred for PMOVES “all green”): use the hardened fork image.
- Start: `make -C pmoves up-tts-studio`
- Smoke: `make -C pmoves tts-studio-smoke`

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

## ComfyUI (Docker vs creator workstation)

Most of the `.bat` installers in this folder are designed for a **Windows creator workstation** ComfyUI install.

For Docker-based local dev, PMOVES also provides an optional ComfyUI service:
- Start: `make -C pmoves up-comfyui` (host `:${COMFYUI_HOST_PORT:-8188}`)
- Smoke: `make -C pmoves comfyui-smoke`

This is primarily used by the `pmoves_comfy_gen` workflow (n8n → `http://comfyui:8188/prompt`).
