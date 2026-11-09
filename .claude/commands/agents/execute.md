Submit a task for execution via Agent Zero's task API.

The Agent Zero supervisor accepts free-form task submissions and forwards them to
the agent runtime. Progress is read back from the job log.

## Usage

Run this command with a task description:
- `/agents:execute Analyze the latest deployment logs`
- `/agents:execute Review the security audit results`

## Implementation

Execute the following steps:

1. **Check supervisor + runtime health:**
   ```bash
   curl -sf http://localhost:8080/healthz | jq '{status, runtime: .runtime.status}'
   ```

   `POST /tasks` requires the runtime to be running. If `.status` is `stopped`,
   inform the user and stop.

2. **Submit the task:**
   ```bash
   curl -sf -X POST http://localhost:8080/tasks \
     -H "Content-Type: application/json" \
     -d '{"message": "<user_provided_task_description>", "metadata": {}}' | jq .
   ```

   Body fields: `message` (required), `attachments`, `lifetime_hours`, and
   `metadata` (merged into the runtime payload — this is how `agent_profile`
   is passed; see `/agents:subordinate`).

   Returns `{"context_id": "...", "response": "..."}`. Keep the `context_id`.

3. **Poll the job log:**
   ```bash
   curl -sf "http://localhost:8080/jobs/{context_id}?length=100" | jq .
   ```

   `length` is 1-1000 (default 100). There is no status enum — the runtime
   returns log items; progress and completion are read from the log tail,
   not from a state field.

4. **Report results to user:**
   - `context_id` for future reference
   - The log tail
   - Whether the run reached a final assistant response

## Authentication

None. The supervisor declares no inbound auth dependency on these routes. It
forwards `X-API-KEY` (`AGENT_ZERO_API_KEY`) to the A0 runtime on your behalf.

## Notes

- Tasks execute asynchronously via Agent Zero's agent runtime
- NATS JetStream provides reliable event delivery (`AGENTZERO_JETSTREAM=true`)
- There is no `priority` field and no per-task `timeout_seconds` on this API
- To dispatch under a specialist profile, see `/agents:subordinate`
- Monitor task metrics: `curl -s http://localhost:8080/metrics | grep agentzero`
- Canonical API surface: `pmoves/docs/operations/AGENT_ZERO_API.md`
