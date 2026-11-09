# nats_event_bus

HTTP-fronted event bus for the **slice-3** NATS pipeline of the
creator-collab lane. The bridge between producers (pinokio_bridge,
notebook-workbench, comfy-watcher, P7) and the dashboard / helpdesk
consumers, with a per-topic in-memory ring buffer for cheap reads.

## Why this exists

The slice-3 subjects (`comfy.collab.{prompt,progress,artifact}.v1`,
`room.presence.v1`, `room.directory.v1`) need a uniform read surface
so the room sidebar, dashboard, and the future helpdesk / room-suggest
skills can answer "what's happening in this room right now?" without
holding a NATS subscription each. This service is the small
projection that lets HTTP-only consumers read the recent stream.

## Endpoints

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `GET` | `/healthz` | open | Service health + topic list + writes/nats state |
| `GET` | `/v1/topics` | open | List configured topics (the 5 slice-3 subjects) |
| `GET` | `/v1/events/{topic}?since=<ts>&limit=<N>` | open | Recent envelopes for a topic (1-200, default 50) |
| `POST` | `/v1/publish` | `X-PMOVES-NatsBus-Token` | Publish a validated envelope |
| `GET` | `/v1/snapshot/room-directory` | open | Most recent `room.directory.v1` envelope |
| `GET` | `/v1/presence/{room_id}?limit=<N>` | open | Recent presence events for a room |

## Auth

The service is **fail-closed** for writes, same pattern as
`pinokio_bridge`. If `NATS_EVENT_BUS_TOKEN` is unset on the service
side, all `POST /v1/publish` requests return 503 with a clear error
pointing the operator at the env var. When set, requests must carry
a matching `X-PMOVES-NatsBus-Token` header. Reads are open.

This means the bus token is **separate** from the bridge token. A
compromise of one does not imply compromise of the other.

## Config

| Env var | Default | Purpose |
|---|---|---|
| `NATS_EVENT_BUS_PORT` | `8131` | HTTP listen port |
| `NATS_EVENT_BUS_HOST` | `127.0.0.1` | HTTP listen host |
| `NATS_EVENT_BUS_TOKEN` | (unset) | Fail-closed write token |
| `NATS_URL` | (unset) | If set, the optional subscriber connects here |
| `NATS_EVENT_BUS_DISABLE_SUBSCRIBER` | `false` | Skip the NATS subscriber at startup |
| `PMOVES_CONTRACTS_DIR` | `/app/contracts` | Where schemas + topics.json live |

When `NATS_URL` is unset (the default in dev), the service still
works for `POST /v1/publish` and `GET /v1/events/{topic}` — it just
doesn't fill the cache from external publishers. The cache is always
populated by events the service itself received via `POST`, plus any
events the optional subscriber observes.

## Subscriber behavior

If `NATS_URL` is set, the service starts a background task that
connects to NATS, subscribes to all configured topics, and pumps
incoming messages into the in-memory cache. The subscriber is
**best-effort**: a failed connection (NATS down, network partition)
just means the cache stays empty until either the bus is back up or
a producer POSTs an event directly. The HTTP surface is unaffected.

## Integration with pinokio_bridge

When `pinokio_bridge` is configured with `NATS_EVENT_BUS_URL`, every
successful app launch fires a `room.presence.v1` event with
`actor_kind=service`, `actor=pinokio_bridge:<slug>`, `action=active`.
The POST is best-effort (a down bus does NOT fail the launch) and
carries an `actor_metadata` block with the process pid and the
launch script for debugging.

This is the first concrete wire-up of the slice-3 pipeline end-to-end:
operator runs `pterm run comfyui-desktop/start.js` → pinokio_bridge
launches it → bus sees a presence event → room sidebar (in a future
slice) can render "comfyui-desktop is now running in creator-studio".

## Schema validation

Every POST is validated against the topic's JSON Schema (resolved via
`pmoves/contracts/topics.json`). The schemas are `additionalProperties:
false` at every level, so a producer cannot smuggle extra fields
through the bus. The validation error is surfaced as a 422 with the
underlying message so the producer can fix the payload.

## Tests

```bash
cd pmoves/services/nats_event_bus
python -m pytest tests/ -q
```

20 tests cover: health, topic listing, write auth (503/401/200),
schema validation (422), unknown topics (404), publish-then-read,
limit clamping, snapshot latest, presence filtering, auto-registration
of new topics, subscriber disabled without `NATS_URL`, subscriber
default topic inheritance, and `PublishRequest` pydantic surface.

The tests do NOT require a live NATS connection — the subscriber is
disabled by passing `subscriber=None` into `create_app()`.
