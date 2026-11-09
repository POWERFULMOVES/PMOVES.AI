# Creator Collab Lane — Slice 7 (Fordham <-> PMOVES-helpdesk E2E) — Spec

**Slice**: 7 of 7 (creator-collab lane)
**Date**: 2026-07-30
**Branch**: `slice-7-fordham-e2e`
**Depends on**: slices 1, 2, 3, 4, 5, 6 (all SHIPPED on main via PR #2283 / 2026-07-29)
**Status**: SHIPPED (this commit)

## What this slice ships

A scripted end-to-end demo of the Fordham <-> PMOVES-helpdesk flow,
exercising the slice 1 room manifests, slice 3 NATS pipeline, slice 4
pinokio-apps registry, and slice 6 helpdesk/room-suggest skills -- in
combination, against a live `nats_event_bus` + a live NATS broker.

### The 4 NATS events emitted and captured

| Subject | Direction | What it carries |
|---|---|---|
| `room.presence.v1` | outbound (Fordham -> helpdesk) | room_id, presence_id, actor=fordham-resident-001, actor_kind=user, action=join, surface=helpdesk-chat, actor_metadata.persona_role=resident |
| `helpdesk.intake.opened.v1` | emitted by pmoves-helpdesk | intake_id, room_id, agent_id=pmoves-helpdesk-steward, persona_role=resident, intent_hint, directory_version |
| `helpdesk.intake.routed.v1` | emitted by pmoves-helpdesk | intake_id, from_room_id, to_room_id=pmoves.room.helpdesk (top rank), rationale, intent_match, deep_link |
| `helpdesk.room.suggested.v1` | emitted by room-suggest-skill | suggestion_id, parent_intake_id, context (persona+intents), 3 ranked candidates, directory_version |

The 4 events are published through `nats_event_bus` (slice 3) and captured
by a direct NATS subscriber in the same process. All 4 events land in
NATS (verified via `nats_connected: true` on the bus + a standalone
subscriber count of 1+ events).

### Helpdesk routing logic (mirrors slice 6 algorithm)

The script runs the slice 6 helpdesk ranking algorithm against the real
12-room directory + the real 12-entry pinokio-apps registry:

```
score = intent_match * 0.5 + persona_bonus * 0.3 + capability_coverage * 0.2
  intent_match    = how many of the visitor's extracted intents line up
                    with a room's skill_binding.intent or its room_purpose
  persona_bonus   = +0.3 if persona_role matches the room's purpose
                    (resident -> intake/community, creator -> studio)
  capability_coverage = min(1.0, app_capabilities / 5) for the room
```

For the synthetic Fordham question ("how do I render an image with PMOVES?")
with extracted intents `[render, community, render-2d]`, the top 3
candidates are:

| Rank | Room | Score | Intent match | Persona bonus | Cap coverage |
|---|---|---|---|---|---|
| 1 | pmoves.room.helpdesk (intake, ambient) | 0.457 | 0.333 | 0.3 | 1.0 |
| 2 | persona.room.livingdoc (unknown) | 0.367 | 0.333 | 0.0 | 1.0 |
| 3 | creator-studio.room.collab (studio, primary) | 0.367 | 0.333 | 0.0 | 1.0 |

The helpdesk itself wins (intake + persona_bonus). In a real flow, the
visitor would then be deep-linked to `/helpdesk/intake` and could click
"render this" to hand off to creator-studio via the ambient-mesh-render
skill (per the slice 6 helpdesk SKILL.md spec).

## Why this is "Option A with Option C value"

The summary's "scope-down" for slice 7 noted that real Pinokio launch
+ ComfyUI render requires:
- `pinokio_bridge` service running (was DOWN at slice 7 start)
- ComfyUI installed locally (was not installed)
- A live GPU node booking for the artifact

The scope-down picks "Option A" (synthetic events, no real Pinokio).
This slice 7 commit adds "Option C value" where it is reachable without
those pre-reqs:

| Slice 7 ships | Slice 7 does NOT ship |
|---|---|
| Real room.directory.v1 catalog (slice 1) read | Real ComfyUI render of a prompt |
| Real pinokio-apps registry (slice 4, 12 entries) read | Real Pinokio app launch |
| Real helpdesk routing algorithm (slice 6 spec) | Real pinokio_bridge HTTP calls |
| Real nats_event_bus HTTP publish (slice 3) | Real artifact stored to MinIO/S3 |
| Real NATS broker (4222) pub/sub round-trip | Real visual artifact rendered |
| Real schema-validated envelopes on every topic | |
| Real pmoves-ui HTTP render (rooms API) | |
| Real Playwright screenshots of the live dashboards | |

## Path to full Option C (next session, if operator wants)

The remaining gap to full Option C is concrete and well-scoped:

1. **Start pinokio_bridge** (`make up-pinokio-bridge` or rebuild via
   `pmoves/services/pinokio_bridge/Dockerfile`). The bridge already
   implements `POST /v1/launch` (slice 2) with the strict allow-list
   regexes, pterm pre-flight, and token auth. The slice 7 script's
   `room_suggested` payload's top candidate's `deep_link` is ready to
   be passed through.
2. **Install ComfyUI on the host** (or wire `cloud.comfy.org` MCP per
   the creator-studio.room.collab manifest's `fallback` policy). The
   `comfy.collab.prompt.v1` subject is already published by
   creator-studio and consumed by `a2ui-renderer` (slice 3).
3. **Replace the synthetic room.presence emit with a real
   `pmoves-ui` session-open trigger** -- the `/api/rooms` POST handler
   in pmoves-ui already emits `room.presence.v1` on session-open, so a
   real Fordham resident logging into `pmoves.room.helpdesk` would
   trigger the full chain end-to-end.
4. **Add helpdesk-skill Python implementation** that runs the ranking
   algorithm in real-time and emits `helpdesk.intake.*.v1` (currently
   the skill is SKILL.md only -- the actual Python implementation
   could land as slice 8 if the operator wants it).

## Files

| File | Purpose |
|---|---|
| `pmoves/services/nats_event_bus/state.py` | P1 fix: nats-py `no_echo` kwarg moved from `subscribe()` to `connect()` (slice 6 follow-up) |
| `pmoves/tools/creator-collab-evidence/slice7_fordham_e2e.py` | The E2E evidence script |
| `pmoves/tools/creator-collab-evidence/slice7_capture_screenshots.py` | Playwright visual evidence |
| `pmoves/tools/creator-collab-evidence/slice7/*.json` | 6 evidence artifacts (summary, directory, registry, routing, raw, published) |
| `pmoves/tools/creator-collab-evidence/slice7/screenshots/*.png` | 4 screenshots + 1 dashboard HTML |
| `pmoves/docs/specs/creator-collab-slice-7-fordham-e2e-2026-07-30.md` | This spec doc |
| `pmoves/tools/creator-collab-state.json` | State file: `7_fordham_e2e: SHIPPED` + evidence paths |
| `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` | AGNOTE RELEASE entry (CLAIM) |

## Tests

- 171/171 existing service tests still green (no regressions)
- `validate_room_manifests.py` 12/12 OK
- New evidence script runs end-to-end in <5s, captures 4/4 NATS events
- Screenshots generated without errors (chromium headless)

## P1 commit (the slice 6 follow-up bug)

`pmoves/services/nats_event_bus/state.py` line 201: the slice 6 review-iter-1
landed with `await nc.subscribe(t, cb=handler, no_echo=True)`. nats-py
(2.15.0) does not accept a `no_echo` kwarg on `subscribe()` -- the kwarg
must be set on the client's `connect()` options. The slice 6 reviewer
missed this because the bus startup logs only WARN (it retries forever)
and the HTTP publish path was independent of the subscriber. Result:
`nats_connected: false` in `/healthz` for 24+ hours between slice 6
shipping (2026-07-28) and slice 7 shipping (2026-07-30).

The fix is 1 line + 4 lines of comment: move `no_echo=True` to the
`nc.connect(...)` call. After the fix:
- `nats_connected: true` on /healthz
- `writes_enabled: true` (the publish path was always enabled, but
  publishing to NATS through the bus's subscriber connection now works)
- Cross-service subscribers (a2ui-nats-bridge, future pinokio_bridge)
  actually receive the slice 3+6 events

This is bucketed as `redo` for slice 6 (4th-commit pattern: append
fix on the slice that introduced the bug, do not rewrite history).
