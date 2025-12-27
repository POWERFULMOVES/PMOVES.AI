# n8n Workflows

List and search n8n workflows.

## Arguments

- `$ARGUMENTS` - Optional: search term to filter workflows

## Instructions

1. Check n8n health at http://localhost:5678
2. List workflows via n8n API or MCP tool
3. If search term provided, filter by name/tags

```bash
# List all workflows
curl -s -H "X-N8N-API-KEY: $N8N_API_KEY" \
  http://localhost:5678/api/v1/workflows | jq '.data[] | {id, name, active}'

# Or via n8n MCP tool
docker exec pmoves-n8n-agent-1 python3 -c "
import asyncio
from app_n8n_agent import N8nClient
async def main():
    client = N8nClient('http://n8n:5678/api/v1', '$N8N_API_KEY')
    workflows = await client.list_workflows()
    for wf in workflows[:10]:
        print(f'{wf[\"id\"]}: {wf[\"name\"]} (active={wf.get(\"active\", False)})')
asyncio.run(main())
"
```

Report:
- Total workflow count
- Active vs inactive workflows
- Workflow names and IDs
