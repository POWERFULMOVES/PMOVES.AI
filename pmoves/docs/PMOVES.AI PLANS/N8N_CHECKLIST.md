# n8n Flow Import + Env (Quick Checklist)
_Copy-paste friendly for internal wiki_

- Start services
  - `make up && make up-agents && make up-n8n`
  - Preflight: `make m2-preflight`

- n8n UI at `http://localhost:5678`
- Import flows
  - Core → `pmoves/n8n/flows/approval_poller.json`, `pmoves/n8n/flows/echo_publisher.json`
  - Audio → `pmoves/n8n/flows/vibevoice_audio_ingest.json`, `pmoves/n8n/flows/vibevoice_discord_preview.json`
  - Health/Finance → drop JSON exports into `pmoves/integrations/health-wger/n8n/flows/` and
    `pmoves/integrations/firefly-iii/n8n/flows/`; run `make integrations-up-all` for the watcher auto-import or
    `make integrations-import-flows` to sync once via REST.
  - Ensure Variables:
    - `SUPABASE_REST_URL=http://host.docker.internal:65421/rest/v1`
    - `SUPABASE_SERVICE_ROLE_KEY=<service_role_key>`
    - `AGENT_ZERO_BASE_URL=http://agent-zero:8080`
    - `AGENT_ZERO_EVENTS_TOKEN` (optional)
    - `DISCORD_WEBHOOK_URL=<webhook>`
    - `DISCORD_WEBHOOK_USERNAME=PMOVES Publisher`
  - `N8N_DEFAULT_TIMEZONE=America/New_York`
  - `N8N_RUNNERS_AUTH_TOKEN=<shared secret>`

- Seed approval row
  - `make seed-approval TITLE="Demo" URL="s3://outputs/demo/example.png"`
- Seed audio preview row
  - `make seed-audio-preview TITLE="Demo voice" AUDIO_URL="s3://outputs/demo/voice.wav" JOB_ID="vv-job-123"`

- Activate
  - Enable approval_poller → verify event in Agent Zero
  - Enable echo_publisher → verify Discord embed
  - Enable vibevoice_audio_ingest → verify Supabase row is enriched + audio transcoded
  - Enable vibevoice_discord_preview → verify Discord voice webhook receives preview clip

- FFmpeg check inside n8n container
  - `docker compose exec n8n ffmpeg -version`
  - If missing, install ffmpeg and set `N8N_FFMPEG_PATH`

- Troubleshooting
  - 404 from Supabase → make sure `/rest/v1` is in `SUPABASE_REST_URL`
  - 503 from Agent Zero → ensure `make up-agents` ran (NATS + Agent Zero)
  - No Discord embed → verify webhook URL and rate limits

- Persistence mode (VPS/prod)
  - Use Postgres for n8n: `N8N_DB=postgres make -C pmoves up-n8n`
  - Required envs: `N8N_DB_NAME`, `N8N_DB_USER`, `N8N_DB_PASSWORD`
