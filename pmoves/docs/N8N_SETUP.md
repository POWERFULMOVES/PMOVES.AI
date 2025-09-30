# n8n Setup Checklist (Supabase → Agent Zero → Discord)
_Last updated: 2025-09-30_

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
- n8n running: `make up-n8n` (UI at `http://localhost:5678`)
- Secrets at hand: `SUPABASE_SERVICE_ROLE_KEY`, `DISCORD_WEBHOOK_URL`

## Environment (n8n)
Set these in n8n (Settings → Variables) or via container env:
- `SUPABASE_REST_URL` = `http://host.docker.internal:54321/rest/v1`
- `SUPABASE_SERVICE_ROLE_KEY` = `<your service role key>`
- `AGENT_ZERO_BASE_URL` = `http://agent-zero:8080`
- `AGENT_ZERO_EVENTS_TOKEN` = `<optional>`
- `DISCORD_WEBHOOK_URL` = `<your Discord webhook URL>`
- `DISCORD_WEBHOOK_USERNAME` = `PMOVES Publisher`

Tip: These defaults are prewired in `docker-compose.n8n.yml`. If you use the Make target `make up-n8n`, only the two secrets are required.

## Import Workflows
1. Open n8n → Workflows → Import from File
2. Import both files:
   - `pmoves/n8n/flows/approval_poller.json`
   - `pmoves/n8n/flows/echo_publisher.json`
3. Keep both inactive until env is confirmed.

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

## Troubleshooting
- 404 from Supabase in n8n: ensure `/rest/v1` is included in `SUPABASE_REST_URL`.
- 503 from Agent Zero: confirm NATS + Agent Zero are running (`make up-agents`).
- Discord no messages: verify `DISCORD_WEBHOOK_URL` and check rate limits in n8n logs.
- n8n cannot reach host services on Linux: replace `host.docker.internal` with the host IP or Docker gateway (`172.17.0.1`).

## Related
- Playbook: `SUPABASE_DISCORD_AUTOMATION.md`
- Local dev: `LOCAL_DEV.md`
- Next steps: `NEXT_STEPS.md`
