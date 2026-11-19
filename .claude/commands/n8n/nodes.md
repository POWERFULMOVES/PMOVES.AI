# n8n Node Documentation

Search the n8n nodes the live instance is actually built from.

## Arguments

- `$ARGUMENTS` - Node name or capability to search for (e.g., "HTTP", "webhook", "Slack")

## Instructions

1. List the workflows in the instance
2. Read each workflow's node graph and keep the nodes whose type or name matches
3. Return the node type, its configured inputs/outputs, and a usage example

The n8n Public REST API returns every workflow's nodes with their `type`,
`name` and full `parameters` object, so the instance itself is the node
catalog — no side-car knowledge base is involved. The old
`PMOVES-BoTZ/features/n8n/n8n-mcp/data/` knowledge base is NOT in this
repository (PMOVES-BoTZ has no `n8n-mcp` directory), so the grep path it used
is gone.

```bash
# 1. List workflows
curl -s -H "X-N8N-API-KEY: $N8N_API_KEY" \
  http://localhost:5678/api/v1/workflows | jq '.data[] | {id, name}'

# 2. Matching nodes across every workflow (type, name, configured parameters)
for id in $(curl -s -H "X-N8N-API-KEY: $N8N_API_KEY" \
  http://localhost:5678/api/v1/workflows | jq -r '.data[].id'); do
  curl -s -H "X-N8N-API-KEY: $N8N_API_KEY" \
    "http://localhost:5678/api/v1/workflows/$id" \
    | jq -r --arg q "$ARGUMENTS" \
      '.nodes[]
       | select((.type | ascii_downcase | contains($q | ascii_downcase))
                or (.name | ascii_downcase | contains($q | ascii_downcase)))
       | "\(.type)\t\(.name)\t\(.parameters | tostring)"'
done

# 3. Example usage from the workflow templates in this repo
grep -rl "$ARGUMENTS" pmoves/n8n/flows/ 2>/dev/null | head -10
```

Report:
- Matching node names and descriptions
- Required inputs/outputs
- Configuration properties
- Example usage from templates
