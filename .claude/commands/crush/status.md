# PMOVES CLI Status

Check the status of PMOVES CLI (Crush) configuration and BoTZ registration.

## Instructions

1. **Check Crush installation**:
   ```bash
   command -v crush && crush --version
   ```

2. **Check crush.json configuration**:
   ```bash
   if [ -f crush.json ]; then
     echo "crush.json found"
     cat crush.json | jq '.options.attribution, .providers[0]'
   else
     echo "crush.json not found - run: pmoves crush setup"
   fi
   ```

3. **Check via PMOVES CLI**:
   ```bash
   pmoves crush status
   ```

4. **Check BoTZ Gateway connectivity**:
   ```bash
   curl -sf http://localhost:8054/healthz 2>/dev/null && echo "BoTZ Gateway: OK" || echo "BoTZ Gateway: Not running"
   ```

5. **Query BoTZ registration status**:
   - Check if this instance is registered in `botz_instances` table
   - Show current skill level and available MCP tools

6. **Show current work item assignments**:
   - Query `integration_work_items` for items assigned to this BoTZ
   - Display in-progress and recently completed items

## Status Output

Report the following:
- Crush CLI version
- Configuration status (crush.json present/valid)
- PMOVES providers configured
- BoTZ Gateway connectivity
- Registration status (registered/unregistered)
- Skill level (basic/tac_enabled/mcp_augmented/agentic)
- Active work items count
- Completed work items count (last 7 days)

## Troubleshooting

If not registered:
1. Run `pmoves crush setup` to configure
2. Ensure BoTZ Gateway is running
3. Check Supabase connectivity
