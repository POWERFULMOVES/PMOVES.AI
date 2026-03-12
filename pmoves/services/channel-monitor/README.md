## PMOVES Channel Monitor

Automates discovery of new YouTube videos from configured channels and queues them for ingestion via `pmoves-yt`.

Current production fetch order:
- YouTube Data API with Google OAuth refresh tokens when available
- yt-dlp flat extraction / RSS fallback when API auth is unavailable or source coverage requires it
- queue handoff to the authoritative `PMOVES.YT` runtime at `/yt/ingest`

### Environment

| Variable | Description | Default |
| --- | --- | --- |
| `CHANNEL_MONITOR_CONFIG_PATH` | Path to JSON config file. | `/app/config/channel_monitor.json` |
| `CHANNEL_MONITOR_QUEUE_URL` | Endpoint that receives discovered URLs (typically pmoves-yt `/yt/ingest`). | `http://pmoves-yt:8077/yt/ingest` |
| `CHANNEL_MONITOR_DATABASE_URL` | Postgres connection string used for persistence. | `postgresql://pmoves:pmoves@postgres:5432/pmoves` |
| `CHANNEL_MONITOR_NAMESPACE` | Default namespace applied when queuing videos. | `pmoves` |
| `CHANNEL_MONITOR_GOOGLE_CLIENT_ID` | Google OAuth client id for YouTube Data API access. | _(unset)_ |
| `CHANNEL_MONITOR_GOOGLE_CLIENT_SECRET` | Google OAuth client secret for token refresh. | _(unset)_ |
| `CHANNEL_MONITOR_GOOGLE_REDIRECT_URI` | OAuth redirect URI served by channel-monitor. | `http://localhost:8097/api/oauth/google/callback` |
| `CHANNEL_MONITOR_GOOGLE_SCOPES` | OAuth scopes used for YouTube access. | `https://www.googleapis.com/auth/youtube.readonly` |
| `CHANNEL_MONITOR_SECRET` | Optional shared secret required by protected write endpoints (`/api/monitor/status`, `/api/monitor/discord-drop`). | _(unset)_ |
| `CHANNEL_MONITOR_DISCORD_APPROVAL_MODE` | Default Discord intake mode (`ask` or `auto`). | `ask` |

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
  -d '{"channel_id":"UCabc123xyz","channel_name":"Example Channel","source_class":"watched","auto_process":true}'
```

`source_class` is the operator-intent class for a source:
- `owned` — PMOVES-managed channels or playlists
- `partner` — explicit collaborator or shared-lane sources
- `watched` — monitored third-party creators
- `candidate` — scout/review sources that should stay gated by default

If omitted, configured channels default to `watched` and Discord/manual drops default to `candidate`.

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

### Discord Video Drop Intake

Use this endpoint when a Discord bot/agent sees message links and should push
them into PMOVES.YT immediately:

```bash
curl -X POST http://localhost:8097/api/monitor/discord-drop \
  -H 'content-type: application/json' \
  -H 'x-channel-monitor-token: $CHANNEL_MONITOR_SECRET' \
  -d '{
    "content": "check this https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "approval_mode": "ask",
    "guild_id": "1234567890",
    "channel_id": "9876543210",
    "message_id": "1122334455",
    "author_id": "9988776655",
    "namespace": "pmoves",
    "tags": ["discord", "drop", "review"],
    "source": "discord_agent"
  }'
```

The monitor will:
- extract and deduplicate URLs from `urls[]` and/or `content`
- persist synthetic tracking rows in `pmoves.channel_monitoring`
- in `auto` mode: queue each URL to `CHANNEL_MONITOR_QUEUE_URL` (`/yt/ingest` by default)
- in `ask` mode: store rows as `pending` and wait for explicit review
- propagate Discord context metadata so downstream events can fan out to
  `publisher-discord` and Open Notebook flows

Approve/reject pending rows (gated review):

```bash
curl -X GET "http://localhost:8097/api/monitor/discord-drop/pending?source=discord_agent" \
  -H 'x-channel-monitor-token: $CHANNEL_MONITOR_SECRET'

curl -X POST http://localhost:8097/api/monitor/discord-drop/approve \
  -H 'content-type: application/json' \
  -H 'x-channel-monitor-token: $CHANNEL_MONITOR_SECRET' \
  -d '{"video_ids":["dQw4w9WgXcQ"],"approve":true,"actor":"discord-agent"}'
```

Queue/review owned-channel PMOVES.YT control actions:

```bash
curl -X POST http://localhost:8097/api/monitor/youtube-control \
  -H 'content-type: application/json' \
  -H 'x-channel-monitor-token: $CHANNEL_MONITOR_SECRET' \
  -d '{
    "action": "playlist_add",
    "details": {
      "playlist_id": "PL123",
      "video_id": "dQw4w9WgXcQ"
    },
    "request_source": "discord_agent"
  }'

curl -X GET "http://localhost:8097/api/monitor/youtube-control/pending" \
  -H 'x-channel-monitor-token: $CHANNEL_MONITOR_SECRET'

curl -X POST http://localhost:8097/api/monitor/youtube-control/review \
  -H 'content-type: application/json' \
  -H 'x-channel-monitor-token: $CHANNEL_MONITOR_SECRET' \
  -d '{"action_ids":["11111111-1111-1111-1111-111111111111"],"approve":true,"actor":"discord-agent"}'
```

Set `CHANNEL_MONITOR_YT_API_KEY` when PMOVES.YT control endpoints require `X-API-Key`.

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
