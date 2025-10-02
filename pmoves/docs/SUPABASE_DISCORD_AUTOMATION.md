# Supabase → Agent Zero → Discord Automation Playbook
_Last updated: 2025-10-01_

This guide captures the concrete steps and validation checks for wiring the M2 "Creator & Publishing" automation path end to end. It augments the high-level context in `pmoves/docs/CREATOR_PIPELINE.md` and the operational checklist in `pmoves/docs/NEXT_STEPS.md` with implementation-ready instructions.

## Overview
The goal is to fan out `studio_board` approvals into Discord notifications with rich embeds while keeping Supabase as the system of record. The automation relies on three cooperating components:

1. **Supabase PostgREST** — exposes `studio_board` for polling updates and persisting publish audit data.
2. **Agent Zero** — provides the `/events/publish` endpoint that accepts approved content events.
3. **n8n workflows** — orchestrate the polling of Supabase, publishing into Agent Zero, and forwarding final `content.published.v1` envelopes to Discord.

## Prerequisites
- Supabase stack running locally (`make up data` or equivalent) with the `studio_board` table migrated.
- Agent Zero service reachable (default `http://agent-zero:8080`).
- Discord webhook configured for the destination channel (create via *Server Settings → Integrations → Webhooks*).
- n8n instance with access to the above services (Docker profile `orchestration`).

## Environment Variables
Populate the following entries in `.env` (see `.env.example` for placement). Restart docker-compose services after changes.

```
# Supabase
SUPABASE_REST_URL=http://localhost:3000
SUPABASE_SERVICE_ROLE_KEY=<service-role-key>

# Agent Zero
AGENT_ZERO_BASE_URL=http://agent-zero:8080
AGENT_ZERO_EVENTS_TOKEN=<optional-shared-secret>

# Discord
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/.../...
DISCORD_WEBHOOK_USERNAME=PMOVES Publisher
```

### Env alignment notes
- Both `SUPA_REST_URL` and `SUPABASE_REST_URL` are now supported for local development. Compose services use `SUPA_REST_URL`; n8n flows reference `SUPABASE_REST_URL`. The example `.env` defines both and points them at `http://postgrest:3000`.
- Prefer `DISCORD_WEBHOOK_USERNAME` for webhook display name. `services/publisher-discord` also supports `DISCORD_USERNAME` for backward compatibility.

### Quick manual webhook ping
- Bash: `export DISCORD_WEBHOOK_URL=...; export DISCORD_WEBHOOK_USERNAME="PMOVES Publisher"; ./pmoves/scripts/discord_ping.sh "PMOVES Discord wiring check"`
- PowerShell: `setx DISCORD_WEBHOOK_URL "<url>"; setx DISCORD_WEBHOOK_USERNAME "PMOVES Publisher"; pwsh -File ./pmoves/scripts/discord_ping.ps1 -Message "PMOVES Discord wiring check"`

## Import & Configure n8n Workflows
1. In the n8n UI, import `pmoves/n8n/flows/approval_poller.json` and `pmoves/n8n/flows/echo_publisher.json` (see also `N8N_SETUP.md`).
2. Open **Credentials** and create the following entries:
   - `Supabase Service Role` — HTTP Basic auth with the service role key (username blank, password set to the key).
   - `Agent Zero Events` — HTTP Header Auth with `Authorization: Bearer <AGENT_ZERO_EVENTS_TOKEN>`.
   - `Discord Webhook` — HTTP Request node credential with the webhook URL.
3. Edit the imported workflows:
   - Set the Supabase node base URL to `${SUPABASE_REST_URL}`.
   - Inject `${DISCORD_WEBHOOK_URL}` and `${DISCORD_WEBHOOK_USERNAME}` via environment expressions (requires n8n `.env` update or credential usage).
   - Confirm polling cadence (default: every 60 seconds). Align with Supabase row update frequency.
4. Save and keep both workflows **inactive** until secrets are confirmed.

## Activation Checklist
Perform the following steps in order to validate the pipeline:

1. **Dry-run webhook ping**
   - Use `curl -H "Content-Type: application/json" -d '{"content":"PMOVES Discord wiring check"}' $DISCORD_WEBHOOK_URL`.
   - Confirm the Discord channel receives the message.
2. **Supabase approval trigger**

   - Use helper to insert an `approved` row with a valid `content_url`:
     - Make (Bash): `make -C pmoves seed-approval TITLE="Demo" URL="s3://outputs/demo/example.png"`
     - PowerShell: `make -C pmoves seed-approval-ps TITLE="Demo" URL="s3://outputs/demo/example.png"`
   - Ensure `meta->>'publish_event_sent_at'` is `null` prior to poller run (default when inserting with the helper).
3. **Enable `approval_poller` workflow**

   - Insert or update a `studio_board` row to `status='approved'` with a valid `content_url` (e.g., `s3://outputs/comfy/sample.png`).
   - Ensure `meta->>'publish_event_sent_at'` is `null`.
3. **Verify Agent Zero controller health**
   - Call `GET ${AGENT_ZERO_BASE_URL}/healthz` and confirm `nats.connected=true` and `nats.controller_started=true`. JetStream metrics should increment once the poller is running.
4. **Enable `approval_poller` workflow**

   - Activate once and watch n8n execution logs.
   - Verify Agent Zero logs a `content.publish.approved.v1` event.
5. **Enable `echo_publisher` workflow**
   - Activate once after step 3 succeeds.
   - Confirm Discord receives an embed containing title, namespace, and presigned asset link.
6. **Supabase audit verification**
   - Query `studio_board` for the modified row and confirm `status='published'`, `meta->>'publish_event_sent_at'` populated, and `meta->>'discord_webhook_response'` stored when available.
7. **Deactivate workflows (optional)**
   - If running in staging, deactivate after validation. For continuous operation, confirm schedule intervals and leave active.

### 2025-10-23 Session Status (Codex Sandbox)

| Step | Status | Notes |
| --- | --- | --- |
| Dry-run webhook ping | Blocked | Discord webhook credentials unavailable inside Codex; cannot reach external Discord API from sandbox. |
| Supabase approval trigger | Blocked | Supabase stack not running in the hosted environment; `make` targets require services that are not provisioned. |
| Verify Agent Zero controller health | Blocked | Agent Zero service is not accessible; health check would require running docker-compose profiles that are disabled in this session. |
| Enable `approval_poller` workflow | Blocked | n8n instance is not available in Codex; workflow import depends on external UI access. |
| Enable `echo_publisher` workflow | Blocked | Depends on previous steps; Discord credential binding cannot be validated. |
| Supabase audit verification | Blocked | Requires Supabase DB access and workflow execution. |
| Deactivate workflows | Blocked | Workflows never activated due to environment constraints. |

> **Follow-up**: Re-run the checklist on a workstation with docker-compose profiles (`data`, `orchestration`) and authenticated Discord/Supabase credentials available. Capture screenshots and log excerpts as originally requested once services are reachable.

## Troubleshooting Tips
- **403 from Agent Zero** — check `AGENT_ZERO_EVENTS_TOKEN` and ensure the shared secret matches the server configuration.
- **Discord rate limits** — limit embed updates to <5/minute per webhook. n8n logs include X-RateLimit headers for inspection.
- **Supabase polling misses rows** — ensure the filter includes `meta->>'publish_event_sent_at' IS NULL` and the poller runs with a consistent `since` cursor.
- **Embed rendering issues** — the `content.published.v1` schema supports `embeds[0].thumbnail_url`; verify the payload includes accessible URLs.

## Related References
- `pmoves/docs/CREATOR_PIPELINE.md` — end-to-end creative flow overview.
- `pmoves/docs/NEXT_STEPS.md` — actionable checklist with owners and status boxes.
- `pmoves/docs/ROADMAP.md` — milestone tracker showing how this automation closes M2 deliverables.
