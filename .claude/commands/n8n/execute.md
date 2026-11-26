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
workflow.

**ACTIVATION IS NOT EXECUTION.** `POST /workflows/{id}/activate` enables the
workflow's TRIGGERS; it does not create an execution. For a schedule-,
manual- or queue-triggered workflow, activating it and then reading
`/executions?workflowId=…` can return NO result, or a run produced by an
earlier trigger — and reporting that as this request's output is a lie. This
command therefore never presents activation as execution:

- a **webhook-triggered** workflow is executed by CALLING its webhook;
- **any other trigger type has no direct-execution route in the Public REST
  API**. Say so, name the trigger type, and say how the workflow is really
  triggered. Do NOT report a historical execution as this request's result.

**RESTORE THE ACTIVATION STATE.** Activating a cron-triggered workflow arms it
for every interval, for ever — nothing else turns it off. Record whether the
workflow was ALREADY active, and deactivate it again if this command is what
activated it.

```bash
# 1. Resolve name -> workflow ID. The name is URL-ENCODED: a workflow called
#    "Finance Monthly" carries a raw space, and any &, # or ? in the name
#    splits or truncates the query, so the lookup silently finds the WRONG
#    workflow. The listing PAGES: the API's default take is 100, so an
#    unpaged lookup ignores every workflow past the first hundred.
CURSOR=""
while : ; do
  RESP=$(curl -s -G -H "X-N8N-API-KEY: $N8N_API_KEY" \
    --data-urlencode "take=250" \
    --data-urlencode "name=$ARGUMENTS" \
    ${CURSOR:+--data-urlencode "cursor=$CURSOR"} \
    http://localhost:5678/api/v1/workflows)
  echo "$RESP" | jq -c '.data[] | {id, name, active}'
  CURSOR=$(echo "$RESP" | jq -r '.nextCursor // empty')
  [ -z "$CURSOR" ] && break
done

# 2. Read the workflow: record its activation state and its trigger nodes
curl -s -H "X-N8N-API-KEY: $N8N_API_KEY" \
  http://localhost:5678/api/v1/workflows/<workflow-id> \
  | jq '{active,
        triggers: [.nodes[]
                   | select(.type | test("webhook|schedule|manual|trigger"))
                   | {type, name}]}'

# 3a. Webhook-triggered: list the CANDIDATES with an index and pick ONE
#     deliberately. A workflow with two webhook nodes otherwise hands the
#     executor two URLs and no tiebreaker. Test-mode webhooks live at
#     /webhook-test/<path> and need no activation; production webhooks live
#     at /webhook/<path> and need the workflow ACTIVE.
curl -s -H "X-N8N-API-KEY: $N8N_API_KEY" \
  http://localhost:5678/api/v1/workflows/<workflow-id> \
  | jq -r '.nodes[]
           | select(.type == "n8n-nodes-base.webhook")
           | "[\(.name)] path=\(.parameters.path) mode=\(.parameters.mode // "production")"'

# 3b. NOT webhook-triggered: do not activate-and-hope. Report the trigger
#     type from step 2. If activation is genuinely required, record that this
#     command activated it, and restore it in step 5.
curl -s -X POST -H "X-N8N-API-KEY: $N8N_API_KEY" \
  -H "Content-Type: application/json" \
  http://localhost:5678/api/v1/workflows/<workflow-id>/activate

# 4. Read the execution — and ONLY an execution that STARTED AFTER this
#    request began. An older run is not this request's output, so it is
#    filtered out rather than reported.
curl -s -H "X-N8N-API-KEY: $N8N_API_KEY" \
  "http://localhost:5678/api/v1/executions?workflowId=<workflow-id>&includeData=true" \
  | jq --arg since "<request-start-timestamp>" \
      '.data[] | select(.startedAt > $since)
       | {id, status, mode, startedAt, stoppedAt}'

# 5. Restore the activation state: deactivate ONLY if this command activated it
curl -s -X POST -H "X-N8N-API-KEY: $N8N_API_KEY" \
  http://localhost:5678/api/v1/workflows/<workflow-id>/deactivate
```

Report:
- Execution ID
- Status (success/error)
- Output data summary
- Any error messages
- **Which webhook path was called** when the workflow is webhook-triggered — and
  which candidate was chosen and why
- **That direct execution is unsupported for this trigger type** when it is
  not webhook-triggered, instead of a historical execution presented as this
  request's result
