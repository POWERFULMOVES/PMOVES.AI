# LangExtract (XML → JSONL for Hi‑RAG)

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
If a provider is not configured or fails, prefer `rule` for offline local use.
