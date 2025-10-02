# n8n Flow Import + Env (Quick Checklist)
_Copy-paste friendly for internal wiki_

- Start services
  - `make up && make up-agents && make up-n8n`
  - Preflight: `make m2-preflight`

- n8n UI at `http://localhost:5678`
  - Import flows → `pmoves/n8n/flows/approval_poller.json` and `echo_publisher.json`
  - Ensure Variables:
    - `SUPABASE_REST_URL=http://host.docker.internal:54321/rest/v1`
    - `SUPABASE_SERVICE_ROLE_KEY=<service_role_key>`
    - `AGENT_ZERO_BASE_URL=http://agent-zero:8080`
    - `AGENT_ZERO_EVENTS_TOKEN` (optional)
    - `DISCORD_WEBHOOK_URL=<webhook>`
    - `DISCORD_WEBHOOK_USERNAME=PMOVES Publisher`

- Seed approval row
  - `make seed-approval TITLE="Demo" URL="s3://outputs/demo/example.png"`

- Activate
  - Enable approval_poller → verify event in Agent Zero
  - Enable echo_publisher → verify Discord embed

- Troubleshooting
  - 404 from Supabase → make sure `/rest/v1` is in `SUPABASE_REST_URL`
  - 503 from Agent Zero → ensure `make up-agents` ran (NATS + Agent Zero)
  - No Discord embed → verify webhook URL and rate limits

