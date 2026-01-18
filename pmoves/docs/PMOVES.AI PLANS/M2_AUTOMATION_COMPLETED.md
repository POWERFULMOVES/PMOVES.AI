# M2 Automation Loop - Implementation Complete
_Last updated: 2026-01-02_

**Status**: ✅ Infrastructure complete; end-to-end validation blocked pending n8n poller activation  
**Date**: October 17, 2025  
**Branch**: `docs/m2-automation-cron-debug`

## What Was Built

### 1. Workflow Update Infrastructure
- **Script**: `pmoves/scripts/update_workflow.py`
  - Auto-detects workflow ID from JSON file (`workflowId` field)
  - Complies with n8n Public API schema (only allowed fields)
  - Fetches current `versionId` before PUT to prevent conflicts
  - Usage: `python3 update_workflow.py [workflow.json]`

### 2. n8n HTTP Request Node Modernization
- **File**: `pmoves/n8n/flows/approval_poller.json`
- Updated all 3 HTTP nodes to v4.1 format:
  - `method` instead of `requestMethod`
  - `sendBody`, `body` instead of `jsonParameters`, `bodyParametersJson`
  - `headerParameters.parameters[]` instead of `options.headerParametersUi.parameter[]`
  - `sendQuery`, `queryParameters` for GET requests

### 3. n8n Configuration
- **File**: `pmoves/docker-compose.n8n.yml`
- Enabled `N8N_PUBLIC_API_ENABLED=true` for workflow updates via API
- Configured environment variables for Supabase, Agent Zero, Discord endpoints

### 4. Test Infrastructure
- **Script**: `pmoves/scripts/test_m2_loop.py`
  - Creates Supabase approval rows with proper schema
  - Monitors `studio_board` for processing status
  - Validates `meta.publish_event_sent_at` timestamp

## Architecture

```
┌─────────────┐     ┌─────────┐     ┌────────────┐     ┌─────────┐
│  Supabase   │────▶│   n8n   │────▶│ Agent Zero │────▶│ Discord │
│ studio_board│     │  Cron   │     │  Gateway   │     │ Webhook │
└─────────────┘     └─────────┘     └────────────┘     └─────────┘
   status:            Every 1m         POST /events      Webhook ID:
   approved           Polls for        /publish          1428763455
                      approved rows                      682510940
```

## Key Discoveries

### n8n Public API Constraints
- PUT `/api/v1/workflows/:id` only accepts: `name`, `nodes`, `connections`, `settings`, `staticData`, `active`, `tags`, `id`, `versionId`, `sharing`
- Must include current `versionId` or PUT fails
- Endpoint: `/api/v1/workflows` (not `/rest/workflows`)
- Requires `N8N_PUBLIC_API_ENABLED=true` environment variable

### HTTP Request Node v4.1 Breaking Changes
- Old format (`requestMethod`, `jsonParameters`) silently fails
- New format requires explicit `method`, `sendBody`, structured `headerParameters`
- Body must use `body` field with `JSON.stringify()` expression, not `jsonBody` or `contentType: "json"`

### Workflow Activation Quirks
- Cron triggers don't auto-reload after workflow updates
- May require manual toggle in UI or workflow restart
- API `PATCH /workflows/:id {"active": true}` not supported in current n8n version

## Testing Status

### ✅ Verified Components
- n8n Public API authentication working
- Workflow update script deploys successfully
- Discord webhook (1428763455682510940) confirmed live
- HTTP nodes configured with POST method
- Cron schedule active (every minute)

### ⚠️ Pending Validation
- End-to-end M2 loop execution (Supabase → Agent Zero → Discord)
- Agent Zero `/events/publish` endpoint validation error resolution
- Supabase row status update (`published` + `meta.publish_event_sent_at`)

> **Status note:** Infrastructure is complete, but the automation loop is not validated until the n8n approval poller is activated and observed processing real `studio_board` rows.

## Next Steps

1. **Debug Agent Zero validation**: Investigate 422 Unprocessable Entity errors
2. **Test complete flow**: Create approval row with `s3://` URI (not `https://`)
3. **Monitor execution**: Check n8n execution logs for payload details
4. **Verify Discord**: Confirm notification appears in Discord channel
5. **Document success**: Update `SESSION_IMPLEMENTATION_PLAN.md` with results

## Files Modified

- `pmoves/scripts/update_workflow.py` (new)
- `pmoves/scripts/test_m2_loop.py` (new)
- `pmoves/n8n/flows/approval_poller.json` (HTTP node updates, added `workflowId`)
- `pmoves/docker-compose.n8n.yml` (enabled Public API)
- `pmoves/docs/N8N_SETUP.md` (API documentation)
- `pmoves/docs/N8N_CHECKLIST.md` (workflow update process)
- `pmoves/docs/SESSION_IMPLEMENTATION_PLAN.md` (progress tracking)

## Environment Variables

Required in `pmoves/.env.local`:
```bash
N8N_API_KEY=<jwt_token>
SUPABASE_REST_URL=http://host.docker.internal:54321/rest/v1
SUPABASE_SERVICE_ROLE_KEY=<jwt_token>
AGENT_ZERO_BASE_URL=http://agent-zero:8080
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/1428763455682510940/...
```

## Commands Reference

```bash
# Update workflow
cd /home/pmoves/PMOVES.AI
source pmoves/.env && export N8N_KEY="$N8N_API_KEY"
python3 pmoves/scripts/update_workflow.py

# Test M2 loop
python3 pmoves/scripts/test_m2_loop.py

# Check workflow status
curl -s "http://localhost:5678/api/v1/workflows/iduu9yTMifft1p47" \
  -H "X-N8N-API-KEY: ${N8N_API_KEY}" | jq '{active, versionId}'

# Test Discord webhook
curl -X POST "$DISCORD_WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d '{"content":"Test message","username":"PMOVES Publisher"}'
```

## Lessons Learned

1. **n8n version compatibility**: Always check node `typeVersion` when updating workflows
2. **API exploration methodology**: Use curl + jq to discover allowed fields through trial and error
3. **Parameter migration patterns**: Document old→new format mappings for future workflows
4. **Workflow state management**: Activation state separate from configuration updates
5. **Environment abstraction**: Use env vars in workflows (e.g., `$env.AGENT_ZERO_BASE_URL`)
