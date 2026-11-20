# n8n Node Documentation

Search the n8n nodes the live instance is actually built from.

## Arguments

- `$ARGUMENTS` - Node name or capability to search for (e.g., "HTTP", "webhook", "Slack")

## Instructions

1. List the workflows in the instance, paging through EVERY page
2. Read each workflow's node graph and keep the nodes whose type or name matches
3. Return the node type, its configured inputs/outputs, and a usage example

**WHAT THE PUBLIC REST API CAN AND CANNOT ANSWER.** The n8n Public REST API
returns every workflow's nodes with their `type`, `name` and full `parameters`
object. It does NOT expose a node CATALOG: there is no route for installed
node metadata, node descriptions, node schemas, or required inputs/outputs.
So the sources are distinct, and the command must not blur them:

- the workflow census below is the instance's real **USAGE** — it is the only
  thing the API can answer, and it is honest about being usage;
- a node that is **INSTALLED but has never been used in a workflow** does not
  appear in the census at all. For that case, read the installed node
  definitions out of the n8n container (the node packages ship inside the
  image) rather than concluding the node is absent;
- the node's **SCHEMA** — required inputs, outputs, credentials — comes from
  that same installed definition, NOT from a workflow's configured instance.
  A workflow's `parameters` object is one CONFIGURED INSTANCE of a node, not
  the node's description of itself.

The old `PMOVES-BoTZ/features/n8n/n8n-mcp/data/` knowledge base is NOT in this
repository (PMOVES-BoTZ has no `n8n-mcp` directory), so the grep path it used
is gone.

**REDACT CREDENTIAL-BEARING PARAMETERS.** A configured instance's `parameters`
object can carry literal HTTP headers, query parameters, webhook secrets and
inline credentials. Printing it whole copies those secrets into the chat
transcript, and this command then asks the agent to report the configuration
properties. So the VALUES of credential-bearing keys are redacted before
anything is emitted: report the KEY names and the shape, never the secret.

```bash
# 1. List workflows, paging through EVERY page. The API's default take is
#    100, so a single unpaged call silently ignores everything past the
#    opening act on a busy instance.
CURSOR=""
while : ; do
  RESP=$(curl -s -G -H "X-N8N-API-KEY: $N8N_API_KEY" \
    --data-urlencode "take=250" \
    ${CURSOR:+--data-urlencode "cursor=$CURSOR"} \
    http://localhost:5678/api/v1/workflows)
  echo "$RESP" | jq -c '.data[] | {id, name}'
  CURSOR=$(echo "$RESP" | jq -r '.nextCursor // empty')
  [ -z "$CURSOR" ] && break
done

# 2. Matching nodes across every workflow: type and name, with the
#    credential-bearing parameter VALUES redacted.
for id in $(curl -s -G -H "X-N8N-API-KEY: $N8N_API_KEY" \
    --data-urlencode "take=250" \
    http://localhost:5678/api/v1/workflows | jq -r '.data[].id'); do
  curl -s -H "X-N8N-API-KEY: $N8N_API_KEY" \
    "http://localhost:5678/api/v1/workflows/$id" \
    | jq -r --arg q "$ARGUMENTS" '
        .nodes[]
        | select((.type | ascii_downcase | contains($q | ascii_downcase))
                 or (.name | ascii_downcase | contains($q | ascii_downcase)))
        | .type as $t
        | .name as $n
        | (.parameters // {})
        | to_entries
        | map(if (.key | ascii_downcase
                  | test("header|auth|token|secret|password|credential|signature|cookie"))
              then {key: .key, value: "***REDACTED***"}
              else . end)
        | from_entries
        | "\($t)\t\($n)\t\(tostring)"'
done

# 3. The INSTALLED node catalog, for a node no workflow uses yet. Locate the
#    package directory rather than assuming a path.
docker exec pmoves-n8n sh -lc \
  'find / -maxdepth 8 -type d -name "n8n-nodes-base" 2>/dev/null | head -1'

# 4. Example usage from the workflow templates in this repo
grep -rl "$ARGUMENTS" pmoves/n8n/flows/ 2>/dev/null | head -10
```

Report:
- Matching node names and descriptions
- Required inputs/outputs — from the INSTALLED definition, not from a
  configured instance
- Configuration properties, with credential-bearing values REDACTED
- Example usage from templates
- When the node is installed but unused, say that the census found no usage
  and that the definition was read from the image instead
