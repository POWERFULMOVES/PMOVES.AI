# PMOVES.YT — Ingest + CGP Publisher

YouTube ingest helper that emits CHIT geometry after analysis.

## Service & Ports
- Compose service: `pmoves-yt`
- Starts with `make up-yt` (brings up `ffmpeg-whisper` too)

## Geometry Bus (CHIT) Integration
- Publishes `geometry.cgp.v1` to the Hi‑RAG gateway:
  - Endpoint: `POST ${HIRAG_URL}/geometry/event`
- Environment:
  - `HIRAG_URL` — base URL for the geometry gateway (`http://localhost:8086` by default)

## Smoke
- See `pmoves/services/pmoves-yt/tests/test_emit.py` for the CGP emission assertion.
- Run the main smokes in `pmoves/docs/SMOKETESTS.md` after `make up`.

## Testing
- Unit suite: `python -m pytest pmoves/services/pmoves-yt/tests`
- Async playlist pacing coverage (`tests/test_rate_limit.py::test_playlist_rate_limit_sleep`) now relies on `pytest-asyncio` for event loop orchestration. The dependency ships in `services/pmoves-yt/requirements.txt`, so re-run `python -m pip install -r services/pmoves-yt/requirements.txt` after pulling this change to keep the test harness green.
- Offline bundle refresh: `make vendor-httpx` (requires [uv](https://github.com/astral-sh/uv)) rebuilds `pmoves/vendor/python/` so helper scripts like `pmoves/scripts/backfill_jellyfin_metadata.py` can import `httpx` without pip.

## Resilient Playlist Ingest (2025-10)
- `/yt/playlist` now runs downloads concurrently (bounded by `YT_CONCURRENCY`) with
  an async worker pool and coordinated rate limiting (`YT_RATE_LIMIT`).
- Transient errors (network, 5xx, yt-dlp hiccups) retry with exponential backoff
  up to `YT_RETRY_MAX` attempts; state updates live in Supabase (`yt_items`).
- Downloads resume automatically thanks to a persistent scratch directory
  (`YT_TEMP_ROOT`, default `/tmp/pmoves-yt`). Successful ingests clean the cache;
  failures leave partial files to resume on the next run.
- Video metadata is enriched with duration, channel details, tags, statistics,
  and provenance (job id, timestamps) so downstream dashboards can render richer
  context without manual joins.
- Summaries/chapters emit `ingest.summary.ready.v1` / `ingest.chapters.ready.v1`
  events so downstream automations (Discord, n8n) can react in real time.

### yt-dlp configuration (2025-10)
- `yt-dlp[default]` + `curl-cffi` ship within the image; `ffmpeg` and `atomicparsley`
  are installed via apt so metadata/thumbnail embedding works out of the box.
- `YT_ARCHIVE_DIR` (default `/data/yt-dlp`) + `YT_ENABLE_DOWNLOAD_ARCHIVE=true`
  configure yt-dlp's archive file. Override per channel with
  `yt_options.download_archive` to dedupe imports per playlist.
- `YT_SUBTITLE_LANGS` (comma separated) `YT_SUBTITLE_AUTO` pull caption tracks;
  pass `yt_options.subtitle_langs` per channel to mix languages.
- `YT_WRITE_INFO_JSON` (default true) stores the `.info.json` artifact; disable
  with `yt_options.write_info_json=false` when not needed.
- `YT_POSTPROCESSORS_JSON` lets you override the default postprocessor list
  (`FFmpegMetadata` + `EmbedThumbnail`). Leave empty (`[]`) to skip embedding.
  Channel configs can set `yt_options.postprocessors` for one-off tweaks.

## Hi‑RAG upsert pacing (2025-10-24)
- `/yt/emit` switches to a background task when `YT_ASYNC_UPSERT_ENABLED=true` and the
  segmented chunk count ≥ `YT_ASYNC_UPSERT_MIN_CHUNKS` (defaults: enabled, 200 chunks).
  The API response returns `{"async": true, "job_id": "..."}`; poll
  `/yt/emit/status/{job_id}` for completion or failure details.
- `YT_INDEX_LEXICAL_DISABLE_THRESHOLD` (default `0`) disables the Meili/lexical index
  step automatically for very large transcripts so the request can return quickly.
- `YT_UPSERT_BATCH_SIZE` (default `200`) defines how many chunks each
  `/hirag/upsert-batch` call carries. Tune alongside the lexical threshold when
  dealing with hour-long transcripts.
