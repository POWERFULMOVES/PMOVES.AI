Query task progress via Agent Zero's job log API.

Read back the progress of a task submitted via `/agents:execute` or `POST /tasks`.

## Usage

Run this command with a context id:
- `/agents:task-status <context_id>` — read that task's job log

## Implementation

Execute the following steps:

1. **Check supervisor + runtime health:**
   ```bash
   curl -sf http://localhost:8080/healthz | jq '{status, runtime: .runtime.status}'
   ```

2. **Fetch the job log for a context id:**
   ```bash
   curl -sf "http://localhost:8080/jobs/{context_id}?length=100" | jq .
   ```

   `<context_id>` is the `context_id` returned by `POST /tasks`.
   `length` is 1-1000 (default 100). A 404 means the context was not found —
   it expired, or the id is wrong.

3. **If no context id was given:** there is no list-tasks endpoint on this API.
   Ask the user for the `context_id` from their `/agents:execute` run.

4. **Report results to user:**
   - The log tail
   - Whether the run reached a final assistant response
   - Any errors surfaced in the log

## Authentication

None. The supervisor declares no inbound auth dependency on these routes. It
forwards `X-API-KEY` (`AGENT_ZERO_API_KEY`) to the A0 runtime on your behalf.

## Task status

The supervisor exposes **no task-status enum**. `GET /jobs/{context_id}` returns
runtime log items; progress and completion are read from the log tail, not from
a `status` field. There is no `queued`/`running`/`completed`/`failed`/`timeout`
state machine on this API.

## Notes

- Agent Zero publishes task events to NATS (`agentzero.task.v1`)
- Monitor metrics: `curl -s http://localhost:8080/metrics | grep agentzero`
- Canonical API surface: `pmoves/docs/operations/AGENT_ZERO_API.md`
