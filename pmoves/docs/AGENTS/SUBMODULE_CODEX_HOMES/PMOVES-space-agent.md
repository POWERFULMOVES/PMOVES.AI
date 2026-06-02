# Codex Home Overlay: PMOVES-space-agent

Scope:
- Browser-first Space Agent runtime, PMOVES bridge endpoints, NATS subscriptions, and L1 customware.

Use this when:
- Codex needs to route PMOVES events into browser spaces or widgets
- the work touches `pmoves.space.*`, `pmoves.agent.*`, or `/api/pmoves_bridge`
- the task needs Space Agent fleet-mode integration with Agent Zero, NATS, or PMOVES room surfaces

PMOVES companions:
- `PMOVES-Agent-Zero` for orchestration and embedded workspace mode
- `PMOVES-BoTZ` for MCP tool inventory and agent event sources
- `PMOVES-tensorzero` for model routing that feeds agent status widgets
- `pmoves/docs/AGENTS/AGNOTE4482.md` for the space-agent fleet integration gap

Core checks:
- `cd PMOVES-space-agent && npm test`
- `cd PMOVES-space-agent && node space serve PORT=3010`
- `curl -fsS http://localhost:3010/api/pmoves_bridge`
- `curl -fsS http://localhost:3010/api/pmoves_nats_status`

Implementation rules:
- Keep bridge API files flat under `server/api/`; router paths are single segment only.
- Keep PMOVES-specific code under the submodule `pmoves/` overlay path unless upstream changes are explicitly intended.
- Use `X-PMOVES-API-KEY` / `PMOVES_BRIDGE_API_KEY` for current bridge auth; CHIT HMAC is future work.
- Keep NATS subjects lowercase under `pmoves.space.>` and `pmoves.agent.>`.

Related parity tokens:
- `/agents:status`
- `/nats:status`
- `/nats:monitor`
- `/workitems:claim`

Related docs:
- `PMOVES-space-agent/PMOVES.AI_INTEGRATION.md`
- `PMOVES-space-agent/CLAUDE.md`
- `pmoves/docs/AGENTS/CODEX_CLAUDE_PARITY_MAP.md`
- `pmoves/docs/AGENTS/AGNOTE4482.md`
