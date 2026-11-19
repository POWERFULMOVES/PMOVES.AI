# n8n Execute Workflow

Execute an n8n workflow by ID or name.

## Arguments

- `$ARGUMENTS` - Workflow ID or name to execute

## Instructions

1. If argument is a name, resolve to workflow ID first
2. Trigger the workflow through the n8n Public REST API
3. Report execution status and any output data

n8n 2.1's Public REST API has NO `POST /workflows/{id}/run` route. The workflow
routes it exposes are `GET/POST /workflows`, `GET/PUT/DELETE /workflows/{id}`,
`POST /workflows/{id}/activate`, `POST /workflows/{id}/deactivate`, plus the
`/tags`, `/transfer` and `/{versionId}` variants — none of which runs a
workflow. So a workflow is executed by calling its webhook, or by activating it
and reading the execution it produces. (A curl to `/workflows/{id}/run`
returns 404: that endpoint does not exist in the public API.)

```bash
# 1. Resolve name -> workflow ID
curl -s -H "X-N8N-API-KEY: $N8N_API_KEY" \
  "http://localhost:5678/api/v1/workflows?name=$ARGUMENTS" | jq '.data[] | {id, name}'

# 2a. Webhook-triggered workflow: read the trigger path, then call the webhook
curl -s -H "X-N8N-API-KEY: $N8N_API_KEY" \
  http://localhost:5678/api/v1/workflows/<workflow-id> \
  | jq -r '.nodes[] | select(.type == "n8n-nodes-base.webhook") | .parameters.path'

curl -X POST -H "Content-Type: application/json" \
  -d '{}' http://localhost:5678/webhook/<webhook-path>

# 2b. Otherwise: activate the workflow so its trigger fires
curl -s -X POST -H "X-N8N-API-KEY: $N8N_API_KEY" \
  -H "Content-Type: application/json" \
  http://localhost:5678/api/v1/workflows/<workflow-id>/activate

# 3. Read the execution
curl -s -H "X-N8N-API-KEY: $N8N_API_KEY" \
  "http://localhost:5678/api/v1/executions?workflowId=<workflow-id>&includeData=true" \
  | jq '.data[] | {id, status, mode, startedAt, stoppedAt}'

curl -s -H "X-N8N-API-KEY: $N8N_API_KEY" \
  "http://localhost:5678/api/v1/executions/<execution-id>?includeData=true" \
  | jq '{id, status, finished, startedAt, stoppedAt, data}'
```

Report:
- Execution ID
- Status (success/error)
- Output data summary
- Any error messages
