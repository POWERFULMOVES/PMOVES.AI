# P7 Service Spec — Room-Aware Stage Manager Runtime

**Status:** DRAFT — pending operator signoff
**Lane:** Open Room Lane (Mavis, mvs_09c9b116c675418b9d8b1a48b10867dc)
**Branch (spec doc):** `feat-auto-20260720-8d27fc57` (provisional)
**Branch (code):** `feat/p7-runtime-slice` (proposed — to be created after spec signoff)
**Date:** 2026-07-20
**Companion spec:** [`room-manifest-schema-extensions-2026-07-20.md`](room-manifest-schema-extensions-2026-07-20.md) (must land first)

---

## 1. Goal

P7 (Pinokio 7) is the room-aware stage manager. The catalog (`pmoves/config/rooms/catalog.json`) and the room manifests exist, the schema is now validating all 9 rooms, and the `current_stage` field is exposed for fast lookup. What is missing is the **runtime**: a small service that knows the room topology, exposes a transition API, and publishes lifecycle events on NATS so downstream consumers (A2UI, agent-registry, observability) can react.

This spec defines that service. It is intentionally small: one Python file for the catalog loader, one for the transition logic, one for the NATS publisher, and a thin FastAPI app. ~300-400 lines total. No business logic, no skill execution, no model routing — P7 is *only* the stage manager.

## 2. Why this exists

Per `pmoves/docs/AGENTS/AGNOTE4482.md` §30-32 (P7 — Room-Aware Stage Manager):

> Pinokio 7 (P7) is the PMOVES runtime launcher and fleet orchestrator. In the rooms-on-a-stage model, P7 is not just a process spawner — it is the **room-aware stage manager**: it knows which rooms exist (via `pmoves/config/rooms/catalog.json`), selects the appropriate room profile for a given workload, and manages the transition between rehearsal → live → review → archive states. P7's NATS subjects (`p7.nats.launch`, `p7.nats.session`) are the control plane for room entry and lifecycle. When agents claim work via AGNOTE4482, P7 is the context they launch into.

Per `pmoves/docs/ROOMS_ON_A_STAGE.md` §56-65 (P7 — The Stage Manager):

> P7 (Pinokio 7) is the room-aware stage manager. It:
> 1. Knows which rooms exist (via `pmoves/config/rooms/catalog.json`)
> 2. Selects the appropriate room profile for a given workload
> 3. Loads the correct overlay for the room
> 4. Manages stage transitions (rehearsal → live → review → archive)
> 5. Provides NATS control plane subjects (`p7.nats.launch`, `p7.nats.session`) for room entry and lifecycle
>
> P7 is not just a process spawner — it is the context that agents launch into.

Both definitions describe a runtime service. Today, P7 is a **declarative concept** (catalog + manifests + NATS subjects) without an executable. This spec closes that gap.

## 3. Scope

### 3.1 In scope

- **Catalog loader** — read `pmoves/config/rooms/catalog.json` (schema v1.2.0+) at startup, cache in memory, refresh on `pmoves.config.rooms.reloaded.v1` NATS subject.
- **Manifest loader** — on demand, load `pmoves/config/rooms/{room_id}.json` and validate against `room.manifest.v1.schema.json`.
- **Stage transition API** — `POST /api/p7/rooms/{room_id}/transition` accepting `{target_stage: rehearsal|live|review|archive, reason: string, requester: agent_id}`. Reads CHIT activation checklist from the canonical `ROOM_MANIFEST_CONTRACT.md`; refuses transition if any unchecked item exists.
- **Room query API** — `GET /api/p7/rooms` (list with current_stage), `GET /api/p7/rooms/{room_id}` (full manifest + current stage + transition history).
- **NATS publishers** — `p7.nats.launch` (room entered), `p7.nats.session` (room session opened/closed), `room.session.updated.v1` (stage changed), `pmoves.config.rooms.reloaded.v1` (config reloaded).
- **Healthcheck** — `GET /healthz` returning `{status: ok, rooms_loaded: N, nats_connected: bool}`.
- **CHIT signing** — every transition publishes a CHIT-signed payload on `room.session.updated.v1` (signed via `pmoves.tools.chit_security.sign_payload`).
- **Docker compose** — new `p7` service in `pmoves/docker-compose.yml` with healthcheck, NATS dependency, and the room manifest volume mounted read-only.
- **Make target** — `make -C pmoves up-p7` (mirrors `up-cipher`, `up-agents-published` patterns from BOOTSTRAP.md).
- **Unit tests** — pytest covering catalog load, manifest validation, transition gating, NATS payload shape.
- **Smoke test** — `make -C pmoves smoke-p7` boots the service, transitions `demo.room.rehearsal` from `rehearsal` → `live` (gated; should fail) and back (should succeed), asserts NATS publishes.

### 3.2 Out of scope (separate lanes)

- **Skill execution** — P7 doesn't run skills. The `skill_bindings[].execution` is consumed by agent-runtime / Agent Zero, not P7.
- **Model routing** — P7 doesn't select models. `policies.model_routing` is consumed by the model nexus layer.
- **Notebook state** — P7 doesn't read/write notebook. The `notebook` block is a reference for the agent runtime.
- **Overlay switching** — P7 doesn't switch overlays. The `overlays` (formerly "suits") concept is a runtime binding that the agent runtime consumes; P7 just records the currently-bound overlay in transition events.
- **CHIT signing key management** — P7 uses the existing `pmoves.tools.chit_security` module; it doesn't manage keys.

## 4. Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    P7 Service (FastAPI)                       │
│                                                              │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐    │
│  │   Catalog   │  │  Transition  │  │   NATS Publisher  │    │
│  │   Loader    │◄─┤   Engine     ├─►│   (signed events) │    │
│  │  (in-mem)   │  │  (gated)     │  │                   │    │
│  └──────┬──────┘  └──────┬───────┘  └────────┬──────────┘    │
│         │                │                   │               │
└─────────┼────────────────┼───────────────────┼───────────────┘
          │                │                   │
          ▼                ▼                   ▼
   pmoves/config/   CHIT activation      p7.nats.launch
   rooms/catalog    checklist gate       p7.nats.session
   .json +          (canonical doc +     room.session.updated.v1
   per-room         signing card         pmoves.config.rooms
   manifests        validation)          .reloaded.v1
```

## 5. File layout (proposed)

```
pmoves/services/p7/
├── __init__.py
├── main.py              # FastAPI app, ~100 lines
├── catalog.py           # CatalogLoader: load + cache + reload, ~80 lines
├── transition.py        # TransitionEngine: gate + execute, ~120 lines
├── nats_pub.py          # NATSPublisher: signed publish to control plane, ~80 lines
├── config.py            # Pydantic settings: NATS URL, catalog path, etc.
├── README.md            # Operator-facing quickstart
└── tests/
    ├── test_catalog.py
    ├── test_transition.py
    ├── test_nats_pub.py
    └── test_api.py

pmoves/tests/smoke/
└── test_p7_smoke.py     # Boots the service, runs scripted transitions
```

`pmoves/docker-compose.yml` adds:

```yaml
  p7:
    build: ./services/p7
    container_name: pmoves-p7
    restart: unless-stopped
    environment:
      - NATS_URL=nats://nats:4222
      - PMOVES_ROOMS_CATALOG=/etc/pmoves/rooms/catalog.json
      - PMOVES_ROOMS_DIR=/etc/pmoves/rooms
      - CHIT_REQUIRE_SIGNATURE=${CHIT_REQUIRE_SIGNATURE:-true}
    volumes:
      - ./config/rooms:/etc/pmoves/rooms:ro
      - ./services/p7:/app:ro
    ports:
      - "8120:8120"  # P7 HTTP API
    depends_on:
      nats:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8120/healthz"]
      interval: 30s
      timeout: 5s
      retries: 3
```

`pmoves/Makefile` adds:

```makefile
up-p7:
	docker compose -f pmoves/docker-compose.yml up -d p7
	$(MAKE) health-wait SERVICE=p7 PORT=8120

smoke-p7:
	pytest -q pmoves/tests/smoke/test_p7_smoke.py
```

## 6. NATS subject contract

All subjects already declared in `pmoves/docs/AGNOTE4482.md` §30-32 and `pmoves/docs/ROOMS_ON_A_STAGE.md` §56-65. This spec fixes the payload shapes.

### 6.1 `p7.nats.launch` (room entered)

```json
{
  "v": "1.0.0",
  "room_id": "demo.room.rehearsal",
  "agent_id": "4090-claude",
  "alter": "4090-demo",
  "overlay": "agent-zero-local",
  "manifest_version": "1.0.0",
  "timestamp": "2026-07-20T18:00:00Z",
  "chit": { "card_id": "...", "signature": "..." }
}
```

### 6.2 `p7.nats.session` (room session opened/closed)

```json
{
  "v": "1.0.0",
  "room_id": "demo.room.rehearsal",
  "session_id": "uuid-v4",
  "action": "open|close|heartbeat",
  "agent_id": "4090-claude",
  "timestamp": "2026-07-20T18:00:00Z",
  "chit": { "card_id": "...", "signature": "..." }
}
```

### 6.3 `room.session.updated.v1` (stage changed) — already declared in room manifest telemetry

```json
{
  "v": "1.0.0",
  "room_id": "demo.room.rehearsal",
  "previous_stage": "rehearsal",
  "new_stage": "live",
  "reason": "operator approval per AGNOTE 2026-07-20",
  "requester": "Mavis",
  "timestamp": "2026-07-20T18:00:00Z",
  "chit": { "card_id": "...", "signature": "..." }
}
```

### 6.4 `pmoves.config.rooms.reloaded.v1` (catalog reloaded)

```json
{
  "v": "1.0.0",
  "schema_version": "1.2.0",
  "rooms_loaded": 9,
  "timestamp": "2026-07-20T18:00:00Z",
  "chit": { "card_id": "...", "signature": "..." }
}
```

## 7. Stage transition gate

`TransitionEngine.transition(room_id, target_stage, reason, requester)` MUST:

1. Load the room manifest.
2. If `current_stage == target_stage`, no-op (idempotent), return 200.
3. If `target_stage == "live"` and `current_stage != "rehearsal"`, reject (only rehearsal → live is valid; the others are review/archive from live).
4. If `target_stage == "live"`, run the CHIT activation checklist from `ROOM_MANIFEST_CONTRACT.md`:
   - `meta.chit.card_id` present OR skill supplies card at runtime
   - signing card validates against `signing-card.v1.schema.json` with `active: true`
   - signing-identity-cards.yaml has a matching row
   - `make sign-trail` returns signed OR unsigned-local explicitly accepted
   - `mcp_servers` / `a2a_servers` declared in manifest are present in agent_registry.yaml
   - `PGRST_DB_EXTRA_SEARCH_PATH` includes the room's schemas
   - `CHIT_REQUIRE_SIGNATURE` / `CHIT_DECRYPT_ANCHORS` documented for target topology
5. Update `catalog.json` row's `current_stage` (atomic write + reload publish).
6. Sign the `room.session.updated.v1` payload with `pmoves.tools.chit_security.sign_payload`.
7. Publish on `room.session.updated.v1`.
8. Return 200 with the signed payload.

If any checklist item fails, return 422 with the specific unchecked items in the response body.

## 8. Operational contract

- **Boot sequence**: P7 starts AFTER `nats` (compose dependency). On boot: load catalog, load all manifests, validate, publish `pmoves.config.rooms.reloaded.v1` with initial state.
- **Reload**: on `pmoves.config.rooms.reloaded.v1` (inbound), reload catalog from disk. Triggered by operator running `make rooms-reload` or by a file-watch on `pmoves/config/rooms/`.
- **Failure mode**: if NATS is unreachable on boot, P7 retries with exponential backoff (1s, 2s, 4s, ..., 60s cap). Healthcheck returns 503 until NATS is reachable. Catalog reads are local-file, so they work without NATS.
- **Observability**: structured JSON logs to stdout. Optional Prometheus metrics on `/metrics` (room count, transition count by from/to, transition latency, NATS publish latency, CHIT signing latency).

## 9. Open questions for operator

1. **Port 8120** — chosen to match the `agent-*` services (Agent Zero 8080, gateway 8082-ish, etc.). Confirm this doesn't collide.
2. **CHIT signing key** — does P7 use the same signing card as the room it serves, or does it have its own? Recommendation: own card (P7 is an infra service, not a room agent).
3. **Catalog write-back** — should P7 be the writer of `catalog.json` (atomic, single-writer) or should transitions go through an admin endpoint that the operator runs `make rooms-transition` to apply? Recommendation: P7 writes directly for the `current_stage` field only; full catalog edits still go through git.
4. **Backward compatibility** — A2UI DL-4.1 (`/stage/` page) was shipped 2026-07-12 by 5090-CLAUDE. It reads `pmoves/ui/lib/rooms.ts` and `isPublicRoom` rules, not P7 directly. P7 service adds a NEW dependency surface; A2UI is unchanged. Confirm.
5. **Worktree strategy** — code in `feat/p7-runtime-slice` (off main, per BOOTSTRAP.md fork-sync discipline). The spec doc is in the operator's auto worktree (`feat-auto-20260720-8d27fc57`). Should the spec PR be split out, or stay co-located with the code PR?

## 10. Signoff checklist (operator)

- [ ] Review the file layout (§5) and the docker-compose snippet.
- [ ] Confirm port 8120 (or pick another).
- [ ] Confirm CHIT signing key strategy (§9 Q2): P7's own card, or per-room card.
- [ ] Confirm catalog write-back strategy (§9 Q3): P7 writes `current_stage` directly, or admin endpoint only.
- [ ] Confirm A2UI backward compatibility (§9 Q4): P7 is additive; A2UI unchanged.
- [ ] Confirm worktree strategy (§9 Q5): spec + code in same PR (`feat/p7-runtime-slice`), or spec in one PR + code in another.
- [ ] Sign off on the NATS subject payload shapes (§6.1-6.4).
- [ ] Confirm the transition gate semantics (§7): rehearsal → live is the only gated path; review/archive from live is ungated.

## 11. References

- `pmoves/docs/AGENTS/AGNOTE4482.md` §30-32 (P7 definition)
- `pmoves/docs/ROOMS_ON_A_STAGE.md` §56-65 (P7 stage manager model)
- `pmoves/docs/ROOM_MANIFEST_CONTRACT.md` (room manifest + CHIT activation checklist)
- `pmoves/docs/specs/room-manifest-schema-extensions-2026-07-20.md` (companion spec — must land first)
- `pmoves/config/rooms/catalog.json` (schema v1.2.0)
- `pmoves/contracts/schemas/room/room.manifest.v1.schema.json`
- `pmoves/contracts/schemas/identity/signing-card.v1.schema.json`
- `pmoves/tools/chit_security.py` (signing module P7 uses)
- `.claude/BOOTSTRAP.md` (Known Roads: `up-cipher` / `up-agents-published` patterns)
- Open Room Lane CLAIM (AGNOTE4482PHI.t1.md, 2026-07-20T17:59:39Z, GRAPHITI_MARK `Mavis::OPEN-ROOM-LANE-CLAIM::2026-07-20`)
