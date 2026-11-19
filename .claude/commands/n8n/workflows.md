# n8n Workflows

List and search n8n workflows.

## Arguments

- `$ARGUMENTS` - Optional: search term to filter workflows

## Instructions

1. Check n8n health at http://localhost:5678
2. List workflows via the n8n Public REST API
3. If search term provided, filter by name/tags

The n8n Public REST API is the live surface here. It is reached from the host at
`http://localhost:5678/api/v1` with the `X-N8N-API-KEY` header, and a list
response is `{"data": [...], "nextCursor": null}` — pass `nextCursor` back as
`?cursor=` to page, and count with `jq '.data | length'`.

```bash
# Health
curl -sf http://localhost:5678/healthz

# List all workflows
curl -s -H "X-N8N-API-KEY: $N8N_API_KEY" \
  http://localhost:5678/api/v1/workflows | jq '.data[] | {id, name, active}'

# Filter server-side by exact name
curl -s -H "X-N8N-API-KEY: $N8N_API_KEY" \
  "http://localhost:5678/api/v1/workflows?name=$ARGUMENTS" | jq '.data[] | {id, name, active}'

# Filter by tag (comma-separated), or by active state
curl -s -H "X-N8N-API-KEY: $N8N_API_KEY" \
  "http://localhost:5678/api/v1/workflows?tags=production" | jq '.data[] | {id, name, active}'
curl -s -H "X-N8N-API-KEY: $N8N_API_KEY" \
  "http://localhost:5678/api/v1/workflows?active=true" | jq '.data[] | {id, name, active}'
```

Report:
- Total workflow count
- Active vs inactive workflows
- Workflow names and IDs
