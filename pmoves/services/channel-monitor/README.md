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
