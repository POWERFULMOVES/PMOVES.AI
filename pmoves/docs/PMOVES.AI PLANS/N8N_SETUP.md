# n8n Setup Checklist (Supabase → Agent Zero → Discord)
_Last updated: 2025-12-14_

## Overview
This guide streamlines importing and running the PMOVES approval and publish workflows in n8n. It targets Supabase CLI on the host, Agent Zero + NATS in Docker, and Discord webhooks.

## Preflight (quick)
- Start stacks: `make up && make up-agents && make up-n8n`
- Run preflight: `make m2-preflight`
  - Confirms Agent Zero + publisher-discord health
  - Sends a Discord ping if `DISCORD_WEBHOOK_URL` is set

## Prerequisites
- Supabase CLI running locally: `supabase start` or `make supa-start`
- PMOVES stack up: `make up && make up-agents`
- n8n running:
  - Local/dev (SQLite): `make up-n8n` (UI at `http://localhost:5678`, launches `n8n` + `n8n-runners`)
  - VPS/prod (Postgres): `N8N_DB=postgres make up-n8n` (adds `n8n-db` Postgres for durable state)
- Secrets at hand: `SUPABASE_SERVICE_ROLE_KEY`, `DISCORD_WEBHOOK_URL`, `N8N_RUNNERS_AUTH_TOKEN`

## Environment (n8n)
Set these in n8n (Settings → Variables) or via container env:
- `SUPABASE_REST_URL` = `http://host.docker.internal:65421/rest/v1`
- `SUPABASE_SERVICE_ROLE_KEY` = `<your service role key>`
- `AGENT_ZERO_BASE_URL` = `http://agent-zero:8080`
- `AGENT_ZERO_EVENTS_TOKEN` = `<optional>`
- `DISCORD_WEBHOOK_URL` = `<your Discord webhook URL>`
- `DISCORD_WEBHOOK_USERNAME` = `PMOVES Publisher`
- `N8N_RUNNERS_AUTH_TOKEN` = `<shared secret – must match the sidecar>`
- `N8N_DEFAULT_TIMEZONE` = `America/New_York` (aligns cron schedules with project TZ)

### n8n persistence mode (SQLite vs Postgres)
By default, `make up-n8n` runs n8n with SQLite for quick local bring-up.

For VPS/production, run n8n on Postgres:
- Set `N8N_DB=postgres`
- Set `N8N_DB_NAME`, `N8N_DB_USER`, `N8N_DB_PASSWORD` (in `pmoves/env.shared` or injected secrets)
- Bring up: `N8N_DB=postgres make -C pmoves up-n8n`

This uses `pmoves/docker-compose.n8n.postgres.yml` to add a dedicated `n8n-db` container. It does **not** move your PMOVES app data into n8n — it only stores n8n’s own workflow/execution state in Postgres.

> **Supabase runtime note:** The CLI runtime binds REST on port `65421` per `supabase/config.toml`. If you switch back to the docker-compose PostgREST service, update `SUPABASE_REST_URL` accordingly (typically `http://host.docker.internal:54321/rest/v1`).

Tip: These defaults are prewired in `docker-compose.n8n.yml`. If you use `make up-n8n`, populate `SUPABASE_SERVICE_ROLE_KEY`, `DISCORD_WEBHOOK_URL`, and `N8N_RUNNERS_AUTH_TOKEN` in `pmoves/env.shared` or `pmoves/.env.local`. The runner token is loaded via `env_file` (not compose-time interpolation) so recreating containers won’t accidentally desync the broker and sidecar.

Note: n8n 1.115.3 already executes cron triggers in the main process. Avoid re-adding the deprecated `EXECUTIONS_PROCESS` flag—the service emits a warning and ignores it.

## Container Tooling
- The custom image defined in `compose/n8n/Dockerfile` bakes in the `sqlite3` CLI so DB inspections persist across restarts.
- Run `make up-n8n` after pulling updates to rebuild the service when the Dockerfile changes.

## Import Workflows
1. Open n8n → Workflows → Import from File.
2. Import the core approvals stack:
   - `pmoves/n8n/flows/approval_poller.json`
   - `pmoves/n8n/flows/echo_publisher.json`
3. Import the creative webhooks (requires ComfyUI hosts prepared via [`pmoves/creator/README.md`](../creator/README.md)):
   - `pmoves/n8n/flows/wan_to_cgp.webhook.json`
   - `pmoves/n8n/flows/qwen_to_cgp.webhook.json`
   - `pmoves/n8n/flows/vibevoice_to_cgp.webhook.json`
4. (Optional) Import the audio enrichment flows:
   - `pmoves/n8n/flows/vibevoice_audio_ingest.json`
   - `pmoves/n8n/flows/vibevoice_discord_preview.json`
5. Keep everything inactive until env is confirmed (Supabase keys, MinIO buckets, Discord webhooks).

## Validate Env Bindings
- Approval Poller
  - GET `{{$env.SUPABASE_REST_URL}}/studio_board`
  - Headers: `apikey` and `Authorization: Bearer {{$env.SUPABASE_SERVICE_ROLE_KEY}}`
  - POST `{{$env.AGENT_ZERO_BASE_URL}}/events/publish` (header `x-agent-token` if used)
- Echo Publisher
  - Discord URL: `{{$env.DISCORD_WEBHOOK_URL}}`
  - Username: `{{$env.DISCORD_WEBHOOK_USERNAME}}`

## Activation & Test
1. Health checks
   - `make health-agent-zero`
   - `make health-publisher-discord`
2. Discord ping
   - `make discord-ping MSG="PMOVES Discord wiring check"`
3. Seed Supabase (approved row)
   - Bash: `make seed-approval TITLE="Demo" URL="s3://outputs/demo/example.png"`
   - PowerShell: `make seed-approval-ps TITLE="Demo" URL="s3://outputs/demo/example.png"`
4. Activate poller → confirm Agent Zero receives `content.publish.approved.v1`
5. Activate echo publisher → confirm Discord embed (title/link/thumbnail if provided)
6. Optional: Post directly to n8n webhook (flow must be active)
   - `make n8n-webhook-demo`

### Voice platform flows (Discord/Telegram)
The repo includes optional chat-platform voice agent flows (Discord/Telegram) that require additional credentials and/or custom n8n nodes.

To keep the stack green by default, `make -C pmoves n8n-activate-flows` disables these unless you opt in:
- Enable chat-platform voice flows: `VOICE_PLATFORMS=1 make -C pmoves n8n-activate-flows`

## VibeVoice / RVC Audio Capture
These flows extend the core approval automations so we can surface RVC voice outputs produced by the VibeVoice toolchain.

### Flow Overview
- **`vibevoice_audio_ingest`** — Watches the Supabase `studio_board` table for rows containing `voice_job_id` metadata published by VibeVoice exports. The flow retrieves the render payload from Supabase storage, runs an `Execute Command` node with `ffmpeg` to normalize the audio (`.wav` → `.mp3`), and attaches duration/format metadata back onto the row so downstream services can consume it.
- **`vibevoice_discord_preview`** — Listens for the enriched payloads from the ingest flow, builds a Discord embed with audio stats, and publishes a short preview clip to the configured Discord voice webhook.

### Required Environment Variables
- `SUPABASE_STORAGE_AUDIO_BUCKET` — Bucket that receives the raw RVC renders.
- `VIBEVOICE_STORAGE_SERVICE_ROLE_KEY` — Service key the ingest flow uses to fetch protected audio.
- `DISCORD_VOICE_WEBHOOK_URL` — Webhook that accepts voice previews (separate from the text embed webhook).
- `DISCORD_VOICE_WEBHOOK_USERNAME` — Optional override for the preview sender name.
- `N8N_FFMPEG_PATH` — (optional) Absolute path to `ffmpeg` inside the n8n container. Defaults to `ffmpeg` if unset.

### FFmpeg Notes
- `make up-n8n` mounts `ffmpeg` into the container by default. If you customized the image, exec into the container and run `ffmpeg -version` to confirm availability.
- If the binary is missing, install it (`apk add ffmpeg` for Alpine-based images) and set `N8N_FFMPEG_PATH=/usr/bin/ffmpeg`.

### Supabase Seeding Helpers
- `make seed-audio-preview TITLE="Demo voice" AUDIO_URL="s3://outputs/demo/voice.wav" JOB_ID="vv-job-123"`
  - Seeds `studio_board` with the audio metadata expected by the ingest flow.
- `make seed-audio-preview-ps ...` (PowerShell variant) mirrors the same payload for Windows operators.

### Discord Validation
- Trigger `vibevoice_discord_preview` manually in n8n once a seeded row exists.
- Confirm the webhook posts an embed with duration + sample rate and attaches the transcoded `.mp3`.

### Troubleshooting
- FFmpeg failures → confirm the binary path and that the container user has execute permissions.
- Supabase 401 → ensure the audio bucket policies allow service role access and that the correct key is in `VIBEVOICE_STORAGE_SERVICE_ROLE_KEY`.
- Discord voice webhook rejects upload → verify the webhook is configured for voice messages and the payload size is under 25 MB.

## Troubleshooting
- 404 from Supabase in n8n: ensure `/rest/v1` is included in `SUPABASE_REST_URL`.
- 503 from Agent Zero: confirm NATS + Agent Zero are running (`make up-agents`).
- Discord no messages: verify `DISCORD_WEBHOOK_URL` and check rate limits in n8n logs.
- n8n cannot reach host services on Linux: replace `host.docker.internal` with the host IP or Docker gateway (`172.17.0.1`).
- Cron schedule idle: confirm `workflow_entity.staticData` populates after activation. If it stays `null`, the scheduler is not persisting its next run; double-check `N8N_DEFAULT_TIMEZONE` and inspect `wait-tracker` logs for scheduler errors.
- Creative webhooks return 401/404: confirm you are POSTing to `http://localhost:5678/webhook/<workflowId>/webhook/<slug>` and that the ComfyUI workstation followed the one-click installer steps in [`pmoves/creator/README.md`](../creator/README.md) (MinIO creds, model downloads, FFmpeg for audio).

## Related
- Playbook: `SUPABASE_DISCORD_AUTOMATION.md`
- Local dev: `LOCAL_DEV.md`
- Next steps: `NEXT_STEPS.md`
