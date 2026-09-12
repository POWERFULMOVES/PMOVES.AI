# Handoff: per-node `expects` matrix (2026-09-05)

**Lane owner (proposed):** Crush on the 5090 (code); the steward reads it, fleet-sentinel verifies it. **Raised by:** operator + 5090-CLAUDE. **Tracking:** #2962 (App/runner reconciliation), #2957 (substrate credentials).

## The gap, measured

`pmoves/config/profiles/desktop-9950xd.yaml` declares hardware, model bundles and compose overrides. Nothing says which compose profiles and services this node must host. Result on the 5090 today: the worker and agent layers are fully up, but every `agents` / `workers` / `orchestration` / `media` profile extra (a2ui-renderer, consciousness-service, gateway-agent, notebook-sync, session-context-worker, cast-tts-gateway, voice-relay, the hf agents) sits dark on the node built to host them, and fleet-sentinel's first real roster has only the services that announce on boot (2 of about 98). Seventeen substrate services still pull upstream images while PMOVES forks exist: qdrant (Darkmatter), neo4j, nats, minio, the eleven Supabase services, tensorzero, clickhouse, meilisearch, juicefs, ollama.

## Shape (snowflake to iceberg)

Each node profile stays a snowflake for hardware and gains one block:

```yaml
expects:
  compose_profiles: [agents, workers, orchestration, media, ui, p7]
  services:
    require: [fleet-sentinel, p7, p7-room-orchestrator, openroom]
    forbid: [nvidia-nim]
  substrate:
    qdrant: {image: darkmatter, mode: full}
    neo4j: {image: pmoves-neo4j}
  identity: {steward: node-steward@5090, cipher: required, village_rules: true}
  sandbox: {e2b: danger-room}
  runners: {self_hosted: false}
```

Constrained nodes set `qdrant.mode: edge`; that is the iceberg's tip on a snowflake.

## Consumers

1. **Steward** (`.claude/agents/node-steward.md`): at session start, load `expects`, diff against `docker ps` and the compose service list across all profiles, and print the gap before claiming work.
2. **fleet-sentinel**: take the expected roster as input so it can report expected-but-never-announced, not only what announced.
3. **Layered bring-up**: `bringup-layered` derives its profile list from `expects.compose_profiles` instead of the hand-picked `AGENT_SERVICES` and `WORKER_SERVICES` lists.
4. **Validator**: `pmoves/tools/profile_loader.py` gains the schema; a ratchet flags a node whose `expects` names a service the compose does not define.

## Known trap

`p7` and `p7-room-orchestrator` both live in the `agents` profile; the legacy one listens on 8122 and must be built from source because no GHCR image exists (#2966). Encode that in `expects` rather than rediscovering it per node.
