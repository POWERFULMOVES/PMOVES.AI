# Helpdesk + Room Suggest — Slice 6 Spec

> **Status:** Slice 6 SHIPPED on `feat/creator-collab-lane`. 5/7 slices
> complete. Companion to the slice-1 spec
> `pmoves/docs/specs/creator-collab-room-extensions-2026-07-27.md`
> (which defined `room_purpose: intake` + `creator_surface: ambient` as
> the missing axes the helpdesk needs), the slice-3 spec's NATS
> pipeline section, and the slice-4 spec's pinokio-apps registry.

## 1. Why slice 6

The slice-1 review-iter cycle-2 review of PR #2264 explicitly flagged
that `room_purpose` + `creator_surface` are meaningless without
**intake rooms** that use them. The slice-1 spec enumerated the
2-axis model (room_purpose × creator_surface) and said the
`intake` × `ambient` quadrant was the missing one — "a helpdesk that
asks 'how can PMOVES help me today?' and routes me to the right
room".

Slices 1+2+3+4 shipped:
- (1) the schema fields + first consumer (`creator-studio.room.collab.json`)
- (2) the `pinokio_bridge` service that reads Pinokio's on-disk state
- (3) the NATS pipeline (5 new subjects incl. `room.directory.v1` +
      `room.presence.v1` — slice 3 already reserved `room-suggest-skill`
      + `pmoves-helpdesk-skill` as subscribers)
- (4) the pinokio-apps registry (12 curated entries) + `mesh_exposure`
      service + `gepeto-wrapper` skill + 4 layer-TAC trees

What was missing: **the intake room itself** + **the 2 skills that
populate it**. Slice 6 ships:
- `pmoves.room.helpdesk` — the first `room_purpose: intake` +
  `creator_surface: ambient` room manifest
- `pmoves-helpdesk-skill` — the concierge (intake state, accept/reject,
  notebook writeback, mesh-render handoff)
- `room-suggest-skill` — the persona-aware ranker (pure function,
  cached, easy to test)
- 3 new NATS subjects (`helpdesk.intake.opened.v1`,
  `helpdesk.intake.routed.v1`, `helpdesk.room.suggested.v1`) +
  their Draft 2020-12 schemas
- A frontmatter smoke-test suite for `pmoves/skills/*/SKILL.md`
  (10 tests, stdlib + pyyaml only)

## 2. The 2-axis model, completed

Slice 1 enumerated these axes:
- `room_purpose`: community / control / studio / operator / classroom /
  field / showroom / **intake** / exchange / custom
- `creator_surface`: primary / **ambient** / background / off

Slice 1 shipped the `studio` × `primary` quadrant
(`creator-studio.room.collab.json`).

Slice 6 ships the **`intake` × `ambient`** quadrant
(`pmoves.room.helpdesk.json`). The helpdesk is the first room that
uses `intake` (the "who comes here and why" is "I have a question,
where do I go?") and the first room that uses `ambient` (small
"render this" button next to chat, no main panel — the helpdesk
routes, it doesn't render).

| Quadrant | Shipped | First consumer |
|---|---|---|
| `studio` × `primary` | slice 1 (PR #2264) | `creator-studio.room.collab` |
| `intake` × `ambient` | **slice 6 (this)** | **`pmoves.room.helpdesk`** |
| `community` × `primary` | pre-existing | `fordham.room.community` (CPU-only, primary) |
| `control` × `off` | pre-existing | `z890-infra.room.fabric` |

## 3. Helpdesk room manifest

`pmoves/config/rooms/pmoves.room.helpdesk.json`:
- `room_id: pmoves.room.helpdesk`
- `room_purpose: intake` (slice 1 — first consumer)
- `creator_surface: ambient` (slice 1 — first consumer; small
  "render this" overlay on chat, no main panel)
- `room_type: hybrid` (mix of operator intake + light builder when
  something needs rendering)
- `agent_id: pmoves-helpdesk-steward` (new persona; CHIT card 051,
  `00000000-0000-4000-8000-000000000051`, interim pending operator
  ssh-keygen)
- `access.visibility: unlisted` + `invite_list: [darkxside-persona,
  fordham-steward, creator-steward, 5090-claude, 4090-claude,
  z890-claude, pmoves-helpdesk-steward]` — intake rooms are private
  to invited members + the 6 fleet agent personas
- `hardware_requirements: { gpu: false, min_vram_mb: 0,
  node_roles: [infra-coordinator] }` — CPU-only, runs on the
  z890 infra-coordinator node. (z890 has a 3090ti, but the helpdesk
  is CPU-only by design: it routes, it doesn't render. The VRAM is
  reserved for the creator fleet.)
- `pinokio_app_refs: [{ slug: comfyui-desktop, role: primary,
  gpu_reservation_mb: 0, autostart: false }]` — the helpdesk has a
  reference to comfyui-desktop so the ambient mesh-render handoff
  can route to creator-studio. `autostart: false` because the
  helpdesk doesn't bring it up itself; creator-studio does.
- 4 `skill_bindings`:
  1. `helpdesk-intake` (pmoves-helpdesk-skill, ambient,
     no selection) — the concierge
  2. `room-suggest` (room-suggest-skill, ambient, no selection) —
     the ranker
  3. `ambient-mesh-render` (pinokio-bridge-skill, ambient, no
     selection) — the handoff to creator-studio when the visitor
     says "render this"
  4. `voice-suit-intake` (persona-bind, suggested, no selection) —
     the FlOO$ voice suit for Fordham elders
- 4 `apps`:
  1. `helpdesk-chat` (chat, active) — the main intake form
  2. `room-suggestions` (dashboard, active) — the ranker output panel
  3. `ambient-mesh-render` (browser, planned) — the small "render
     this" button + handoff
  4. `helpdesk-log` (custom, active) — intake trail + routing
     decisions + redirect counts
- `policies.publish.allowed_subjects` includes the 3 new `helpdesk.*`
  subjects + the slice-3 `comfy.collab.*` + `room.directory.v1` +
  `room.presence.v1` subjects (so the helpdesk can observe
  directory updates and emit collab handoffs)

## 4. The 2 skills

### 4.1 `pmoves-helpdesk-skill` (the concierge)

Bound by the helpdesk room's `helpdesk-intake` skill_binding
(`invocation_mode: ambient`, `requires_selection: false`).

Lives in `pmoves/skills/pmoves-helpdesk-skill/SKILL.md` (8.8 KB,
~280 lines).

What it does:
- Reads the latest `room.directory.v1` snapshot (slice 3) +
  the pinokio-apps registry (slice 4 curated/ + user/)
- Asks the visitor what they want (max 4 clarifying follow-ups,
  stops early if intent is unambiguous)
- Extracts intents ("render an image", "voice a script", "join a
  community pool", "log a dues payment", "build a dashboard")
- Maps intents → room capabilities (room.apps[*].capabilities,
  room.skill_bindings[*].intent, room.room_purpose)
- Ranks candidates:
  ```
  score = intent_match * 0.5
        + persona_affinity * 0.3
        + capability_coverage * 0.2
  ```
  - Filters: stage != 'archive', hardware_requirements satisfied
    by the visitor's node profile (or the default z890 for
    anonymous visitors)
- Proposes top 1-3 candidates with rationale
- On visitor accept (or 30s auto-route), emits
  `helpdesk.intake.routed.v1` with the chosen room_id + deep-link +
  intent_match block
- Writes the intake session to notebook (pmoves-helpdesk workspace,
  `threads/intake-sessions`) for the audit trail
- On "render this": emits `comfy.collab.prompt.v1` with
  `actor=pmoves-helpdesk` + deep-links to
  `/canvas/creator?from=helpdesk` (creator-studio picks up the
  prompt, runs the actual render on the 5090/Spark fleet node)

Why **ambient + CPU-only** by design:
- No node lock — the helpdesk doesn't steal VRAM from the
  creator fleet. A resident asking a question doesn't bump a
  5090 session.
- No UI lock — a resident can be in any room when they ask
  "wait, where do I do X?" — the helpdesk bound ambiently
  answers from the chat, then deep-links without forcing a
  navigation.

### 4.2 `room-suggest-skill` (the ranker)

Bound by the helpdesk room's `room-suggest` skill_binding
(`invocation_mode: ambient`, `requires_selection: false`).

Lives in `pmoves/skills/room-suggest-skill/SKILL.md` (8.7 KB,
~280 lines).

What it does:
- Pure, deterministic, no visitor state, no accept/reject
- Same data sources as `pmoves-helpdesk` (room directory +
  apps registry)
- Produces a ranked list of candidates (top 5) rather than a
  single routed answer
- Emits `helpdesk.room.suggested.v1` on every invocation
- Two invocation modes:
  - **ambient**: every chat turn in pmoves.room.helpdesk
    (a small "did you mean…?" panel)
  - **explicit**: the operator clicks the room-suggestions
    panel ("where should this go?") or the helpdesk needs
    to make a routing decision

Ranking:
```
score = intent_match * 0.4
      + persona_affinity * 0.3
      + capability_coverage * 0.2
      + recency_bonus * 0.1
```

The candidate shape matches the schema:
```json
{
  "room_id": "fordham.room.community",
  "score": 0.92,
  "rationale": "intents match the voice-suit-bind binding; ...",
  "matched_intents": ["voice", "read-out-loud", "elders"],
  "matched_capabilities": ["tts", "persona-suit", "spoken-summary"],
  "deep_link": "/dashboard/fordham?intent=voice&role=elder"
}
```

Why **two skills, one ranker** instead of one big skill:
- `room-suggest` is the *ranker* — pure, deterministic, no
  visitor state. Easy to test (snapshot input → ranked output),
  easy to call from anywhere.
- `pmoves-helpdesk` is the *concierge* — visitor state
  (intake session, follow-up count, accept/reject), emits the
  routed event, manages the notebook writeback, handles the
  mesh-render handoff.

The skill split is a copy-paste boundary, not a duplicated
ranker.

## 5. New NATS subjects (3)

| Subject | Schema | Emitter | Consumer |
|---|---|---|---|
| `helpdesk.intake.opened.v1` | `pmoves/contracts/schemas/helpdesk/helpdesk.intake.opened.v1.schema.json` | `pmoves-helpdesk-skill` (at session-open) | `nats_event_bus`, `dashboard`, `helpdesk-log` |
| `helpdesk.intake.routed.v1` | `pmoves/contracts/schemas/helpdesk/helpdesk.intake.routed.v1.schema.json` | `pmoves-helpdesk-skill` (after accept or 30s auto-route) | `nats_event_bus`, `dashboard`, `helpdesk-log`, `room-suggest-skill` |
| `helpdesk.room.suggested.v1` | `pmoves/contracts/schemas/helpdesk/helpdesk.room.suggested.v1.schema.json` | `room-suggest-skill` (every chat turn + explicit UI) | `nats_event_bus`, `room-suggestions`, `pmoves-helpdesk-skill`, `dashboard` |

All 3 are Draft 2020-12, `additionalProperties: false`, `format:uuid`
on the id fields, `format:date-time` on the timestamps. Topics count
goes from 96 (post slice 3) to **99** (post slice 6).

The slice-3 `room.directory.v1` + `room.presence.v1` already
reference `room-suggest-skill` + `pmoves-helpdesk-skill` as
subscribers (slice 3 reserved these names); slice 6 is the consumer
that fulfills them.

## 6. Frontmatter smoke tests

`pmoves/skills/tests/test_frontmatter.py` — 10 tests, stdlib + pyyaml
only (no FastAPI / httpx / fixtures needed).

What it locks:
- Every `pmoves/skills/*/SKILL.md` has valid YAML frontmatter
- Every frontmatter has `name` + `description`
- The `name` matches `[a-z0-9][a-z0-9-]*`
- The 2 slice-6 skills exist as directories under `pmoves/skills/`
- `pmoves-helpdesk-skill` documents the 2 helpdesk subjects it
  emits
- `room-suggest-skill` documents the 1 subject it emits
- Both skills reference `room.directory.v1` (slice 3 input) + the
  pinokio-apps registry (slice 4 input)
- `pmoves-helpdesk-skill` documents the ambient invocation mode

What it **doesn't** do (deliberate):
- A global "every skill_id resolves" check. Skills live in multiple
  places (`pmoves/skills/` newer convention + `.claude/skills/`
  older convention). A global resolver belongs in P7, not in a
  slice smoke test.

## 7. What slice 6 unblocks for slice 7

Slice 7 is the Fordham ↔ PMOVES-helpdesk E2E (full cross-room flow
+ visual evidence). With slice 6 in place:

- Fordham residents can land in `pmoves.room.helpdesk` (ambient
  + plain-spoken + voice-suit-bind for elders)
- The helpdesk reads `room.directory.v1` (slice 3) to know
  `fordham.room.community` exists
- The helpdesk reads the pinokio-apps registry (slice 4) to know
  which apps can do what
- The helpdesk ranks `fordham.room.community` at the top (community
  + resident persona affinity)
- The helpdesk emits `helpdesk.intake.routed.v1` with the Fordham
  deep-link
- The Fordham resident sees the suggestion in chat (or hears it
  via FlOO$ voice) + clicks → deep-link to Fordham
- All 4 NATS events land in `nats_event_bus` (slice 3) and show up
  in the dashboard
- The intake session is in notebook (pmoves-helpdesk workspace,
  threads/intake-sessions) for the audit trail
- If the resident says "render this" instead, the helpdesk emits
  `comfy.collab.prompt.v1` (actor=pmoves-helpdesk) and creator-studio
  picks it up + renders on 5090

The slice-7 E2E is the integration test: pinokio_bridge launches
comfyui-desktop → nats_event_bus sees `room.presence.v1` →
helpdesk room opens → Fordham resident lands → helpdesk routes to
Fordham room → Fordham room's `mesh-egress-ab` skill runs the
capacity A/B → writeback to notebook → dashboard.

## 8. Decisions

- **`room_purpose: intake` and `creator_surface: ambient` get their
  first consumer in slice 6.** The slice-1 spec said the
  `intake` × `ambient` quadrant was the missing one; slice 6
  ships it.
- **The helpdesk is a thin router, not a full creator surface.**
  CPU-only, ambient, no main panel. The helpdesk routes; creator-studio
  renders. This matches the slice-1 `creator_surface: ambient`
  definition.
- **Two skills, one ranker.** `room-suggest` is the pure
  function (testable, cacheable, callable from anywhere);
  `pmoves-helpdesk` is the concierge (visitor state, accept/reject,
  notebook writeback). The split is a copy-paste boundary, not
  a duplicated ranker.
- **3 helpdesk.* NATS subjects**, not 1. The split (intake.opened
  vs intake.routed vs room.suggested) lets the dashboard render
  intake traffic, routing outcomes, and candidate rankings
  separately, which is the shape the slice-7 E2E dashboard needs.
- **CHIT card 051** for the new `pmoves-helpdesk-steward` persona.
  Card 050 is `creator-steward`; 051 is the next free. Interim
  pending operator ssh-keygen, transition date 2026-08-15.
- **z890-coordinator stale profile acknowledged.** z890 has a
  3090ti 24GB but the helpdesk declares `gpu: false` — the
  helpdesk is CPU-only by design. The 3090ti is reserved for
  the creator fleet. The stale profile cache refresh is
  tracked in a separate cross-cutting follow-up.
- **No global "every skill_id resolves" check in the
  frontmatter test.** Skills live in multiple places; the
  global resolver belongs in P7.

## 9. Out of scope

- **NATS broker deployment.** The slice-3 schemas are ready and
  the slice-6 helpdesk emits to them. The actual broker deploy
  is a separate cross-cutting follow-up.
- **ComfyUI runtime smoke** (slice 5's job). Slice 6 ships
  the helpdesk that *routes* to creator-studio; the actual
  ComfyUI render is slice 5.
- **P7 global skill resolver.** Belongs in a follow-up
  P7 spec; not in slice 6.
- **`test_load_public_rooms_curates_real_manifests` failure**
  (z890 leak in fixtures) — pre-existing, separate concern.
- **`persona.room.livingdoc` em-dash catalog drift** — pre-existing
  out of scope per the cron constraints.

## 10. Cross-references

- `pmoves/docs/specs/creator-collab-room-extensions-2026-07-27.md` (slice 1)
- `pmoves/docs/specs/pinokio-apps-registry-2026-07-28.md` (slice 4)
- `pmoves/contracts/schemas/helpdesk/{helpdesk.intake.opened,helpdesk.intake.routed,helpdesk.room.suggested}.v1.schema.json`
- `pmoves/contracts/schemas/room/room.directory.v1.schema.json` (slice 3)
- `pmoves/configs/pinokio-apps/curated/*.yaml` (slice 4)
- `pmoves/skills/pinokio-bridge-skill/SKILL.md` (slice 2)
- `pmoves/skills/pmoves-helpdesk-skill/SKILL.md` (slice 6)
- `pmoves/skills/room-suggest-skill/SKILL.md` (slice 6)
- `pmoves/skills/tests/test_frontmatter.py` (slice 6)
- `pmoves/services/nats_event_bus/` (slice 3)
- `pmoves/config/rooms/pmoves.room.helpdesk.json` (slice 6)
- `pmoves/config/rooms/catalog.json` (+1 entry for helpdesk)
- `pmoves/tools/creator-collab-state.json` (ship_count 4 → 5)
- `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` (CLAIM entry for slice 6)
