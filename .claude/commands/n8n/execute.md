# n8n Execute Workflow

Execute an n8n workflow by ID or name.

## Arguments

- `$ARGUMENTS` - Workflow ID or name to execute

## Instructions

1. If argument is a name, resolve to workflow ID first
2. Execute the workflow via n8n API
3. Report execution status and any output data

```bash
# Execute by ID
curl -X POST -H "X-N8N-API-KEY: $N8N_API_KEY" \
  -H "Content-Type: application/json" \
  http://localhost:5678/api/v1/workflows/$ARGUMENTS/run

# Or via n8n MCP tool
docker exec pmoves-n8n-agent-1 python3 -c "
import asyncio
from app_n8n_agent import N8nClient
async def main():
    client = N8nClient('http://n8n:5678/api/v1', '$N8N_API_KEY')
    result = await client.execute_workflow('$ARGUMENTS')
    print(result)
asyncio.run(main())
"
```

Report:
- Execution ID
- Status (success/error)
- Output data summary
- Any error messages
