# PR: v2 Supabase Realtime DNS fallback + v2‑GPU Qwen reranker default + Meili enabled

## Summary
- Fixes intermittent "Name or service not known" on Supabase Realtime in `hi-rag-gateway-v2` by auto‑deriving a host‑gateway websocket URL when a host‑only DNS name leaks into `SUPABASE_REALTIME_URL`.
- Sets Qwen reranker as default for `hi-rag-gateway-v2-gpu` and exposes env overrides.
- Enables Meilisearch lexical scoring by default via `pmoves/.env.local`.
- Cleans up Neo4j deprecation by replacing `exists(e.type)` with `e.type IS NOT NULL` (v2 and legacy v1 gateways).

## Changes
- Code: `pmoves/services/hi-rag-gateway-v2/app.py`
  - Adds `_hostname_resolves()` and container‑aware `_derive_realtime_url()` fallback to `ws://host.docker.internal:54321/realtime/v1/websocket` using `SUPA_REST_INTERNAL_URL`/`SUPA_REST_URL`.
  - Updates Neo4j warm query to `CASE WHEN e.type IS NOT NULL THEN e.type ELSE 'UNK' END`.
- Code: `pmoves/services/hi-rag-gateway/gateway.py`
  - Same Neo4j exists() → IS NOT NULL change.
- Compose: `pmoves/docker-compose.yml`
  - v2‑GPU: default reranker → `Qwen/Qwen3-Reranker-4B` (overridable).
- Env: `pmoves/.env.local`
  - Adds robust defaults for Supabase REST/Realtime and sets `USE_MEILI=true`, Qwen reranker flags.
- Docs: `pmoves/docs/LOCAL_DEV.md`
  - Notes fallback behavior and explicit override.
- Evidence: `pmoves/docs/logs/2025-10-19_*.txt`

## Rationale
- `api.supabase.internal` resolves on the host/CLI network, not inside the app network. The fallback ensures v2 remains resilient and subscribes without manual restarts.
- Qwen reranker is the target default for GPU path per recent validation.
- Meili improves lexical grounding compared to rapidfuzz‑only fallback.

## Validation
- v2 startup now shows:
  - `Supabase realtime geometry listener started (url=ws://host.docker.internal:54321/realtime/v1/websocket)`
  - `Subscribed to Supabase realtime geometry.cgp.v1 channel`
- Logs: see `pmoves/docs/logs/2025-10-19_v2_realtime_fix.txt`.
- GPU smoke: `make smoke-gpu` OK; Qwen smoke uses `make smoke-qwen-rerank`.
- Neo4j: no `Statement.SyntaxError` for `exists(variable.property)`.

## Local CI
- Please run on your host:
  - `make smoke`
  - `make smoke-gpu`
  - Optionally: `make smoke-rerank` and `make retrieval-eval-smoke`

## Rollout / Config
- Ensure `pmoves/.env.local` exists with:
  - `SUPA_REST_URL=http://host.docker.internal:54321/rest/v1`
  - `SUPA_REST_INTERNAL_URL=http://host.docker.internal:54321/rest/v1`
  - `SUPABASE_REALTIME_URL=ws://host.docker.internal:54321/realtime/v1/websocket`
  - `USE_MEILI=true`
  - `RERANK_MODEL=Qwen/Qwen3-Reranker-4B` (v2‑GPU)

## Next
- If desired, make Meili default on directly in compose (instead of env) and wire retrieval‑eval artifact capture in CI.
