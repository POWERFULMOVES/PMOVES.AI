# SESSION_IMPLEMENTATION_PLAN — Stabilization Snapshot (Nov 7, 2025)

Owner: @POWERFULMOVES  • Agents: @AGENTS

## Completed This Session
- SupaSerch service
  - FastAPI worker now connects to `supaserch.request.v1`/`supaserch.result.v1`, exposes Prometheus counters/histograms, and reports NATS status via `/healthz` + `/metrics`.
  - Added `make supaserch-smoke` harness publishing a labelled envelope, asserting the NATS round-trip, and confirming the HTTP fallback diagnostics.
  - Console dashboard now links directly to SupaSerch health/metrics, and the service README captures runbook + monitoring guidance.
- GPU smokes
  - Strict rerank validation is the default (`GPU_SMOKE_STRICT=true`), with the Qwen3 4B reranker pinned via `RERANK_MODEL_PATH` in `env.shared.example` and stats verification baked into `make smoke-gpu`.
- Agent Zero
  - UI bound to port 80 in-container; host mapping 8081→80. Verified 200 on http://localhost:8081/.
  - JetStream resilience: forced JetStream outage by relocating `/tmp/nats/jetstream`, published `agentzero.memory.update` task, and observed fallback warning at log line 4444; threshold env `AGENTZERO_JS_UNAVAILABLE_THRESHOLD` (compose default 1 for local).
- Console UI
  - Notebook Workbench view now shows dashboard navigation by default; dashboard pill bar exposes runtime + workbench entries without additional props.
- DeepResearch
  - In-network NATS smoke target (`make -C pmoves deepresearch-smoke-in-net`) returns status=success.
  - Echo subscribers stabilized (URL normalization, retries, no empty args).
  - Core `make smoke` now runs `deepresearch-smoke` automatically when OpenRouter + Notebook credentials are present and logs a skip hint otherwise.
- Monitoring & docs
  - Node Exporter toggle for Linux (`MON_INCLUDE_NODE_EXPORTER=true`); cAdvisor default.
  - SupaSerch, Hi-RAG, and smoke documentation refreshed with the new targets and health probes; GHCR image pins for DeepResearch/SupaSerch captured in `env.shared.example`.

## Evidence
- See `pmoves/PR_EVIDENCE/*` for current smoke/health outputs appended to the PR.
- JetStream fallback log capture (Nov 7, 2025):

   ```bash
   docker compose -p pmoves logs agent-zero | sed -n '4440,4455p'
   ```

   ```
   WARNING:services.agent_zero.controller:JetStream pull loop error for agentzero.memory.update (agentzero-agentzero-memory-update): nats: ServiceUnavailableError: code=None err_code=None description='None'
   WARNING:services.agent_zero.controller:Falling back to core NATS subscription for agentzero.memory.update after repeated ServiceUnavailable
   ```

   Triggered by moving `/tmp/nats/jetstream` out of the NATS container and posting a valid `/events/publish` payload to exercise the fallback path.

## Next Steps (handoff to @AGENTS)
1) SupaSerch orchestration depth
   - Replace the stubbed multimodal plan with real DeepResearch + Archon/Agent Zero execution, persisting aggregated results into Supabase and emitting geometry packets.
   - Extend the smoke harness (or add a follow-on check) to assert stage status transitions and capture Prometheus counters for published results.
2) Loki readiness & alerts
   - Finalize `/ready` 200 for Loki; wire basic alerts in Grafana (Services Overview dashboard) now that SupaSerch metrics are live.
3) Real Data Bring-Up
   - Complete repo indexing (`make -C pmoves index-repo-docs`) and flip strict geometry jump by default so ShapeStore warm-up stays deterministic.
4) n8n monitoring & automation activation
   - Ensure `N8N_API_AUTH_ACTIVE=true`, add a blackbox probe covering `/healthz`, and execute the Supabase → Agent Zero → Discord activation checklist with evidence in this plan.
5) Retrieval + geometry hardening
   - Record GPU rerank warm-start troubleshooting (cache size, download timing) and align persona/pack gates with the strict geometry defaults before turning on CI enforcement.

## Notes
- Single-env policy remains active; Supabase REST is canonical for `public,pmoves_core,pmoves_kb`.
- Node Exporter is Linux-only; on macOS/Windows, keep using cAdvisor only.
- JetStream fallback ensures Agent Zero remains responsive even when JetStream is warming up.

