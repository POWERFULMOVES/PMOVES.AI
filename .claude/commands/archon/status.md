Check Archon health and Supabase connectivity status.

Archon is a Supabase-driven agent service that manages prompt templates and agent forms. This command verifies Archon's health, its connection to Supabase, and its link to Agent Zero's MCP API.

## Usage

Run this command to:
- Verify Archon API is responding
- Check Supabase database connectivity
- Confirm Agent Zero MCP link is active
- View active prompt template count

## Implementation

Execute the following steps:

1. **Check Archon API health:**
   ```bash
   curl -sf http://localhost:8091/healthz | jq .
   ```

   Should return status, version, and dependency health.

2. **Verify Supabase connectivity:**
   ```bash
   curl -sf http://localhost:8091/healthz | jq '.dependencies.supabase'
   ```

   Should show `"connected"`. If not, check `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`.

3. **Check Archon UI availability:**
   ```bash
   curl -sf -o /dev/null -w "%{http_code}" http://localhost:3737/
   ```

   Should return `200`.

4. **Report results to user:**
   - Archon API health status
   - Supabase connectivity
   - UI availability
   - Any errors or misconfigurations

## Notes

- Archon API runs on port 8091, UI on port 3737
- Requires `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` to be configured
- Part of the `agents` Docker Compose profile
- Health endpoint: `GET http://localhost:8091/healthz`
