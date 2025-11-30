Title: Stabilization: Agent Zero UI + JetStream resilience, GPU smokes, DeepResearch in‑net smoke, Monitoring toggle

Summary
- Fix Agent Zero UI ERR_EMPTY_RESPONSE by aligning container UI to port 80; host 8081→80 now responds 200.
- Add JetStream resilience to Agent Zero controller: auto‑fallback to core NATS after repeated ServiceUnavailable.
- Harden DeepResearch: add in‑network NATS smoke and echo subscriber fixes; request decoder fallback.
- Improve GPU smokes: strict/relaxed modes; relaxed default for bring‑up; strict requires `used_rerank==true`.
- Monitoring: add Node Exporter toggle (Linux) alongside cAdvisor; expand docs + checks.
- Update AGENTS.md, NEXT_STEPS.md, ROADMAP.md with latest changes and next‑commit targets.

Key Changes
- Agent Zero
  - UI: serve on port 80 in‑container; compose maps host 8081→80.
  - JetStream: controller now counts `ServiceUnavailableError` in pull loop and falls back to core NATS queue subs once threshold exceeded (`AGENTZERO_JS_UNAVAILABLE_THRESHOLD`, default 3; compose uses 1 for local).
- DeepResearch
  - New target `deepresearch-smoke-in-net`: copies a minimal smoke script into the container and verifies request→result via in‑net NATS.
  - Echo subscribers: robust NATS URL handling, retries; no empty `--nats` argument.
  - Worker: `_decode_request` backwards‑compatible when `extras` param is absent.
- GPU smokes
  - `make -C pmoves smoke-gpu` tries multiple queries; relaxed mode validates presence of `used_rerank`; strict requires `true`.
  - Strict mode = `GPU_SMOKE_STRICT=true`.
- Monitoring
  - `MON_INCLUDE_NODE_EXPORTER=true make -C pmoves up-monitoring` enables Node Exporter + cAdvisor (Linux only).
  - Prometheus/Grafana/Blackbox targets validated; cAdvisor UP by default on Linux.

How to Verify
1) Agent Zero UI
   - `curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8081/` → `200`.
   - Browser: http://localhost:8081
2) Agent Zero JetStream
   - If JetStream is unavailable, controller falls back to core NATS; logs quiet down.
3) DeepResearch
   - `make -C pmoves deepresearch-smoke-in-net` → `✔ deepresearch-smoke-in-net: status=success`.
4) GPU smokes
   - Relaxed: `make -C pmoves smoke-gpu` → PASS.
   - Strict: `GPU_SMOKE_STRICT=true make -C pmoves smoke-gpu` → PASS when reranker model/runtime pinned.
5) Monitoring
   - `make -C pmoves up-monitoring` (or with Node Exporter toggle on Linux).
   - `make -C pmoves monitoring-status` shows targets UP; `make -C pmoves monitoring-report` prints summary.

Evidence (abbrev.)
```
# Agent Zero UI
$ curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8081/
200

# DeepResearch smoke (in‑net)
✔ deepresearch-smoke-in-net: status=success

# GPU smoke (relaxed)
OK

# Monitoring status (excerpt)
  - blackbox_http http://host.docker.internal:8086/hirag/healthz: up
  - channel_monitor channel-monitor:8097: up
  - deepresearch http://host.docker.internal:8098/healthz: up
  - prometheus prometheus:9090: up
```

Docs Updated
- `AGENTS.md` — latest stabilization changes + next steps
- `pmoves/docs/NEXT_STEPS.md` — latest changes + next commit targets
- `pmoves/docs/PMOVES.AI PLANS/ROADMAP.md` — Stabilization sprint notes

Notes / Gotchas
- Node Exporter requires Linux; on macOS/Windows, keep it off and rely on cAdvisor.
- GPU strict mode depends on the reranker model/runtime pinned for your node; relaxed mode remains default for CI/local smoke.
- Agent Zero JetStream fallback threshold is configurable via `AGENTZERO_JS_UNAVAILABLE_THRESHOLD`.

Next Commit Targets (tracked in NEXT_STEPS.md)
- Re‑enable GPU strict smokes by default on GPU node.
- Loki `/ready` 200 + Grafana alerts.
- Real Data Bring‑Up completion → strict geometry jump default.
- SupaSerch: add NATS subjects + metrics + console badge.
- n8n public API probe in monitoring.
- Pin GHCR images for DeepResearch/SupaSerch in `pmoves/env.shared`.

Reviewers: @POWERFULMOVES @cataclysm‑ops
Labels: stabilization, monitoring, agents, gpu, smoke‑tests
