# n8n Suggest Workflow

Get AI-powered workflow suggestions using TensorZero and n8n-mcp node knowledge.

## Arguments

- `$ARGUMENTS` - Description of the automation task you want to accomplish

## Instructions

1. Analyze the task description
2. Query n8n-mcp for relevant node documentation (543 nodes available)
3. Use TensorZero LLM to suggest a workflow structure
4. Optionally reference existing workflow templates (2,646 available)

The n8n MCP agent provides:
- `n8n_suggest_workflow` - AI-powered suggestions
- `n8n_node_docs` - Node documentation lookup
- `n8n_find_templates` - Template search

```bash
# Via n8n MCP agent
docker exec pmoves-n8n-agent-1 python3 -c "
import asyncio
from app_n8n_agent import suggest_workflow
async def main():
    result = await suggest_workflow('$ARGUMENTS')
    print(result)
asyncio.run(main())
"
```

Report:
- Suggested workflow structure (nodes and connections)
- Required node types and their purposes
- Configuration hints
- Similar templates if available
