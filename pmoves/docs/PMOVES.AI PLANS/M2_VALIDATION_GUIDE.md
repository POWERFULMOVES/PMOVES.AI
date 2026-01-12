# M2 Automation Loop • Validation Guide
_Last updated: 2025-09-30_

Goal: Validate Supabase → Agent Zero → Discord automation end‑to‑end, capture evidence, and mark M2 complete.

## 1) Prerequisites
- Supabase CLI started locally (`supabase start` or `make supa-start`).
- `.env.local` configured (Supabase CLI `/rest/v1`, service role key, Discord webhook, Agent Zero URL).
- PMOVES stack: `make up && make up-agents && make up-n8n`.

## 2) Preflight
- Run: `make m2-preflight`
  - Confirms Agent Zero and publisher-discord health.
  - Sends Discord ping if webhook set.

## 3) n8n Import & Env
- Open `http://localhost:5678`.
- Import flows:
  - `pmoves/n8n/flows/approval_poller.json`
  - `pmoves/n8n/flows/echo_publisher.json`
- Ensure variables (Settings → Variables):
  - `SUPABASE_REST_URL=http://host.docker.internal:54321/rest/v1`
  - `SUPABASE_SERVICE_ROLE_KEY=<service-role-key>`
  - `AGENT_ZERO_BASE_URL=http://agent-zero:8080`
  - `AGENT_ZERO_EVENTS_TOKEN` (optional)
  - `DISCORD_WEBHOOK_URL`, `DISCORD_WEBHOOK_USERNAME`

## 4) Seed Approval Row
- Make (Bash): `make seed-approval TITLE="Demo" URL="s3://outputs/demo/example.png"`
- PowerShell: `make seed-approval-ps TITLE="Demo" URL="s3://outputs/demo/example.png"`

## 5) Activate Workflows
1. Enable approval_poller → watch execution logs.
2. Verify Agent Zero receives `content.publish.approved.v1`.
3. Enable echo_publisher.
4. Confirm Discord receives an embed.

## 6) Verify Supabase State
- Confirm `status='published'` and `meta.publish_event_sent_at` set on the modified `studio_board` row.

## 7) Evidence Capture (fill below)
- Paste screenshots/logs under `pmoves/docs/evidence/` and link here.

Helpers:
- Create a stamped filename (Bash): `make evidence-stamp LABEL="discord-embed"` → prints a path like `pmoves/docs/evidence/20250930_142233_discord-embed.png`
- Create a stamped filename (PowerShell): `make evidence-stamp-ps LABEL="discord-embed"`
- Append to CSV log (Bash): `make evidence-log LABEL="Discord embed" PATH="pmoves/docs/evidence/20250930_...png" NOTE="first run"`
- Append to CSV log (PowerShell): `make evidence-log-ps LABEL="Discord embed" PATH="pmoves/docs/evidence/20250930_...png" NOTE="first run"`

- [ ] Preflight output (Agent Zero + Publisher)
  - Timestamp: ________
  - Path: `pmoves/docs/evidence/preflight.png`
- [ ] Discord webhook ping
  - Timestamp: ________
  - Path: `pmoves/docs/evidence/discord-ping.png`
- [ ] n8n flows imported & env set
  - Timestamp: ________
  - Path: `pmoves/docs/evidence/n8n-import.png`
- [ ] approval_poller run shows publish → Agent Zero event
  - Timestamp: ________
  - Path: `pmoves/docs/evidence/poller-run.png`
- [ ] echo_publisher run shows Discord POST
  - Timestamp: ________
  - Path: `pmoves/docs/evidence/echo-run.png`
- [ ] Supabase row updated (published + timestamp)
  - Timestamp: ________
  - Path: `pmoves/docs/evidence/supabase-row.png`
- [ ] Discord embed received
  - Timestamp: ________
  - Path: `pmoves/docs/evidence/discord-embed.png`

## 8) Optional Checks
- `make demo-content-published` to test the embed pipeline directly via Agent Zero.
- Jellyfin link field (set `JELLYFIN_URL` and include `jellyfin_item_id` in payload).

## References
- `N8N_SETUP.md`, `SUPABASE_DISCORD_AUTOMATION.md`, `LOCAL_DEV.md`
