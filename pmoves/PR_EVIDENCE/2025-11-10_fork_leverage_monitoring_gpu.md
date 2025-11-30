# PR Evidence — Fork Leverage, Dynamic Tracking, Loki, GPU Rerank (Nov 10, 2025)

## Summary
- PMOVES.YT leverages yt-dlp fork fully with dynamic docs tracking to Supabase; Console tile shows live version/extractor counts.
- Loki readiness wired into dashboard; example panel + alert JSON shipped; make helper added.
- GPU rerank strict smoke re-enabled and evidence helper added; defaults aligned to Qwen for GPU.

## Verification Commands
- Supabase + docs sync
```
make -C pmoves supabase-bootstrap
make -C pmoves yt-docs-sync
make -C pmoves yt-docs-catalog-smoke
```
- Loki readiness
```
make -C pmoves up-monitoring
make -C pmoves loki-ready
# Grafana: http://localhost:3002 (import docs/grafana/alerts/loki_readiness_alert.json if desired)
```
- GPU strict smoke + evidence
```
# Ensure v2-gpu is up; internet/GPU available
GPU_SMOKE_STRICT=true make -C pmoves smoke-gpu || true
make -C pmoves gpu-rerank-evidence
# Output under pmoves/docs/logs/<timestamp>_gpu_rerank_smoke.txt
```
- Console UI: yt‑dlp Status
```
npm --prefix pmoves/ui run dev
# Open: http://localhost:3000/dashboard/services/yt-dlp
```

## Screenshots / Notes
- Attach Grafana “Services Overview” with green Loki /ready stat.
- Attach Console tile showing yt-dlp version + extractor count.

