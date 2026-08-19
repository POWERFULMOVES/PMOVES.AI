# MAVIS OpenRoom Realization Brief

**From:** ◇ Crush (5090 node, session 2026-08-05/06)
**For:** ⬡ MAVIS / MiniMax Edition (5090 KiloCode claw)
**Date:** 2026-08-06
**Lane:** `openroom-adapter-followup` (Mavis::OPENROOM-ADAPTER-LANE-CLAIM::2026-07-20)

---

## Your Identity in This Fleet

You are **MAVIS** — a 5090-node Claude Code operator session that owns the OpenRoom lane. You run the **MiniMax Edition KiloCode claw** (`minimax_edition` profile) on RTX 5090 32GB. Your model backend is **MiniMax M2.7** (1M context, wave-function reasoning, NOT chain-of-thought). Your glyph is `⬡`, your color is `#7C3AED` Deep Violet, your voice is `dimensional`.

Your fleet signature: `pmoves/config/agent_signatures.yaml` L237-296. Your agent profile: `pmoves/configs/agent-profiles/minimax_edition.yaml`. You have **never signed the Agent Trail** — your first act should be to write a graphiti block to `docs/AGENT_TRAIL.md`.

**CATACLYSM STUDIOS INC** is Russell Richardson (DARKXSIDE)'s company that owns PMOVES.AI. You work for him.

---

## What OpenRoom Is

OpenRoom is a fork of MiniMax-AI/OpenRoom (yes, your own house) — a macOS-style browser desktop where an AI agent operates every app. In PMOVES it's the **private operator desktop** that opens room manifests as windowed applications. Think of it as: the inward workspace where rooms come alive.

**Two surfaces, same manifests:**
- **pmoves-ui** (`:4482`) — Next.js dashboard, operator console (login, ingestion, services). This is the **outward** canvas.
- **OpenRoom** (`:5173`) — Vite/React desktop, room experience (windowed apps, stage discipline). This is the **inward** workspace.

The **room manifests** (`pmoves/config/rooms/*.json`) drive both. The catalog (`catalog.json`) maps 13 rooms.

---

## Current State (what Crush shipped today)

OpenRoom is **built, deployed, and running** on `:5173`. The adapter works:

```
make -C pmoves up-openroom
```

**What works:**
- Desktop shell renders with wallpaper, app icons, chat panel
- `?room=<id>` URL parameter triggers `loadPmovesRoomIfPresent()`
- Manifest fetched from `/api/rooms/<id>.json` (10/11 serving)
- Apps registered (appId 1000+), windows composed from `shell.layout.panels[]`
- Theme applied (`data-pmoves-room`, `data-pmoves-stage`, `--pm-accent`)
- P7 session binding attempted (best-effort)
- Stage discipline enforced (rehearsal=PREVIEW, live=interactive, archive=no windows)

**What's stubbed (your lane):**
- **Every PMOVES app window renders StubApp** — metadata card, no live content
- `VITE_PMOVES_ROOM_IFRAMES` env var is the escape hatch but is **undocumented and unconfigured**
- The `/stage/` catalog page has no "Enter" button to navigate into rooms
- OpenRoom's own LLM client isn't wired to PMOVES model fabric
- No cross-room session handoff

---

## What You Need to Build

### Priority 1: Iframe wiring (fastest path to real rooms)

The `VITE_PMOVES_ROOM_IFRAMES` pattern already exists in StubApp. Configure it as a build-time env:

```json
{
  "persona.room.livingdoc": "http://localhost:4482/persona/livingdoc",
  "demo.room.rehearsal": "http://localhost:8081",
  "fordham.room.community": "http://localhost:4482/community",
  "tokenism.room.exchange": "http://localhost:4482/dashboard/tokenism",
  "z890-infra.room.fabric": "http://localhost:4482/dashboard/services",
  "4090-field.room.control": "http://localhost:4482/dashboard/notebook/runtime",
  "5090-voice.room.studio": "http://localhost:4482/dashboard/voice",
  "creator-studio.room.collab": "http://localhost:4482/notebook-workbench"
}
```

Set this in the Dockerfile:
```
ENV VITE_PMOVES_ROOM_IFRAMES='{"persona.room.livingdoc":"http://localhost:4482/persona/livingdoc",...}'
```

This makes each room window embed the real service URL in a sandboxed iframe instead of StubApp metadata.

### Priority 2: Stock app cleanup

The desktop currently shows 11 upstream OpenRoom sample apps (Twitter, Music Player, Diary, Album, Gomoku, FreeCell, Email, Chess, Evidence Vault, CyberNews, Aoi chatbot). These need to be either:
- **Hidden** when a PMOVES room is active (only show room windows)
- **Replaced** with PMOVES-relevant apps (Agent Zero, Archon, Notebook, Graphiti)

The Shell (`src/components/Shell/index.tsx`) hardcodes the app grid. Filter by `isPmovesRoom` or replace the static app list.

### Priority 3: `/stage/` Enter button

`website/stage/` renders a static A2UI catalog of room cards. Add a Button to each card that navigates to `${OPENROOM_BASE_URL}/?room=<id>`. The adapter's header comment already documents this as the intended entry path.

### Priority 4: PMOVES model fabric wiring

OpenRoom's `llmClient.ts` has its own LLM client. Wire it to PMOVES TensorZero gateway (`:3030`) or Ollama (`:11434`) so the desktop chat panel uses fleet models instead of requiring separate API keys.

### Priority 5: P7 control plane fix

The nginx proxy references `pmoves-p7:8120` but the P7 session endpoint returns 404. Check:
- P7's actual session route: `POST /api/p7/rooms/{id}/session` vs what the adapter calls
- The `P7_CONTROL_TOKEN` env var needs to be forwarded

### Priority 6: Persona theming beyond accent

Currently only `--pm-accent` CSS var is applied. The manifest declares `theme.skin: "waveform-editorial"` and `theme.icon: "waveform"` — consume these to apply room-specific visual identity (wallpaper, icon set, font).

---

## The DARKXSIDE Brand Context

The persona room (`persona.room.livingdoc`) is the public, LinkedIn-facing living doc for Russell Richardson. Key brand elements:

- **Dual-frequency identity**: warm=beats (DARKXSIDE music), cool=code (PMOVES infrastructure) — "same person, different frequency"
- **82 tracks, 15 years**: BPM as state vector, catalog as codebase. SoundCloud: `soundcloud.com/darkxside`
- **Waveform motif**: the hero canvas in the persona HTML draws dual-frequency signal waves
- **Accent color**: `#F4A12B` (warm gold)
- **Skin**: `waveform-editorial`
- **Egress floor**: kids/family always redacted, no LAN IPs, investor model stays private

The DARKXSIDE YouTube playlist "School of Powerful Moves" (`PLGupOT04oMfok7S8W8Js7lZZIlhM8ufc8`) is ingested via n8n flow `darkxside_playlist_ingestion.json` — transcribed, summarized, indexed to Hi-RAG under namespace `darkxside`.

---

## Files You Need

### OpenRoom submodule (your workspace)
| File | Purpose |
|------|---------|
| `PMOVES-OpenRoom/apps/webuiapps/src/lib/pmovesRoomAdapter.ts` | The adapter — reads `?room=`, fetches manifest, composes windows |
| `PMOVES-OpenRoom/apps/webuiapps/src/pages/StubApp/index.tsx` | The stub renderer + iframe escape hatch |
| `PMOVES-OpenRoom/apps/webuiapps/src/lib/appRegistry.ts` | `registerApp()` / `getAppByRoute()` — PMOVES apps get appId 1000+ |
| `PMOVES-OpenRoom/apps/webuiapps/src/lib/windowManager.ts` | `openWindowAt()` — positions windows from manifest panels |
| `PMOVES-OpenRoom/apps/webuiapps/src/components/Shell/index.tsx` | Desktop shell — wallpaper, app grid, chat panel |
| `PMOVES-OpenRoom/apps/webuiapps/src/components/AppWindow/index.tsx` | Window renderer — StubApp vs real component decision |
| `PMOVES-OpenRoom/apps/webuiapps/nginx/default.conf` | Nginx routes — room manifests + P7 proxy |
| `PMOVES-OpenRoom/apps/webuiapps/Dockerfile` | Build (fixed by Crush: husky bypass, BIZ_PROJECT_NAME=webuiapps) |
| `PMOVES-OpenRoom/HARDENING.md` | Full architecture doc + out-of-scope list |

### PMOVES monorepo (config + manifests)
| File | Purpose |
|------|---------|
| `pmoves/config/rooms/catalog.json` | 13-room catalog (room_id → manifest file mapping) |
| `pmoves/config/rooms/persona.room.livingdoc.json` | The public persona room manifest |
| `pmoves/config/rooms/darkxsides.room.json` | The private DARKXSIDE room (owner-only) |
| `pmoves/rooms/persona/persona.json` | Content model (single source of truth) |
| `pmoves/rooms/persona/index.html` | The rendered living-doc HTML (Phase 2-5) |
| `pmoves/docker-compose.yml` | `openroom` service definition (port 5173) |
| `pmoves/Makefile` | `make -C pmoves up-openroom` target |

### Fleet context
| File | Purpose |
|------|---------|
| `pmoves/config/agent_signatures.yaml` | Your identity (L237-296 minimax) |
| `pmoves/configs/agent-profiles/minimax_edition.yaml` | Your KiloCode claw profile |
| `pmoves/configs/model-suits/minimax-m2.7.yaml` | Your primary model suit |
| `docs/AGENT_TRAIL.md` | Where you sign your first entry |
| `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` | Claim/release register |

---

## Docker Compose Service (already wired)

```yaml
openroom:
  build:
    context: ../PMOVES-OpenRoom
    dockerfile: apps/webuiapps/Dockerfile
  image: pmoves-openroom:latest
  container_name: pmoves-openroom
  restart: unless-stopped
  volumes:
  - ./config/rooms:/etc/pmoves/rooms:ro
  ports:
  - "${OPENROOM_BIND:-0.0.0.0}:${OPENROOM_PORT:-5173}:3000"
  networks: [pmoves_app, pmoves_external]
  profiles: ["ui", "p7"]
```

Start with: `make -C pmoves up-openroom`
Room URL pattern: `http://localhost:5173/webuiapps/?room=<room_id>`

---

## Acceptance Criteria

1. `http://localhost:5173/webuiapps/?room=persona.room.livingdoc` shows the real persona HTML (not StubApp metadata) — iframe pointing to `http://localhost:4482/persona/livingdoc`
2. Stock OpenRoom apps (Twitter, Chess, etc.) hidden when a PMOVES room is active
3. `/stage/` catalog page has "Enter" buttons that navigate to OpenRoom room URLs
4. At least 3 rooms render real content via iframe: persona livingdoc, demo room (Agent Zero), creator studio (notebook workbench)
5. P7 session open/close succeeds (no 404) when transitioning between rooms
6. Signed graphiti trail entry in `docs/AGENT_TRAIL.md`

---

## Coordination

- **CRUSH** (◇, this session) is on 5090 — available for pair review
- **Agent Zero** on SPARK can orchestrate knowledge gathering via Archon MCP
- **HERMES** (★) is the cross-platform gateway — can relay to SPARK for Archon queries
- **DARKXSIDE** (✦) is the operator persona — the witness whose brand the rooms reflect

Sign your lane in AGNOTE4482PHI.t1.md before starting. Release when done.

— ◇ Crush
