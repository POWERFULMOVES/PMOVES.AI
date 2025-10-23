# LangExtract (XML → JSONL for Hi‑RAG)
_Last updated: 2025-10-23_

This service and scripts convert XML into structured chunks ready for embedding and indexing.

## Service
- Endpoints:
  - POST `/extract/text` with `{ text, namespace?, doc_id? }`
  - POST `/extract/xml` with `{ xml, namespace?, doc_id? }`
  - POST `/extract/jsonl` with `{ text|xml, namespace?, doc_id? }`
- Returns: `{ count, chunks: [{doc_id, section_id, chunk_id, namespace, text, kind}], errors: [...] }`.
- Kinds: `title`, `paragraph`, `question`, `text`.
- Start: `docker compose up -d langextract`

## CLI
- XML → JSONL: `docker compose run --rm --entrypoint python -v /abs/in.xml:/in.xml -v /abs/out.jsonl:/out.jsonl langextract /app/scripts/xml_to_jsonl.py /in.xml /out.jsonl pmoves mydoc`
- Then load: `make load-jsonl FILE=/abs/out.jsonl NAMESPACE=pmoves`

## Notes
- Questions are detected from sentences ending in `?` or `<q>` tags.
- IT troubleshooting: the service also extracts structured error records from common tags/attributes (e.g., `<entry severity="..." service="...">`, `<error>`, `<exception>`, `<stacktrace>`), capturing `message`, `code`, `service`, `host`, `severity`, `timestamp`, and `stack` when present.
- The JSONL produced matches the loader format (`text` field required).

## Providers (local-first)
- `LANGEXTRACT_PROVIDER=rule` (default): Fast rule-based segmentation and IT error extraction.
- `LANGEXTRACT_PROVIDER=openai`: Uses any OpenAI-compatible endpoint (OpenAI, OpenRouter, Groq, or local LM Studio/vLLM/NIM) via `OPENAI_API_BASE`, `OPENAI_API_KEY`, `OPENAI_MODEL`.
- `LANGEXTRACT_PROVIDER=gemini`: Uses Google Gemini via `GEMINI_API_KEY`, `GEMINI_MODEL`.
- `LANGEXTRACT_PROVIDER=cloudflare`: Targets Cloudflare Workers AI chat models using `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_API_TOKEN`, and `CLOUDFLARE_LLM_MODEL` (defaults to `@cf/meta/llama-3.1-8b-instruct`). Override the API root with `CLOUDFLARE_API_BASE` if you proxy through a tunnel or mock server.
If a provider is not configured or fails, prefer `rule` for offline local use.

### Cloudflare Workers AI setup

Cloudflare now publishes an OpenAI-compatible path plus a native Workers AI run endpoint. LangExtract uses the Workers AI JSON response to stay independent of beta compatibility layers.

1. Create a Cloudflare API token with the **Workers AI:Read** and **Workers AI:Edit** permissions scoped to your account.
2. Copy your account ID from the Workers AI dashboard (`dash.cloudflare.com` → Workers AI) and set:
   - `CLOUDFLARE_ACCOUNT_ID=<uuid>`
   - `CLOUDFLARE_API_TOKEN=<token>`
   - `CLOUDFLARE_LLM_MODEL=@cf/meta/llama-3.1-8b-instruct` (or another catalog slug)
3. Optional: When routing through the OpenAI shim, set `OPENAI_API_BASE=https://api.cloudflare.com/client/v4/accounts/${CLOUDFLARE_ACCOUNT_ID}/ai` so other services discover the same backend.

**Free plan notes:** Workers AI currently ships with a daily free allotment (10k text tokens/day and 100 generations/day for meta Llama 3.1 variants). Throttle high-volume LangExtract runs or upgrade the plan before batch migrations.

**Local dev:** Populate `.env` or `env.shared` with the variables above, then run `LANGEXTRACT_PROVIDER=cloudflare uvicorn pmoves.services.langextract.api:app --reload` (or `make up` to let Compose export the env). Use `CLOUDFLARE_API_BASE=http://127.0.0.1:9999/ai/run` to point at a mock server during tests.

**VPS / remote deployments:** Store the same variables in `env.shared` (synced via `python3 -m pmoves.tools.secrets_sync generate`) and export them to your secrets manager (Fly.io, Coolify, Docker Swarm). Add the helper comment to `.env` so operators know the OpenAI shim base value: `OPENAI_API_BASE=https://api.cloudflare.com/client/v4/accounts/${CLOUDFLARE_ACCOUNT_ID}/ai`.
