# PMOVES v5 • Stabilization Checklist
Last updated: 2025-12-14

Goal: one-command bring-up, no red containers, and smoketests green for M2 (Creator & Publishing).

## 0) Prereqs / sanity
- [ ] `git submodule update --init --recursive` completes cleanly.
- [ ] Docker can pull/build without Desktop credential-helper errors:
  - Recommended: repo-scoped Docker config at `/.docker-nocreds/` (auto-used by `pmoves/Makefile`).
- [ ] GitHub auth for GHCR push: `gh auth status` OK; token includes `write:packages` when publishing images.
- [ ] Secrets are **not** in compose files; they live in `pmoves/env.shared` / GitHub Secrets / vault.

## 1) Bring-up (single env)
- [ ] Supabase CLI stack up and healthy:
  - `make -C pmoves supa-start`
  - `make -C pmoves supa-status`
  - `make -C pmoves supabase-bootstrap`
- [ ] Core + agents + n8n + monitoring:
  - `make -C pmoves up-all`

## 2) n8n (workflows + activation)
- [ ] n8n reachable: `http://localhost:5678/healthz` returns 200.
- [ ] Import + repair + activate:
  - `make -C pmoves n8n-bootstrap`
- [ ] Confirm workflows are active:
  - `docker exec -i pmoves-n8n n8n list:workflow --active=true`

## 3) Voice Agents (local model, end-to-end)
- [ ] Flute gateway health shows NATS connected:
  - `curl -sf http://localhost:8055/healthz | jq .`
- [ ] End-to-end voice smoke (n8n webhook → Agent Zero publish → NATS):
  - `make -C pmoves voice-agent-smoke`
- [ ] VibeVoice (realtime TTS): confirm `GET /config` returns 200, then ensure `VIBEVOICE_URL` points at it and restart `flute-gateway` if needed.
  - Option A (host / Pinokio): run the Pinokio VibeVoice server, then set `VIBEVOICE_URL=http://host.docker.internal:<PORT>`.
    - See `pmoves/docs/ARTSTUFF/VibeVoice-RealtimeREADME.md`
  - Option B (Docker profile, downloads large model weights): `make -C pmoves up-vibevoice` (expects `http://localhost:${VIBEVOICE_HOST_PORT:-3000}/config`).
    - Note (RTX 5090 / SM_120): the Docker VibeVoice launcher auto-falls back to `--device cpu` when the bundled PyTorch build can’t run CUDA kernels yet; synthesis will be slower until a compatible wheel lands.
  - Flute `/healthz` will show `"vibevoice": false` until VibeVoice is running.

## 4) Core smokes (release gates)
- [ ] Core smoke:
  - `make -C pmoves smoke`
- [ ] GPU smoke (strict rerank telemetry):
  - `GPU_SMOKE_STRICT=true make -C pmoves smoke-gpu`
- [ ] CHIT contract check:
  - `make -C pmoves chit-contract-check`

## 5) Jellyfin + publisher (baseline)
- [ ] Jellyfin bridge health:
  - `make -C pmoves health-jellyfin-bridge`
- [ ] Jellyfin playback smoke (requires at least one `videos` row):
  - `make -C pmoves jellyfin-smoke`
  - If it prints “No videos found”, seed with: `make -C pmoves yt-emit-smoke`

## 6) UI (dev)
- [ ] Console dev server reachable:
  - `make -C pmoves ui-dev-start` → `http://localhost:3001`
- [ ] Notebook Workbench smoke (if you touched UI wiring):
  - `make -C pmoves notebook-workbench-smoke ARGS="--thread=<uuid>"`

## 7) Evidence capture (for PR)
- [ ] Save logs in `pmoves/docs/logs/` (optional but recommended):
  - `make -C pmoves gpu-rerank-evidence`
  - `make -C pmoves archon-mcp-evidence`
  - `make -C pmoves evidence-auto`
