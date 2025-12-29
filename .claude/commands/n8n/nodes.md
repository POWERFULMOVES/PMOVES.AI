# n8n Node Documentation

Search n8n node documentation from the PMOVES-n8n-mcp knowledge base.

## Arguments

- `$ARGUMENTS` - Node name or capability to search for (e.g., "HTTP", "webhook", "Slack")

## Instructions

1. Search the n8n-mcp node registry (543 nodes with documentation)
2. Return matching node schemas and operations
3. Include usage examples from templates if available

The n8n-mcp submodule provides:
- 543 n8n nodes from base and LangChain packages
- 87% documentation coverage
- 99% schema coverage
- 2,709 workflow templates

```bash
# Search nodes in n8n-mcp data
grep -ri "$ARGUMENTS" /home/pmoves/PMOVES.AI/PMOVES-BoTZ/features/n8n/n8n-mcp/data/ 2>/dev/null | head -20

# Or use the MCP tool
docker exec pmoves-n8n-agent-1 python3 -c "
# Query node documentation
from pathlib import Path
import json

data_dir = Path('/app/data/nodes')
for node_file in data_dir.glob('*.json'):
    node = json.loads(node_file.read_text())
    if '$ARGUMENTS'.lower() in node.get('displayName', '').lower():
        print(f'{node[\"displayName\"]}: {node.get(\"description\", \"No description\")}')
"
```

Report:
- Matching node names and descriptions
- Required inputs/outputs
- Configuration properties
- Example usage from templates
