# Publisher Service

The publisher service listens for `content.publish.approved.v1` events, downloads the
referenced artifact from MinIO, refreshes Jellyfin so new media appears in the
library, and publishes a `content.published.v1` envelope to NATS.

## Event Flow

1. Consume `content.publish.approved.v1`.
2. Fetch the artifact from MinIO (respecting retry + backoff settings).
3. Store the file under `MEDIA_LIBRARY_PATH`, deriving a namespace folder and
   slugged filename.
4. Trigger a Jellyfin library refresh so the asset surfaces in user facing
   clients.
5. Publish `content.published.v1` with metadata, enriched Jellyfin links,
   thumbnail URL, duration, optional Jellyfin item id, and public download URL.
6. Emit `content.publish.failed.v1` whenever a dependency error prevents
   completion (download failures, Jellyfin errors, rollup persistence issues).

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `NATS_URL` | `nats://nats:4222` | NATS broker connection string. |
| `MINIO_ENDPOINT` | `minio:9000` | MinIO host:port. |
| `MINIO_USE_SSL` | `false` | Whether to talk to MinIO over HTTPS. |
| `MINIO_ACCESS_KEY` | `pmoves` | MinIO access key. |
| `MINIO_SECRET_KEY` | `password` | MinIO secret key. |
| `MEDIA_LIBRARY_PATH` | `/library/images` | Root directory for downloaded media. |
| `MEDIA_LIBRARY_PUBLIC_BASE_URL` | unset | Optional HTTP base used to produce public URLs in publish events. |
| `JELLYFIN_URL` | `http://jellyfin:8096` | Jellyfin base URL for direct refreshes (use your Tailscale URL if you want refresh calls to hit that endpoint). |
| `JELLYFIN_API_KEY` | unset | API token for Jellyfin REST calls. |
| `JELLYFIN_USER_ID` | unset | Optional user for item lookups. |
| `JELLYFIN_PUBLIC_BASE_URL` | `JELLYFIN_URL` | Alternate public Jellyfin base for share links (set to `http://localhost:8096` or your Tailscale HTTPS URL for deep links). |
| `JELLYFIN_REFRESH_WEBHOOK_URL` | unset | When set, triggers a POST instead of calling Jellyfin directly. |
| `JELLYFIN_REFRESH_WEBHOOK_TOKEN` | unset | Optional bearer token included with webhook POSTs. |
| `JELLYFIN_REFRESH_DELAY_SEC` | `0` | Optional delay before refresh/webhook execution (seconds). |
| `PUBLISHER_DOWNLOAD_RETRIES` | `3` | Artifact download retry count. |
| `PUBLISHER_DOWNLOAD_RETRY_BACKOFF` | `1.5` | Seconds added per retry attempt. |
| `PUBLISHER_METRICS_HOST` | `0.0.0.0` | Bind address for the lightweight `/metrics` endpoint. |
| `PUBLISHER_METRICS_PORT` | `9095` | TCP port for the `/metrics` endpoint. |
| `PUBLISHER_METRICS_TABLE` | `publisher_metrics_rollup` | Supabase table used to persist publish rollups. |
| `PUBLISHER_METRICS_CONFLICT` | `artifact_uri` | Optional Supabase `on_conflict` key when upserting rollups. |

### Refresh Strategies

**Direct Jellyfin refresh (default)**

Leave `JELLYFIN_REFRESH_WEBHOOK_URL` unset to POST directly to Jellyfin's
`/Library/Refresh` endpoint immediately after the download completes. This
mirrors the previous behaviour and provides the fastest turn-around for smaller
libraries.

**Webhook mode**

Provide a `JELLYFIN_REFRESH_WEBHOOK_URL` when Jellyfin refreshes are scheduled
through an external automation runner or when the built-in `/Library/Refresh`
call is too heavy to execute for each asset. The publisher will:

1. Wait for `JELLYFIN_REFRESH_DELAY_SEC` (if non-zero) to accumulate multiple
   publish events.
2. POST `{ "title": ..., "namespace": ... }` to the configured webhook, adding
   an `Authorization: Bearer <JELLYFIN_REFRESH_WEBHOOK_TOKEN>` header when the
   token is supplied.
3. Resolve the Jellyfin item id and share URL so downstream consumers still
   receive enriched metadata.

The webhook endpoint can enqueue a cron job, trigger a Jellyfin API task, or fan
out to additional workflows. Non-2xx responses raise a
`JellyfinRefreshError` and surface in the service logs with the failing URL.

## Metrics & Logging

`PublisherMetrics` now records turnaround time, approval-to-publish latency,
downstream engagement proxies (e.g. views, click-through rates), and cost
drivers surfaced in approval metadata. The running summary is exposed via
`GET /metrics` on the configured host/port and is also embedded in the
`Published content` log line. Every publish emits a rollup row to Supabase
(`publisher_metrics_rollup` by default) so ROI dashboards can chart trends
without scraping logs.

When a dependency fails, the service emits structured failure envelopes:

- **`content.publish.failed.v1`** – includes the failing stage, retryable flag,
  captured context (`details`), and normalized metadata. Fatal errors surface
  when validation/downloading/rollup emit unrecoverable faults; partial errors
  (e.g. Jellyfin refresh warnings) are emitted with `outcome: "partial"` so
  downstream automation can alert without stopping the pipeline.
- Actionable log lines now include HTTP status codes, response bodies (truncated
  to 256 bytes), and the affected namespace/artifact identifiers.

### ROI Dashboards

Supabase rollups persist the following keys for downstream analytics:

- `turnaround_seconds` – time from ingest/submission until publish.
- `approval_latency_seconds` – lag between approval and publication.
- `engagement` – JSON map of numeric engagement metrics (views, CTR, etc.).
- `cost` – JSON map of cost drivers (processing minutes, storage/egress).

Dashboards can derive ROI by correlating engagement totals with cost totals for
each artifact, aggregated by namespace. Average turnaround and approval latency
highlight operational friction; spikes should trigger reviews of automation
queues or manual approval load.

See `pmoves/docs/TELEMETRY_ROI.md` for step-by-step guidance on charting the
rollup tables and pairing them with Discord delivery telemetry.

## Jellyfin Credential Smoke

Before relying on the publisher, validate that the Jellyfin URL, API key, and
optional user ID are correct:

```bash
cd pmoves
# Internal compose network (default)
JELLYFIN_URL=http://jellyfin:8096 \
JELLYFIN_API_KEY=<your-token> \
JELLYFIN_USER_ID=<optional-user> \
make jellyfin-verify

# Example: verify the Tailscale-exposed endpoint instead
JELLYFIN_URL=https://media.yourtailname.ts.net \
JELLYFIN_API_KEY=<same-token> \
JELLYFIN_USER_ID=<optional-user> \
make jellyfin-verify
```

The helper script hits `/System/Info`, checks the server branding (defaults to
`PMOVES Jellyfin`), and, when `JELLYFIN_USER_ID` is provided, enumerates user
libraries. Fix any reported errors before running end-to-end publisher smokes.

## Optional Jellyfin AI Stack

The repository ships an overlay compose file (`docker-compose.jellyfin-ai.yml`)
that brings up a Jellyfin media server together with the audio analysis stack
from `CATACLYSM_STUDIOS_INC/PMOVES-PROVISIONS`. To launch it alongside the
core PMOVES services:

```bash
cd pmoves
make up-jellyfin-ai
```

The make target wires the services onto the shared `pmoves-net` network and
creates data directories under `jellyfin-ai/` by default (override with
`JELLYFIN_AI_BASE=...` if you prefer a different location). Adjust the published ports
with `JELLYFIN_HTTP_PORT`, `JELLYFIN_API_PORT`, and `JELLYFIN_DASHBOARD_PORT` if
the defaults collide with existing services.

## Local Smoke Test

1. Ensure the PMOVES stack is running (`make up`).
2. Publish a demo event via `make smoke` or send a
   `content.publish.approved.v1` envelope manually to NATS.
3. Watch `docker compose logs -f publisher` for the `Published content` entry and
   confirm the asset appears inside Jellyfin after the configured refresh delay
   or webhook completes.
