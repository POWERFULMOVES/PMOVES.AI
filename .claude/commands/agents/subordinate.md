Dispatch a task to Agent Zero under a specialist agent profile.

Agent Zero has **no subordinate-creation API**. What exists: you can pin the
*profile* a task runs under, and the agent itself may spawn subordinates mid-run
via its `call_subordinate` tool. Neither gives you a subordinate handle — results
arrive in the task's job log.

## Usage

Run this command with a profile and a task:
- `/agents:subordinate researcher Find prior art for X`
- `/agents:subordinate developer Refactor the retry logic in Y`

## Implementation

Execute the following steps:

1. **Check supervisor + runtime health:**
   ```bash
   curl -sf http://localhost:8080/healthz | jq '{status, runtime: .runtime.status}'
   ```

   If `.status` is `stopped`, inform the user and stop.

2. **Submit the task with a profile:**
   ```bash
   curl -sf -X POST http://localhost:8080/tasks \
     -H "Content-Type: application/json" \
     -d '{
       "message": "<role, goal, and the concrete task>",
       "metadata": {"agent_profile": "researcher"}
     }' | jq .
   ```

   `metadata` is merged into the runtime payload, so `agent_profile` reaches the
   runtime's message handler. Returns `{"context_id": ..., "response": ...}`.

   The profile can only be set on a **new** context. Passing `agent_profile`
   together with an existing `context_id` returns 400.

3. **Read the result:**
   ```bash
   curl -sf "http://localhost:8080/jobs/{context_id}?length=200" | jq .
   ```

4. **Report results to user:**
   - The `context_id`
   - The profile the task was dispatched under
   - The log tail, including any subordinate transcript

## Available profiles

`agent0`, `default`, `developer`, `hacker`, `pmoves_custom`, `researcher`

Defined in `PMOVES-Agent-Zero/agents/`. There is no API to create new ones — add
a profile directory to the submodule.

## Authentication

None. The supervisor declares no inbound auth dependency on these routes. It
forwards `X-API-KEY` (`AGENT_ZERO_API_KEY`) to the A0 runtime on your behalf.

## Notes

- No subordinate id, no subordinate registry, no per-subordinate timeout or turn
  cap is exposed over HTTP. Those were documented but never built.
- True subordinates are spawned by the model via its `call_subordinate` tool
  (`PMOVES-Agent-Zero/tools/call_subordinate.py`, contract
  `prompts/agent.system.tool.call_sub.md`; args `message`, `profile`, `reset`).
  Ask for delegation in the `message` and read the transcript in the job log.
- Canonical API surface: `pmoves/docs/operations/AGENT_ZERO_API.md`
