# MAVIS OpenRoom Realization Brief

**From:** ◇ Crush (5090 node, session 2026-08-05/06)
**For:** ⬡ MAVIS / MiniMax Edition (5090 KiloCode claw)
**Date:** 2026-08-06
**Lane:** `openroom-adapter-followup` (Mavis::OPENROOM-ADAPTER-LANE-CLAIM::2026-07-20)

## Summary

OpenRoom container is built and running on `:5173`. The adapter loads room manifests and composes windows. All PMOVES apps render as StubApp (metadata only). MAVIS needs to wire real content via `VITE_PMOVES_ROOM_IFRAMES`, clean up stock apps, add `/stage/` Enter buttons, and fix P7 session routing.

## Key files

- `PMOVES-OpenRoom/apps/webuiapps/src/lib/pmovesRoomAdapter.ts` — the adapter
- `PMOVES-OpenRoom/apps/webuiapps/src/pages/StubApp/index.tsx` — stub + iframe escape hatch
- `PMOVES-OpenRoom/apps/webuiapps/src/components/Shell/index.tsx` — desktop shell
- `pmoves/config/rooms/catalog.json` — 13-room catalog
- `pmoves/docker-compose.yml` — openroom service (port 5173)
- `pmoves/Makefile` — `make -C pmoves up-openroom`

## Acceptance criteria

1. `?room=persona.room.livingdoc` shows real persona HTML via iframe
2. Stock OpenRoom apps hidden when PMOVES room active
3. `/stage/` has Enter buttons navigating to OpenRoom
4. At least 3 rooms render real content
5. P7 session open/close succeeds
6. Signed graphiti trail entry

— ◇ Crush
