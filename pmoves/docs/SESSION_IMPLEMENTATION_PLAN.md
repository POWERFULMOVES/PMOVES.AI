# SESSION_IMPLEMENTATION_PLAN — Stabilization Snapshot (Nov 7, 2025)

Owner: @POWERFULMOVES  • Agents: @AGENTS

## Completed This Session
- Agent Zero
  - UI bound to port 80 in-container; host mapping 8081→80. Verified 200 on http://localhost:8081/.
  - JetStream resilience: controller falls back to core NATS after repeated ServiceUnavailable; threshold env `AGENTZERO_JS_UNAVAILABLE_THRESHOLD` (compose default 1 for local).
- DeepResearch
  - In-network NATS smoke target (`make -C pmoves deepresearch-smoke-in-net`) returns status=success.
  - Echo subscribers stabilized (URL normalization, retries, no empty args).
- GPU Smokes
  - Relaxed default passes; strict mode available via `GPU_SMOKE_STRICT=true`.
- Monitoring
  - Node Exporter toggle for Linux (`MON_INCLUDE_NODE_EXPORTER=true`); cAdvisor default.
- Docs
  - AGENTS.md, NEXT_STEPS.md, ROADMAP.md updated with changes and next-commit targets.

## Evidence
- See `pmoves/PR_EVIDENCE/*` for current smoke/health outputs appended to the PR.

## Next Steps (handoff to @AGENTS)
1) SupaSerch integration
   - Add NATS subjects `supaserch.request.v1`/`supaserch.result.v1` and Prometheus metrics in services/supaserch.
   - Console tile: add health badge + quick links.
2) Loki readiness & alerts
   - Finalize `/ready` 200 for Loki; wire basic alerts in Grafana (Services Overview dashboard).
3) Real Data Bring-Up
   - Complete repo indexing (`make -C pmoves index-repo-docs`) and flip strict geometry jump by default.
4) GPU Smokes
   - Pin reranker model/runtime for 5090 node; enable strict GPU smokes by default.
5) n8n monitoring
   - Ensure `N8N_API_AUTH_ACTIVE=true`; add blackbox probe to monitoring dashboard.
6) Image pinning
   - Pin DEEPRESEARCH_IMAGE and SUPASERCH_IMAGE in `pmoves/env.shared` with GHCR tags (stable or date+sha).

## Notes
- Single-env policy remains active; Supabase REST is canonical for `public,pmoves_core,pmoves_kb`.
- Node Exporter is Linux-only; on macOS/Windows, keep using cAdvisor only.
- JetStream fallback ensures Agent Zero remains responsive even when JetStream is warming up.

