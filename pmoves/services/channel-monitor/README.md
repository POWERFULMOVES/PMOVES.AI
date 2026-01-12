## PMOVES Channel Monitor

Automates discovery of new YouTube videos from configured channels and queues them for ingestion via `pmoves-yt`.

### Environment

| Variable | Description | Default |
| --- | --- | --- |
| `CHANNEL_MONITOR_CONFIG_PATH` | Path to JSON config file. | `/app/config/channel_monitor.json` |
| `CHANNEL_MONITOR_QUEUE_URL` | Endpoint that receives discovered URLs (typically pmoves-yt `/yt/ingest`). | `http://pmoves-yt:8077/yt/ingest` |
| `CHANNEL_MONITOR_DATABASE_URL` | Postgres connection string used for persistence. | `postgresql://pmoves:pmoves@postgres:5432/pmoves` |
| `CHANNEL_MONITOR_NAMESPACE` | Default namespace applied when queuing videos. | `pmoves` |
| `CHANNEL_MONITOR_SECRET` | Optional shared secret required by `/api/monitor/status` updates. | _(unset)_ |

### Commands

Run locally via Docker:

```bash
docker compose -p pmoves --profile channel-monitor up -d channel-monitor
```

Manual check:

```bash
curl -X POST http://localhost:8097/api/monitor/check-now
```

### Configuration

The service maintains a JSON config at `CHANNEL_MONITOR_CONFIG_PATH`. If the file does not exist it is created using sensible defaults. Channels can be appended by editing the file or via `POST /api/monitor/channel`:

```bash
curl -X POST http://localhost:8097/api/monitor/channel \
  -H 'content-type: application/json' \
  -d '{"channel_id":"UCabc123xyz","channel_name":"Example Channel","auto_process":true}'
```

`yt_options` blocks (global or per-channel) are forwarded to pmoves-yt, letting you tune yt-dlp behaviour without rebuilding containers. Example knobs:

- `download_archive`: absolute path to the archive file so yt-dlp skips previously ingested videos.
- `subtitle_langs`: list of language codes to pull caption tracks (e.g. `["en", "es"]`).
- `postprocessors`: override yt-dlp post-processing chain; defaults embed thumbnails + metadata.
- `write_info_json`: emit `.info.json` alongside downloads for downstream RAG enrichment.

#### Metadata profiles

Global defaults live under `global_settings.channel_metadata_fields` and
`global_settings.video_metadata_fields`. The lists control which attributes are
captured for each discovered item and mirrored into the `metadata` JSONB column
as well as the payload sent to `pmoves-yt`.

- Channel fields include identifiers, canonical URLs, namespace/tags, priority,
  thumbnail, and subscriber counts. The defaults surface all of these so the
`/api/monitor/stats` endpoint reports per-channel health (aggregated counters, recent activity). For lightweight monitoring probes, `GET /api/monitor/status` returns `{ "status": "ok" }` without requiring a secret, while `POST /api/monitor/status` remains the authenticated status update hook used by downstream services.
- Video fields include duration, view/like counts, best thumbnail, publish
  timestamps, categories, and tags.

Override the defaults per-channel by setting `channel_metadata_fields` or
`video_metadata_fields` on the channel entry (or via the `POST
/api/monitor/channel` payload). The monitor only persists the requested keys,
keeping metadata lean for sources that do not need the full profile.

`global_settings.channel_breakdown_limit` controls how many channels are
returned by `/api/monitor/stats` in the aggregated breakdown (default 25).

CLI helper (writes to the active config path):

```bash
python -m pmoves.tools.register_media_source \
  --platform youtube \
  --source-type playlist \
  --name "DARKSXIDE Mix Series" \
  --url "https://www.youtube.com/playlist?list=PLGupOT04oMfok7S8W8Js7lZZIlhM8ufc8" \
  --namespace pmoves.darkxside \
  --tags "darkxside,mix" \
  --yt-options '{"download_archive": "/data/yt-dlp/darkxside/mixseries.archive"}'
```

### Persistence

Discovered videos are stored in `pmoves.channel_monitoring` with status flags (`pending`, `processing`, `queued`, `completed`, `failed`). The service records each transition timestamp inside the row metadata so operations can audit ingestion attempts. The `pmoves/supabase/initdb/14_channel_monitoring.sql` migration creates the table and indexes for Supabase/Postgres environments.

To close the loop, downstream services (e.g. pmoves-yt) can acknowledge ingestion outcomes via:

```bash
curl -X POST http://localhost:8097/api/monitor/status \
  -H 'content-type: application/json' \
  -H 'x-channel-monitor-token: $CHANNEL_MONITOR_SECRET' \
  -d '{"video_id":"abc123","status":"completed","metadata":{"ingest":{"source":"pmoves-yt"}}}'
```

Accepted statuses: `pending`, `processing`, `queued`, `completed`, `failed`.

### Observability

`GET /api/monitor/stats` now returns:

- `summary`: global totals plus the first/last discovery timestamps (UTC ISO
  strings).
- `recent`: the ten most recent discoveries including channel ID, URLs, and
  thumbnails.
- `channels`: aggregated metrics per monitored channel (counts by status,
  namespace, tags, last discovery/publish timestamps, subscriber counts, and
  thumbnail/URL hints).

Use the channel breakdown to spot stalled sources (e.g. increasing `pending`
counts or repeated failures) and to confirm branding metadata is being
populated as expected.
