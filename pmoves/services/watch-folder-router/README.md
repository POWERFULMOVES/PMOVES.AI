# watch-folder-router

**SEAP ingestion Bud 1** (see `SEAP_WATCHFOLDER_NATS_CONSTELLATION_2026-08-12`).
The auto-router that makes the watch folder real: it turns "a file landed in
MinIO" into "the right analyzer ran and the right downstream subject fired,"
retiring the manual `media-audio /analyze` calls that every hand-driven ingest
used to make.

## Role

- **Port:** `:8125` (health/metrics only; the work is NATS-driven, no client HTTP)
- **Subscribes:** `ingest.file.added.v1`
- **Publishes (by MIME):**
  - `audio/*`, `video/*` → `media-audio /analyze` (transcription) → `ingest.transcript.ready.v1`
  - `application/pdf` + office docs → `ingest.document.ready.v1` (pdf-ingest / langextract consume)
  - everything else → `ingest.text.ready.v1` (extract-worker embeds)

MIME is trusted first; when it's generic (`application/octet-stream`) the file
extension is the fallback classifier.

## Why it exists

The ingest subjects existed but nothing auto-wired `ingest.file.added.v1` to an
analyzer — so every ingest went through a hand-driven script. This service is
the smallest, highest-leverage node in the constellation: drop a file in the
watch folder (MinIO), get automatic analysis.

## Upstream (who emits `ingest.file.added.v1`)

- **[drop-folder-ingest](../drop-folder-ingest/README.md)**: host drop folder ->
  MinIO -> `ingest.file.added.v1`. The operator-facing way in: drop any file in
  the folder and it routes here.
- a2ui-renderer and pdf-ingest also publish the subject; their payloads carry no
  `bucket`/`key`, so the router rejects them (pdf-ingest has already processed
  and announced its document itself).

Both the standard envelope (`{id, topic, ts, version, source, payload}`) and the
legacy flat shape are accepted: fields are read from `payload` when present.

## Downstream (the rest of the constellation — not this service)

- **transcript-harvester** (Bud 2, not yet built): consume the `*.ready.v1`
  family → Hi-RAG + Open Notebook + JuiceFS + CGP.
- **archon-harvest** (Bud 3, not yet built): decide what deserves an Archon
  work order.

## Env

| Var | Default | Purpose |
|-----|---------|---------|
| `NATS_URL` | `nats://nats:4222` | bus |
| `MEDIA_AUDIO_URL` | `http://media-audio:8082` | transcription analyzer |
| `ROUTER_TRANSCRIBE_TIMEOUT_SEC` | `3600` | media-audio call timeout |

## Envelope

Publishes the PMOVES standard envelope: `{topic, payload, correlation_id,
source: "watch-folder-router", ts}`. `correlation_id` carries the source
`file_id` so the constellation can trace an artifact end-to-end.
