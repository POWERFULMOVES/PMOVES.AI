# CLIP + Qwen2-Audio Integration Plan
_Last updated: 2025-10-14_

## Objective
Upgrade PMOVES media enrichment to support multimodal reranking and acoustic captioning by integrating:
- **OpenAI CLIP** (or alternative open-source CLIP variant) for visual embeddings and thumbnail similarity.
- **Qwen2-Audio** (Ollama-hosted) for improved audio transcripts, tags, and mood metadata.

## Target Services
| Service | Integration | Notes |
| --- | --- | --- |
| `services/hi-rag-gateway-v2` | CLIP embeddings for image/video frames; optional reranker step. | Deploy as a new provider (`RERANK_PROVIDER=clip`). |
| `services/jellyfin-audio-processor` | Qwen2-Audio summarization and tags. | Consumes Ollama models via `jellyfin-qwen-audio`. |
| `services/publisher` | Attach CLIP/Qwen metadata to `content.published.v1` payloads. | Populate `meta.clip_similarity`, `meta.audio_tags`. |

## Work Streams
1. **Model provisioning**
   - Extend `docker-compose.jellyfin-ai.yml` to pre-pull CLIP + Qwen models (via Ollama or Hugging Face cache mounts).
   - Document GPU/CPU footprints; default to quantized models (`CLIP ViT-B/32`, `Qwen2-Audio-7B Q4`).

2. **Gateway support (CLIP)**
   - Add provider module under `services/hi-rag-gateway-v2/providers/clip.py` implementing rerank interface.
   - Expose configuration via env: `CLIP_ENDPOINT`, `CLIP_MODEL`, `CLIP_TIMEOUT`.
   - Update `RERANK_PROVIDER` handling to accept `clip` with fallback to existing providers.

3. **Audio processor enhancements (Qwen)**
   - Implement adapter to call `QWEN_AUDIO_URL` for each processed media item; store summary, tags, and mood in Supabase (`media_audio_analysis`).
   - Add CLI flag / env toggle: `JELLYFIN_AUDIO_QWEN_ENABLE=true`.
   - Update backfill script to optionally reprocess historical items.

4. **Publisher metadata wiring**
   - Extend `build_published_payload()` to include new fields when available:
     ```json
     {
       "meta": {
         "clip_best_match": {
           "asset_id": "...",
           "score": 0.87
         },
         "audio_tags": ["orchestral", "uplifting"],
         "audio_summary": "...",
         "qwen_confidence": 0.72
       }
     }
     ```
   - Update Discord embed formatter to surface audio mood + top CLIP match when present.

5. **Smoke tests**
   - Add `make smoke-clip` to evaluate reranking on a sample query.
   - Add `make jellyfin-qwen-smoke` to verify Qwen summaries are written to Supabase.

6. **Documentation & onboarding**
   - Extend `pmoves/docs/LOCAL_TOOLING_REFERENCE.md` with new toggles.
   - Publish a focused guide (`docs/CLIP_QWEN_SMOKE.md`) once implementation lands.

## Dependencies & Risks
- Requires GPU for best performance; document CPU fallback or quantized performance expectations.
- Ollama model licensing: ensure redistributable weights or provide install instructions.
- Discord embed payload size: additional fields must stay under Discord limits (6000 characters).

## Rollout Checklist
- [ ] Finalize provider implementations and unit tests.
- [ ] Add environment variables to bootstrap registry.
- [ ] Update make targets to include new smoke tests.
- [ ] Capture evidence: rerank diff, Discord embed screenshot with CLIP/Qwen metadata.
- [ ] Update `pmoves/docs/NEXT_STEPS.md` with completion date.
