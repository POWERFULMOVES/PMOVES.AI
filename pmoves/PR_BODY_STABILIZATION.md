## PMOVES.AI — Stabilization Sprint (Nov 6, 2025)

This PR captures infra/app hardening completed today and a short plan to finish the sprint.

### Summary
- Storage unified to Supabase Storage S3 endpoint. Presign + Render Webhook recreated and validated.
- Invidious stabilized on 127.0.0.1:3005 with valid companion/HMAC keys.
- Hi‑RAG v2 CPU/GPU up; health at /hirag/admin/stats; core smoke PASS (14/14).
- Jellyfin verified (8096); bridge up.
- Monitoring stack online (Prometheus/Grafana); Loki config upgraded and starting. Readiness converging.

### Notable decisions
- Supabase‑only storage (standalone MinIO stopped by default).
- YouTube smoke will force offline transcript provider when SABR detected.
- GPU rerank temporarily disabled for smoke while model/runtime are validated.

### Operator quick links
- Supabase REST: http://127.0.0.1:65421/rest/v1 • Studio: http://127.0.0.1:65433
- Hi‑RAG v2 GPU: http://localhost:8087/hirag/admin/stats • CPU: http://localhost:8086/hirag/admin/stats
- Invidious: http://127.0.0.1:3005 • Jellyfin: http://localhost:8096
- Grafana: http://localhost:3002 • Prometheus: http://localhost:9090

### Evidence
- make -C pmoves smoke → PASS 14/14
- Invidious /api/v1/stats → 200
- Loki: restarting → now running; /ready returns 503 while warming; config updated to 3.1 schema.
- pmoves-yt /yt/emit still failing with 502 (SABR path; next steps below).

### Follow‑ups (next 48h)
- [ ] Loki: finish config polish until /ready=200; wire panels in Grafana
- [ ] YT emit: set YT_TRANSCRIPT_PROVIDER=qwen2-audio in smoke; broaden SABR fallback; add stable IDs
- [ ] GPU rerank: re‑enable and add integration smoke
- [ ] Document Hi‑RAG health path and Supabase‑only storage in service docs + SMOKETESTS

### Files touched
- AGENTS.md — stabilization status, quick links, decisions, next actions
- pmoves/AGENTS.md — operator quick links, env notes, next actions
- pmoves/docs/NEXT_STEPS.md — “Stabilization Sprint — Status and Plan”
- pmoves/docs/PMOVES.AI PLANS/ROADMAP.md — new sprint milestone
- pmoves/monitoring/loki/local-config.yaml — 3.1‑compatible config


### Tailscale integration & latest smoke results
- Added optional auto-join in first-run; Makefile targets (tailscale-save-key/join/rejoin/status/logout) and mini_cli join/rejoin commands.
- Key stored locally at CATACLYSM_STUDIOS_INC/PMOVES-PROVISIONS/tailscale/tailscale_authkey.txt (0600). Not versioned.
- ARC docs updated with overlay/admin guards section.

### Current status (Nov 6, 2025)
- Core 12-step smoke: PASS
- Monitoring: Prometheus/Grafana/Loki/Blackbox up; quick report prints healthy probes
- Jellyfin verify (single): PASS at http://localhost:8096
- pmoves-yt → geometry:
  - /yt/emit OK (chunks upserted; /hirag/upsert-batch 200; /geometry/event 200)
  - /shape/point jump returns {detail: point not found} for p:yt:<vid>:0 after 10 retries via in-container curl; CGP reaching gateway confirmed. Follow-up: align point-id expectation or wait for async indexing.

### Commands from this pass
```
make -C pmoves tailscale-save-key   # local only; not committed
make -C pmoves tailscale-join
make -C pmoves up
make -C pmoves up-agents
make -C pmoves up-external
make -C pmoves up-invidious
make -C pmoves smoke
make -C pmoves jellyfin-verify-single
make -C pmoves yt-emit-smoke URL=https://www.youtube.com/watch?v=jNQXAC9IVRw
```
