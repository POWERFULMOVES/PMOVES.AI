# n8n Suggest Workflow

Get AI-powered workflow suggestions using TensorZero and the live n8n node graph.

## Arguments

- `$ARGUMENTS` - Description of the automation task you want to accomplish

## Instructions

1. Analyze the task description
2. Collect the node types the live instance actually uses
3. Use TensorZero LLM to suggest a workflow structure
4. Reference existing workflows as templates

Two live services back this command: the n8n Public REST API
(`http://localhost:5678/api/v1`, header `X-N8N-API-KEY`) for the node graph and
the existing workflows, and the TensorZero gateway
(`http://localhost:3030/v1/chat/completions`, host port 3030 maps to the
gateway's container port 3000) for the synthesis.

**PAGE THROUGH EVERY PAGE.** The API's default take is 100, so an unpaged
listing silently ignores every workflow past the opening act — and this census
is what feeds the node-type list the model is told to use. Page on
`nextCursor` until it is null.

```bash
# 1. Every workflow id, across EVERY page
WORKFLOW_IDS=""
CURSOR=""
while : ; do
  RESP=$(curl -s -G -H "X-N8N-API-KEY: $N8N_API_KEY" \
    --data-urlencode "take=250" \
    ${CURSOR:+--data-urlencode "cursor=$CURSOR"} \
    http://localhost:5678/api/v1/workflows)
  WORKFLOW_IDS="$WORKFLOW_IDS $(echo "$RESP" | jq -r '.data[].id')"
  CURSOR=$(echo "$RESP" | jq -r '.nextCursor // empty')
  [ -z "$CURSOR" ] && break
done

# 2. Node types the live instance actually uses
NODE_TYPES=$(for id in $WORKFLOW_IDS; do
  curl -s -H "X-N8N-API-KEY: $N8N_API_KEY" \
    "http://localhost:5678/api/v1/workflows/$id" | jq -r '.nodes[].type'
done | sort -u | paste -sd, -)

# 3. Existing workflows to model the suggestion on, across EVERY page
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

# 4. Ask TensorZero for a structure (build the payload with jq so the task
#    description cannot break the JSON)
jq -n --arg q "$ARGUMENTS" --arg nodes "$NODE_TYPES" \
  '{model: "agent_zero",
    messages: [{role: "user",
      content: ("Suggest an n8n workflow for: " + $q +
                ". Use only these node types: " + $nodes +
                ". List the nodes in order with their connections.")}]}' \
  | curl -s -X POST http://localhost:3030/v1/chat/completions \
      -H "Content-Type: application/json" -d @- \
  | jq -r '.choices[0].message.content'
```

Report:
- Suggested workflow structure (nodes and connections)
- Required node types and their purposes
- Configuration hints
- Similar templates if available
