# P7 Room-Aware Stage Manager

FastAPI service that mediates the room lifecycle (rehearsal → live → review
→ archive) per the rooms-on-a-stage model. Aligned to the spec at
[`pmoves/docs/specs/p7-service-spec-2026-07-20.md`](../../docs/specs/p7-service-spec-2026-07-20.md).

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET  | `/healthz` | service + catalog + NATS health |
| GET  | `/api/p7/rooms` | list rooms (catalog rows) |
| GET  | `/api/p7/rooms/{room_id}` | room detail (catalog row + validated manifest) |
| POST | `/api/p7/rooms/{room_id}/transition` | state-machine transition (gated rehearsal→live) |
| POST | `/api/p7/reload` | force re-read of catalog from disk |

Default port: **8120** (override with `P7_HTTP_PORT`).

## State machine

```
rehearsal ──► live ──► review ──► archive
                │        │
                └────────┴──► (any of: review, archive)
```

| from → to | Gated? | Notes |
|---|---|---|
| `rehearsal → live` | **YES** (full CHIT checklist) | the only gated transition |
| `live → review` | no | audit pause |
| `live → archive` | no | retire |
| `review → live` | no | promote back |
| `review → archive` | no | retire from review |
| same → same | n/a | idempotent no-op |
| `archive → *` | rejected (409) | terminal |

## CHIT activation checklist (rehearsal → live only)

See the canonical list in
[`pmoves/docs/ROOM_MANIFEST_CONTRACT.md`](../../docs/ROOM_MANIFEST_CONTRACT.md)
§ "CHIT Signing-Card Activation Checklist". P7 implements all 7 items and
returns `422` with the unchecked items in the response body if any fail.

## NATS subjects (signed envelopes)

| Subject | When | Payload |
|---|---|---|
| `p7.nats.launch` | reserved (room entered) | `{room_id, agent_id, alter, overlay, ...}` |
| `p7.nats.session` | reserved (session opened/closed) | `{room_id, session_id, action, ...}` |
| `room.session.updated.v1` | on every stage transition | `{room_id, previous_stage, new_stage, reason, requester, ...}` |
| `pmoves.config.rooms.reloaded.v1` | on startup + `/api/p7/reload` | `{schema_version, rooms_loaded, ...}` |

Every payload has a `chit: {kid, ts, status, signature}` block. If P7 is
configured with `P7_SERVICE_CARD_ID` + `P7_SIGNING_KEY`, signatures are
HMAC-SHA256. If unset, status is `unsigned-local` per
`pmoves/.claude/BOOTSTRAP.md` § "Signing is optional locally".

## Configuration (env vars, all `P7_`-prefixed)

| Var | Default | Notes |
|---|---|---|
| `P7_NATS_URL` | `nats://nats:4222` | NATS endpoint |
| `P7_ROOM_CATALOG_PATH` | `pmoves/config/rooms/catalog.json` | path to catalog |
| `P7_ROOMS_DIR` | `pmoves/config/rooms` | dir containing per-room manifests |
| `P7_ROOM_MANIFEST_SCHEMA` | `pmoves/contracts/schemas/room/room.manifest.v1.schema.json` | schema for manifest validation |
| `P7_SIGNING_CARDS_PATH` | `pmoves/config/signing_identity_cards.yaml` | CHIT signing card registry |
| `P7_AGENT_REGISTRY_PATH` | `pmoves/config/agent_registry.yaml` | server registry for mcp_servers/a2a_servers |
| `P7_HTTP_PORT` | `8120` | FastAPI port |
| `P7_PMOVES_ROOT` | `.` (cwd) | root for resolving relative paths |
| `P7_SERVICE_CARD_ID` | (empty) | P7's own signing card UUID; empty = unsigned-local |
| `P7_SIGNING_KEY` | (empty) | HMAC key for P7's own envelopes; empty = unsigned-local |
| `P7_CHIT_REQUIRE_SIGNATURE` | `true` | fail-closed if transitions are unsigned |
| `P7_ALLOW_UNSIGNED_LOCAL` | `true` | operator-acknowledged unsigned-local advisory is OK |
| `P7_LOG_LEVEL` | `INFO` | |

## Local development

```bash
cd pmoves/services/p7-room-orchestrator
pip install -r requirements.txt
P7_PMOVES_ROOT=../../.. python main.py
# → http://localhost:8120/healthz
```

## Container

```bash
docker build -t pmoves-p7 pmoves/services/p7-room-orchestrator
docker run --rm -p 8120:8120 \
  -v $PWD/pmoves/config/rooms:/etc/pmoves/rooms:ro \
  -e P7_PMOVES_ROOT=/etc/pmoves \
  -e P7_ROOM_CATALOG_PATH=/etc/pmoves/rooms/catalog.json \
  -e P7_ROOMS_DIR=/etc/pmoves/rooms \
  -e NATS_URL=nats://host.docker.internal:4222 \
  pmoves-p7
```

## Tests

```bash
cd pmoves/services/p7-room-orchestrator
P7_PMOVES_ROOT=../../.. pytest tests/ -v
```

The tests are hermetic — they write a temp catalog + signing_cards + agent
registry, exercise the engine + endpoints, and clean up.

## Operator runbook

- **First-time setup**: set `P7_SERVICE_CARD_ID` to a real signing-card UUID
  from `pmoves/config/signing_identity_cards.yaml` and `P7_SIGNING_KEY` to
  the matching HMAC secret. Until then, transitions are `unsigned-local`
  (P7 logs this every transition; the CHIT checklist item 4 still passes
  because `P7_ALLOW_UNSIGNED_LOCAL=true` by default).
- **Transition a room to live**:
  ```bash
  curl -X POST http://localhost:8120/api/p7/rooms/z890-infra.room.fabric/transition \
    -H "Content-Type: application/json" \
    -d '{"target_stage":"live","reason":"operator approval","requester":"DARKXSIDE"}'
  ```
- **Reload catalog after manual edit**:
  ```bash
  curl -X POST http://localhost:8120/api/p7/reload
  ```
- **Audit transitions**: subscribe to `room.session.updated.v1` on NATS. The
  `chit.status` field tells you whether the envelope is signed or
  `unsigned-local`.

## Cross-references

- Spec: [`p7-service-spec-2026-07-20.md`](../../docs/specs/p7-service-spec-2026-07-20.md)
- Rooms model: [`ROOMS_ON_A_STAGE.md`](../../docs/ROOMS_ON_A_STAGE.md)
- Manifest contract: [`ROOM_MANIFEST_CONTRACT.md`](../../docs/ROOM_MANIFEST_CONTRACT.md)
- Catalog: [`catalog.json`](../../config/rooms/catalog.json)
- Schema: [`room.manifest.v1.schema.json`](../../contracts/schemas/room/room.manifest.v1.schema.json)
- Operator slash command: [`.claude/commands/p7/room.md`](../../../.claude/commands/p7/room.md)
- AGNOTE CLAIM/RELEASE: `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` (search "Mavis::OPEN-ROOM-LANE")
