# ffmpeg-whisper — Subsystem Context

> Subsystem-specific CLAUDE.md. Load when working inside `pmoves/services/ffmpeg-whisper/`. README (this directory) covers operator setup; this doc captures the developer-facing model.

## Role in the mesh

Transcription is the **single chokepoint between audio media and the text-driven retrieval graph (Hi-RAG)**. Quality and latency here ripple across:
- PMOVES.YT ingestion (YouTube → transcript → Hi-RAG embed)
- Voice agents (mic → transcript → reasoning loop)
- Live captioning and accessibility surfaces

When changing model selection, GPU placement, or batching, expect to break or improve all three downstream pipelines simultaneously.

## Model selection rules

- **Default**: `large-v3` (best accuracy, ~1-2× realtime on RTX 3090 Ti).
- **PMOVES.YT batch**: `large-v3` always; ingest speed is not user-facing.
- **Voice agents (live)**: `small` or `medium` — latency-bound; users perceive >2s as broken.
- **NEVER** silently swap models. Make the env-var explicit in the call site.

## CHIT integration

**Status: None** per `pmoves/docs/audit/CHIT_INTEGRATION_STATUS.md`. ffmpeg-whisper does not directly sign CHIT trails — it produces text artifacts that are then signed by Hi-RAG when embedded.

If a code path here needs CHIT signing, route the artifact through Hi-RAG; do NOT add `chit_signing.py` to this service.

## GPU contention

This service competes for GPU with:
- TTS (Ultimate-TTS-Studio, Flute-Gateway)
- Vision (ComfyUI watchers)
- LLM inference (TensorZero local providers)

Mitigation: GPU Orchestrator (`pmoves/services/gpu-orchestrator/`) gates GPU lifecycle. When adding new GPU consumers in this service, check `/gpu:status` first and respect the orchestrator's allocation hints.

## Common tasks

- **Add a new model**: extend the model-size enum + verify VRAM headroom on a 24GB box; document in README env-var table.
- **Change batching**: benchmark against PMOVES.YT (large files) AND voice-agent (small chunks); both must improve or stay flat.
- **Debug a stuck transcribe**: `docker logs pmoves-ffmpeg-whisper`; check `/healthz`; verify GPU availability via `nvidia-smi` (or `rocm-smi` on RDNA Phase-C).

## Cross-references

- README: this directory.
- TAC tree: no dedicated TAC yet — pairs with `pmoves/docs/TAC/TAC_PMOVES_YT.md` (TODO: dedicated TAC).
- Audit: `pmoves/docs/audit/2026-05-15-service-doc-audit.md` flagged this as P1 priority fix.
- Known Road: `make -C pmoves up-ffmpeg-whisper`.
