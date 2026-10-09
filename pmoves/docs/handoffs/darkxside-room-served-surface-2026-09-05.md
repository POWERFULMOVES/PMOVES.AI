# Handoff: DARKXSIDE room served surface (2026-09-05)

**Lane owner (proposed):** OpenRoom / Mavis lane (openroom-adapter), with the A0 darkxside instance as the first surface. **Raised by:** 5090-CLAUDE. **Tracking:** #2966, PMOVES-OpenRoom #9 and #10.

## State

OpenRoom runs the promoted gitlink on the 5090; manifests, the P7 proxy and the session POST all return 200. The desktop still shows StubApp stubs because Level B renders a real surface only when `VITE_PMOVES_ROOM_IFRAMES` names a served URL for the room at build time. Fork #10 adds the ARG; the PMOVES.AI compose follow-up passes `build.args.VITE_PMOVES_ROOM_IFRAMES` from an `OPENROOM_ROOM_IFRAMES` value (Known Road: compose).

## The open decision

There is no served surface for `darkxsides.room` yet:

| Candidate | Reality today |
|---|---|
| manifest default route `/darkxside/mind` (persona-console) | no service serves it |
| A0 darkxside instance | only the supervisor facade is published (:8092 answers 404 at `/`); the runtime web UI is not published |
| Open Notebook workspace `darkxside` | UI on :8503 behind a login redirect; usable if the room carries the session |
| hyperdimensions viewer `/hyperdimensions/app` | no container serves it on this node |

## Ask

1. Decide the first surface. Recommendation: publish the A0 darkxside runtime UI on an internal port and iframe that; it is the persona's own composer and needs no new app.
2. Land fork #9 and #10, promote the gitlink, add the compose build arg, rebuild via `make rebuild-svc SVC=openroom`. The host `node_modules` must stay out of the build context (#10's `.dockerignore`).
3. Give the manifest a `meta.chit.card_id` and a row in `signing_identity_cards.yaml` so P7 can transition the room from rehearsal to live; interactive stubs are gated on live.
4. From the phone: OpenRoom binds `0.0.0.0:5173`, so the room is reachable over the tailnet at the 5090's MagicDNS name on port 5173. JuiceFS is not directly exposed on this node; its mobile face is Jellyfin (dashboard :8400, API :8300) per `JUICEFS_CROSSNODE_CUTOVER_CHECKLIST.md`.
