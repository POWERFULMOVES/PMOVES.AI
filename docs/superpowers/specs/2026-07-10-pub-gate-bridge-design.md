# PR B — Pub-Gate → Publish Bridge (design)

**Date:** 2026-07-10
**Branch:** `feat/pub-gate-bridge`
**Depends on:** PR A (#2047, merged) — `publish_gate` is a first-class dimension of the provenance geometry state vector.
**Followed by:** PR C (queue salvaged reports as gate-closed items) · PR D (flute-translator plugs into the floor interface).

## 1. Purpose

Build the wire that turns a **geometry-plane gate-open** into a **real-world publish approval**, with a fail-closed **egress floor** on that wire. This is the load-bearing PR: it is the single point where autonomy meets the outside world, so the safety logic lives here, in one testable unit.

## 2. The two planes (why a bridge is needed)

PMOVES has two content planes that do not natively share a vocabulary:

- **Geometry / provenance plane** — the gateway already listens on `content.hirag.accepted.v1` and derives a geometry state vector (delta, kappa, hz, attribution, fitness, and now `publish_gate`). This plane describes the *shape of meaning*. It has no concept of a finished, publishable artifact.
- **Publish plane** — the `publisher` service waits on `content.publish.approved.v1`, whose schema **requires** `artifact_uri` (must match `^s3://`) and `title`. This plane is about a *finished thing going out the door* (Discord, Jellyfin, etc.).

`publish_gate` is a knob on plane 1; the approval event lives on plane 2. **PR B is the bridge between them**, and the egress floor sits on the bridge.

## 3. Architecture (Option B — event-mediated bridge)

```
[any surface: notebook / tablet / CLI / /hyperdimensions]
        │  publishes (raw NATS, geometry bus)
        ▼
geometry.publish.gate.v1
   { artifact_uri(s3://…), title, namespace?, tags?, meta?, mode, approved_by }
        │
        ▼
┌─ gate_bridge (one dedicated subscriber, the #2048 pattern) ────────┐
│  1. floor = get_egress_floor(room_manifest)     ← pluggable        │
│  2. verdict = floor.check(item)                                     │
│       clean     → publish content.publish.approved.v1              │
│       not-clean → HOLD; publish rejection (no approval)            │
│  fail-closed: ANY error / missing field / floor unavailable → HOLD │
└─────────────────────────────────────────────────────────────────────┘
        │ (clean only)
        ▼
content.publish.approved.v1 { artifact_uri, title, …, approved_by }
        ▼
publisher.py (already subscribed) → publishes
```

**Why event-mediated (vs. a direct call or inline-on-stream):**
- Mirrors the already-reviewed #2048 shape: *governance event → one dedicated subscriber → real-world action*. Copying a shape that survived Codex review is the safest way to build the PR we agreed deserves care.
- Honors "any surface is a client onto the manifold" — notebook, tablet, CLI, `/hyperdimensions` all drive the same gate by publishing the same event. No surface gets a private back door around the floor.
- The gate event **carries the artifact descriptor inline**, so the bridge needs no queue/lookup. The queue of gate-closed items is PR C's job.
- Inline-on-`content.hirag.accepted` was rejected: that stream carries lexicon/provenance shapes, not `s3://` artifacts — an impedance mismatch.

## 4. Components (each small and independently testable)

### 4.1 `egress_floor.py` — the plug-point
- A `Floor` protocol: `check(item: dict) -> Verdict` where `Verdict = {clean: bool, tripped: list[str]}`.
- Default implementation **`BlockAndHoldFloor`**: detector only, never transforms. Reads the room manifest's `policies.publish.egress_redaction_floor.rules` and evaluates each against the item's descriptor + text.
- **Corrected rules for `darkxsides.room`** (operator correction 2026-07-10 — see §7):
  - `operator-pii-protected`
  - `collaborator-pii-protected` (e.g. shaela-private — adult collaborator)
  - `no-literal-lan-or-tailscale-ips`
  - (`kids-always-redacted` is **removed** from this room — minor safety is handled by room separation into P7 Playground, not by scanning an adults-only room.)
- Pure functions, no NATS, no I/O. This is where PR D's flute-translator registers as an alternate `Floor`.

### 4.2 `gate_bridge.py` — the dedicated subscriber
- Subscribes `geometry.publish.gate.v1`; for each event: run the floor; on `clean` publish exactly one conformant `content.publish.approved.v1`; on `not-clean` publish a rejection and emit nothing to the publish plane.
- **Best-effort, fail-fast, env-gated** (`PUBLISH_GATE_BRIDGE=1`); behavior-identical when unset; never crashes the gateway (mirrors #2048's `sign_trail` discipline).
- Uses the gateway's existing raw-NATS path (`geometry_bus.py`), not the shared `events.publish()` helper.

### 4.3 Contract registration
- New schema: `pmoves/contracts/schemas/geometry/publish.gate.v1.schema.json` — fields per §5, `additionalProperties: false` OK since we control emitters.
- New `topics.json` entry: `geometry.publish.gate.v1 → { schema: schemas/geometry/publish.gate.v1.schema.json }`.
- The emitted `content.publish.approved.v1` payload conforms to its existing schema field-for-field. That schema is **not** `additionalProperties:false`, so top-level `approved_by` is valid, and `publisher._extract_reviewer()` already reads it. **(The #2048 P2 lesson: never emit a payload a validating consumer would reject.)**

## 5. Payload shapes

**`geometry.publish.gate.v1`** (emitted by any surface, consumed by the bridge):
```json
{
  "artifact_uri": "s3://bucket/path/to/artifact",
  "title": "string",
  "namespace": "string (optional)",
  "tags": ["string (optional)"],
  "meta": { "optional": "object" },
  "mode": "manual | village-rules-auto",
  "approved_by": "operator surface identity"
}
```

**`content.publish.approved.v1`** (emitted by the bridge on a clean verdict) — existing contract:
- Required: `artifact_uri` (`^s3://`), `title`.
- Carried through: `namespace`, `tags`, `description`, `meta`, `studio_board_id`, plus top-level `approved_by`.

**Hold on not-clean** — default is **log-only** (structured log + a `publish_gate_held` metric), carrying `{ artifact_uri, title, tripped: [...], approved_by }`. Log-only is deliberate: it avoids introducing a *second* new subject/contract in the load-bearing PR. A dedicated `content.publish.rejected.v1` subject is a possible follow-up, not part of PR B.

## 6. Fail-closed invariant (the load-bearing rule)

The bridge emits `content.publish.approved.v1` **only** on a positive `clean` verdict. Any rule match, any exception, any missing required field, or an unavailable floor → **HOLD** (log-only, never approval). Opening the gate cannot bypass the floor: the floor runs *after* the gate event, on the wire, every time.

## 7. Precondition — manifest correction

Before/with implementation, correct `pmoves/config/rooms/darkxsides.room.json` → `policies.publish.egress_redaction_floor.rules` to the §4.1 list (drop `kids-always-redacted`, add `operator-pii-protected` / `collaborator-pii-protected`). This fixes a mis-scoped rule from #2042 and is the data the floor reads. Rationale captured in memory `p7-playground-room-separation`.

## 8. Testing (all offline — no NATS / GPU / Supabase)

**Floor unit tests:**
- operator-PII present → held; shaela/collaborator identifier → held; literal `192.168.x.x` / `100.64–127.x` → held; clean item → clean.
**Bridge tests:**
- clean verdict → exactly one conformant `content.publish.approved.v1`; not-clean → zero approvals + one hold log/metric; floor raises → zero approvals (fail-closed).
**Contract tests:**
- `geometry.publish.gate.v1` sample validates against its schema; the bridge's approval payload validates against `publish.approved.v1.schema.json`.
**Demo harness:** a `make gate-emit` / CLI publishing a test `geometry.publish.gate.v1` (the #2048 `sign_trail`-style demo).

## 9. Scope boundaries

- **PR B (this):** bridge + floor interface + `BlockAndHoldFloor` default + contract (schema + topics.json) + manifest correction + tests. **No queue, no transform.**
- **PR C:** seed gate-closed items (salvaged `pmoves-reports/*`) into the darkxside notebook; emit gate events for chosen items; retire `publish_batch1.sh`.
- **PR D:** flute-translator plugs into the `Floor` interface as a richer transformer.

## 10. Known-Road note (contract paths are gated)

`pmoves/contracts/schemas/` and `pmoves/contracts/` are readOnly gated paths (patterns.yaml). Adding the schema is covered by the `schema` Known-Road domain (it is a `.schema.json`); `topics.json` is **not** a `.schema.json`, so it needs either a domain-predicate extension or an operator out-of-band edit. The gateway publishes via **raw NATS** (not the shared `events.publish()` helper), so a missing `topics.json` entry does **not** raise `KeyError` locally — registration is for consumer correctness, giving latitude on sequencing but not an excuse to skip it. Resolve the Known Road before editing `topics.json`.

## 11. Verification checklist (before PR B merges)
- [ ] Floor + bridge + contract tests pass with `uv run --with pytest ...`.
- [ ] Manifest correction applied and room manifest re-validates against `room.manifest.v1.schema.json`.
- [ ] `geometry.publish.gate.v1` registered (schema + topics.json) via a recorded Known Road.
- [ ] Bridge is env-gated and behavior-identical when `PUBLISH_GATE_BRIDGE` is unset.
- [ ] Codex/CodeRabbit threads triaged (expect a re-check of schema conformance — the #2048/#2047 P2 pattern).
