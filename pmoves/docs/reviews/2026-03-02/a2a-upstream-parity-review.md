# A2A Upstream Parity Review (2026-03-02)

Reference snapshot:
- Upstream repo: `https://github.com/a2aproject/A2A`
- Reviewed commit: `4890b77`

## Findings Applied

1. Discovery endpoint path drift
- Upstream canonical discovery path is `/.well-known/agent-card.json`.
- PMOVES had only `/.well-known/agent.json`.
- Action: Added canonical route and kept `/.well-known/agent.json` as legacy alias.

2. Auth posture consistency
- Upstream guidance emphasizes authenticated access for sensitive/enterprise deployment.
- PMOVES previously auth-gated discovery but left task APIs open.
- Action: Auth is now required by default for all A2A task/discovery endpoints.

3. Explicit opt-in for public mode
- Public discovery/task exposure should be intentional.
- Action: Added env overrides:
  - `A2A_DISCOVERY_PUBLIC=true`
  - `A2A_TASKS_PUBLIC=true`

4. Error hygiene
- Avoid leaking JWT parser internals in responses.
- Action: Replaced detailed JWT exception text with generic validation errors.

## Files Updated

- `pmoves/services/agent-zero/python/features/a2a/server.py`
- `pmoves/services/agent-zero/python/features/a2a/types.py`
- `pmoves/services/agent-zero/python/features/a2a/test_server.py`
- `pmoves/docs/integrations/INTEGRATIONS.md`
