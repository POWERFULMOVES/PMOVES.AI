# feat: LangExtract core + Hi‑RAG v2 hybrid, data IO, Supabase full, realtime UI, avatars

## Summary
This PR elevates LangExtract to a core library + service, upgrades the Hi‑RAG v2 gateway to a hybrid (vector + lexical + graph + rerank) pipeline, adds data loaders and evaluation, integrates a local‑first Supabase backend (stub + optional full stack), and provides a realtime demo UI with avatar upload/assignment for agents and content.

## Highlights
- LangExtract core (`libs/langextract`) with providers: rule (default, offline), openai‑compatible, gemini
- Hi‑RAG v2: hybrid vector+lexical (alpha), Neo4j entity boost, rerank fusion (mul/wsum), admin + logging
- Embeddings: local‑first resolver (Ollama → OpenAI‑compat [LM Studio/vLLM/NIM/OpenRouter/Groq] → HF → ST fallback)
- Data IO: JSONL/CSV loaders, Qdrant/Meili seeding/export; Make/PS tasks
- Supabase: Postgres + PostgREST in main compose; optional full stack via `docker-compose.supabase.yml`
- Realtime + Avatars: browser demo (supabase‑js), server‑proxied upload to Storage, assign avatar to studio_board and pmoves_core.agent

## New/Updated Services
- `services/hi-rag-gateway-v2`: unified hybrid + rerank gateway
- `services/langextract`: extract text/XML → chunks + structured errors
- `services/extract-worker`: ingest chunks to Qdrant/Meili, errors to Supabase
- `services/presign`, `services/render-webhook` added
- Retrieval‑Eval: `/samples`, `/query`, static UI, metrics script

## Compose & Scripts
- `docker-compose.yml`: Postgres + PostgREST, named network `pmoves-net`
- `docker-compose.supabase.yml`: GoTrue/Auth, Realtime, Storage, Studio (dev‑friendly)
- `scripts/pmoves.ps1`: `up`, `down`, `up-fullsupabase`, `seed-data`, `load-jsonl`, `load-csv`, `export-jsonl`, `eval-jsonl`, `init-avatars`

## Environment
- `.env.example` expanded: Qdrant/Meili/Neo4j, embedding providers, Supabase (REST/Storage/keys)
- For full Supabase (CLI): set `SUPA_REST_URL=http://localhost:54321/rest/v1` and provide anon key to UI

## Database Init (local dev)
- `supabase/initdb`: pmoves_core schema, public tables (studio_board, it_errors), agents with `avatar_url`, permissive RLS

## Docs
- README Quickstart; `docs/LOCAL_DEV.md`, `DATA_IMPORT.md`, `LANGEXTRACT.md`, `SUPABASE_FULL.md`, `REALTIME_LISTENER.md`, `RENDER_COMPLETION_WEBHOOK.md`

## How To Run
- Full stack (compose): `./scripts/pmoves.ps1 up-fullsupabase` then `./scripts/pmoves.ps1 up`
- Seed data: `./scripts/pmoves.ps1 seed-data`
- Realtime demo: open `http://localhost:8090/static/realtime.html` (enter Supabase URL + anon key)
- Upload avatar (UI) → assign to studio_board or agent, watch events live

## Testing
- Smoke: `make smoke` (or use endpoints from docs)
- Eval: `make eval-jsonl FILE=./datasets/queries_demo.jsonl K=5` (CSV mode supported)

## Compatibility / Notes
- Legacy `hi-rag-gateway` retained under profile `legacy`.
- Compose setup is dev‑oriented; prefer Supabase CLI for robust full‑stack features.

## Follow‑ups (optional)
- Envelope + NATS events from LangExtract for Agent‑Zero
- Neo4j linker for `it_errors` and agent relationships
- Richer eval sets, precision/recall@k reporting, CSV export

