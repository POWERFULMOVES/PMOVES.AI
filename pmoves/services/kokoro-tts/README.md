# kokoro-tts — CPU-only Kokoro TTS deploy unit

The first synthesis engine PMOVES can run on a **GPU-less node** (a KVM VPS). It
makes "it's time for agents to start talking" real on the fleet's cheap nodes.

**Why this exists:** the two CPU-viable engines (Kokoro, KittenTTS — both
Apache-2.0) previously shipped *only* bundled inside the GPU-hosted
Ultimate-TTS-Studio Pinokio app. OmniVoice, the one merged Apache engine with a
deploy unit, is hard GPU-gated (→ SPARK). Neither could run on a KVM. This is a
standalone, self-contained, CPU-only container.

- **Engine:** Kokoro-82M (Apache-2.0) via `kokoro-onnx` (onnxruntime, CPU).
- **Footprint:** ~340 MB model, ~1–2 GB RAM — comfortable on kvm4 (4vCPU/16GB);
  `role: announcer` per `tts-engine-capabilities.yaml`.
- **Output:** 24 kHz PCM16 WAV. A headless KVM has no speaker — the WAV is
  consumed downstream (flute-gateway → Discord webhook / Cast device), never
  played on the VPS.

## Run

```bash
# CPU-only; model is baked into the image at build.
docker compose -f services/kokoro-tts/kokoro.compose.yml --profile voice up -d kokoro-tts

curl -fsS localhost:8004/healthz
curl -fsS -X POST localhost:8004/synthesize \
  -H 'content-type: application/json' \
  -d '{"text":"PMOVES agents are online.","voice":"af_heart"}' -o out.wav
```

## API

| Method | Path | Body / notes |
|---|---|---|
| POST | `/synthesize` | `{text, voice?, speed?, lang?}` → `audio/wav`. Header `X-Kokoro-Token` if `KOKORO_TOKEN` set. |
| GET | `/voices` | `{voices, default}` |
| GET | `/healthz` | `{status, model_loaded, ...}` |

## flute-gateway integration

`providers/kokoro.py` (`KokoroProvider`) wraps the service on the standard
`VoiceProvider` ABC. Register it in the gateway's provider map pointing at the
node hosting kokoro-tts (default `http://host.docker.internal:8004`).

## Deploy target

`kvm4` (announcer). Co-locate the CPU-only `voice-relay` (`:8121`) and
`cast-tts-gateway` (`:8060`) for the full KVM voice path. `kvm2` (2vCPU/8GB) can
run KittenTTS by the same pattern if a sibling unit is built.

> **Validation status:** built to convention; **needs on-node build + first-synth
> validation** (model download at build, CPU synth latency on kvm4) — cannot be
> runtime-tested on a GPU-less CI/dev box without Docker + the model.
