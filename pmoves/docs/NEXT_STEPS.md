# PMOVES v5 • NEXT_STEPS
_Last updated: 2025-09-03_

## Immediate
- [x] Prepare PR and branch for feature rollup (done in this PR)
- [x] Add/refresh ROADMAP and NEXT_STEPS (committed in this PR)
- [ ] Set Discord webhook in `.env` and activate n8n flows (pending: env + flow wiring)
- [ ] Configure Jellyfin API key (+ optional user id) (pending: local instance)
- [ ] Test PDF + MinIO ingestion with a sample object (pending: PDF lane is not yet implemented in this repo)

## Short-term (September)
- [ ] Publisher: Jellyfin library refresh (cron/webhook) — not implemented yet
- [ ] Discord: rich embeds (cover art, duration, links) — not implemented yet
- [x] ComfyUI ↔ MinIO presign endpoint — implemented (services/presign); example notebook still pending
- [~] Hi‑RAG: reranker toggle (bge‑rerank‑base) + eval sweep — toggle + eval scripts done; labeled sweeps/CI pending
- [ ] Neo4j: seed brand alias dictionary (DARKXSIDE, POWERFULMOVES) — pending
- [ ] Windows/WSL polish: add scripts/smoke.ps1 and helper commands — pending

## Later
- [ ] Office docs conversion lane (libreoffice headless → PDF)
- [ ] OCR: image ingestion with text extraction + tagging
- [ ] CI: retrieval‑eval in GH Actions with artifacts
- [ ] Proxmox templates and cluster notes

## Next Session Focus
- [ ] media-video: insert `detections`/`segments` into Supabase and emit `analysis.entities.v1`
- [ ] media-audio: insert `emotions` into Supabase and emit `analysis.audio.v1`
- [ ] ffmpeg-whisper: switch to `faster-whisper` with GPU auto-detect (Jetson/desktop)
- [ ] CLIP embeddings on keyframes (optional; desktop on by default, Jetson off)
- [ ] n8n flows: end-to-end ingest → transcribe → extract → index → notify
- [ ] Jellyfin refresh hook + Discord rich embeds (cover art, duration, link)
- [ ] Supabase RLS hardening pass (non-dev)
- [ ] Qwen2-Audio provider (desktop-only toggle) for advanced audio QA/summarization
