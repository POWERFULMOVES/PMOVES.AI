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

**URL-ENCODE THE SEARCH TERM.** A workflow name commonly contains characters
that are meaningful in a URL: a space (`Finance Monthly`), `&`, `#`, `?`. A raw
interpolation either makes curl reject the URL or changes the query
parameters, so the search silently finds the WRONG workflow or none. Build the
query with curl's `--get --data-urlencode` instead of pasting the term into the
URL.

**PAGE THROUGH EVERY PAGE.** The API's default take is 100, so a single
unpaged listing silently ignores every workflow past the first hundred.

```bash
# Health
curl -sf http://localhost:5678/healthz

# List all workflows, paging through EVERY page
CURSOR=""
while : ; do
  RESP=$(curl -s -G -H "X-N8N-API-KEY: $N8N_API_KEY" \
    --data-urlencode "take=250" \
    ${CURSOR:+--data-urlencode "cursor=$CURSOR"} \
    http://localhost:5678/api/v1/workflows)
  echo "$RESP" | jq -c '.data[] | {id, name, active}'
  CURSOR=$(echo "$RESP" | jq -r '.nextCursor // empty')
  [ -z "$CURSOR" ] && break
done

# Filter server-side by exact name (URL-ENCODED)
curl -s -G -H "X-N8N-API-KEY: $N8N_API_KEY" \
  --data-urlencode "name=$ARGUMENTS" \
  http://localhost:5678/api/v1/workflows | jq '.data[] | {id, name, active}'

# Filter by tag (comma-separated), or by active state
curl -s -H "X-N8N-API-KEY: $N8N_API_KEY" \
  http://localhost:5678/api/v1/workflows?tags=production | jq '.data[] | {id, name, active}'
curl -s -H "X-N8N-API-KEY: $N8N_API_KEY" \
  http://localhost:5678/api/v1/workflows?active=true | jq '.data[] | {id, name, active}'
```

Report:
- Total workflow count — counted across EVERY page, not just the first
- Active vs inactive workflows
- Workflow names and IDs
