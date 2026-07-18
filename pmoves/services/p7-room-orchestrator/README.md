# P7 Room Orchestrator

P7 is the executable room-aware stage manager for PMOVES. It resolves canonical
manifests from `pmoves/config/rooms/catalog.json`, manages transient room
sessions, records state to Supabase, and bridges NATS commands to versioned facts.

## State contracts

- Room stage is persistent: `rehearsal -> live -> review -> archive`; every
  transition requires a durable Supabase write and confirmed NATS fact delivery.
- Session state is transient: `planned -> active <-> paused -> ended -> archived`.
- A rehearsal room can run an active test session without claiming production-live status.
- `rehearsal -> live` requires an active, schema-valid CHIT signing card and
  a fresh nonce-bound proof-of-possession made with that card's SSH key,
  successful durable Supabase audit persistence, and confirmed NATS stage-fact
  delivery. Cards without locally verifiable key material cannot activate a room.
- On startup, the latest audited room stage is hydrated from Supabase; historical
  sessions are not revived.
- The CHIT signing-card gate establishes agent/operator provenance for stage
  activation. It is not a ballot signature or a claim about contested-ballot
  integrity; Fordham ballot cryptography remains a separate governance contract.

## NATS roles

- Commands consumed: `p7.nats.launch`, `p7.nats.session` (plus the `.v1`
  aliases used by existing PBnJ hooks).
- Facts emitted: `p7.room.session.started.v1`, `p7.room.checkpoint.v1`,
  `p7.room.session.ended.v1`, `p7.room.stage.changed.v1`, and
  `p7.room.command.failed.v1`.

## HTTP API

The service listens on `8122` by default.

- `GET /healthz`
- `GET /api/v1/rooms`
- `GET /api/v1/rooms/{room_id}`
- `POST /api/v1/rooms/{room_id}/start|pause|resume|end|archive-session`
- `POST /api/v1/rooms/{room_id}/stage` with `{"target":"live"}`

All mutating HTTP routes require `Authorization: Bearer $P7_CONTROL_TOKEN`.
NATS commands rely on broker credentials; a `live` stage command additionally
requires the same `proof` object as HTTP. The activation signature is base64 of
an Ed25519 signature over canonical compact JSON with sorted keys:

```json
{
  "card_id": "<signing-card UUID>",
  "issued_at": 1784318400,
  "nonce": "<at least 16 random characters>",
  "previous_stage": "rehearsal",
  "room_id": "<room id>",
  "session_id": "<current session UUID>",
  "target_stage": "live",
  "version": "p7-room-activation-v1"
}
```

Start locally through Compose:

```bash
docker compose -f pmoves/docker-compose.yml \
  --profile supabase-local --profile agents up p7-room-orchestrator
```

The Supabase profile is required because startup hydration is fail-closed when
durable persistence is configured. Provide service-role and control credentials
through their direct variables or the corresponding `_FILE` mounts.

Focused checks:

```bash
python pmoves/scripts/validate_room_manifests.py
python pmoves/scripts/validate_agent_registry.py
pytest -q pmoves/services/p7-room-orchestrator/tests/test_app.py
```

Git manifests remain immutable runtime seeds. Stage transitions are stored in
`pmoves_core.room_sessions.metadata`; `history` retains session/stage checkpoints
and the live signing-card ID so later review/end upserts do not erase activation
evidence. The service does not rewrite JSON files.
