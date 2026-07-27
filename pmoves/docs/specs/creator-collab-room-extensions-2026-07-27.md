# Creator Collab Lane — Room Manifest Schema Extensions (2026-07-27)

**Status:** Slice 1 SHIPPED on `feat/creator-collab-lane` (worktree off `origin/main` @ `4cbf58b4e5`).

**Lane owner:** Mavis (Mavis::CREATOR-COLLAB-LANE-CLAIM::2026-07-27).
**Pattern:** openroom-adapter cadence (3 stacked commits per slice: P1 + functional + docs).
**Visual evidence / smoke test:** slice 5d — **planned** (full creator-studio E2E with real Pinokio apps + a 5090/Spark render, lands with slice 5). Until slice 5 ships, no E2E evidence is available; the only shipped artifacts are the manifest + schema (slice 1) and the first consumer of the new fields (also in slice 1).

## Why

Rooms are creation surfaces, not just meeting rooms. The openroom-adapter lane (PR #2199, merged 2026-07-24) made rooms loadable; this lane makes them **productive**. The Fordham pilot room (`pmoves/config/rooms/fordham.room.community.json`) already binds `claude-d3js` with intent `["creator", "visualization", "dashboard"]` — the use case is real, the schema didn't yet express it. The ComfyUI MCP (`.claude/mcp.json` line 125, cloud.comfy.org hosted, registered PR #2185) + the self-host config (`pmoves/services/comfyui/Dockerfile`, 4090 handoff 2026-06-24) + the Pinokio fleet (`D:\pinokio\api\*`, 22 apps installed on 5090) are all the surface — the contract was the missing layer.

## Design

Three additions to `room.manifest.v1`, all top-level optional, all additive (no breakage for existing rooms):

1. **`room_purpose`** — string enum: `community | control | studio | operator | classroom | field | showroom | intake | exchange | custom`. Distinct from `room_type` (which is the operating pattern, e.g. `creator`/`scout`/`hybrid`); `room_purpose` answers **"who comes here and why"** at the social/topological level. Fordham = `community`; the new `creator-studio.room.collab` = `studio`; PMOVES helpdesk (slice 6) = `intake`; ops rooms = `control`; live-ops rooms = `operator`; learning rooms = `classroom`; field-rig rooms = `field`; showcase rooms = `showroom`.

2. **`creator_surface`** — string enum: `primary | ambient | background | off`. Tunes how the ComfyUI / Pinokio creator surface shows up in the room:
   - `primary` = full collab canvas (prompt queue + live progress + artifact gallery + whiteboard)
   - `ambient` = chat-overlay only (small "render this" button next to chat, no main panel)
   - `background` = no UI on the desktop but the skill runs on explicit agent request
   - `off` = not available

   Every room gets the `pinokio-bridge-skill` bound; this field just tunes the UI mode. Fordham uses `ambient` (community help desk can render an infographic on demand); 4090-field uses `background` (no ComfyUI panel in the ops room, but the skill runs if an agent asks for a viz); 5090-voice and the new `creator-studio` use `primary` (full studio surface); legacy rooms without this field default to `off` (zero behavior change).

3. **`hardware_requirements`** — object: `{ gpu: bool, min_vram_mb: int, gpu_arch: [sm_89|sm_90|sm_100|sm_110|sm_120], node_roles: [primary-gpu-tts|infra-coordinator|mobile-relay|gpu-inference|edge-ai|api-gateway|data-storage|exit-proxy], cpu_arch: [x86_64|arm64] }`. P7's session-open handler reads this + the current node's profile (`pmoves/config/profiles/`) + the fleet's `pinokio-network-inventory.yaml` to pick the right physical host for the room session. The Fordham room sets `gpu: false` (CPU-only SESSION — lives on z890 as the infra-coordinator; the room itself never moves to a GPU host) + `node_roles: [infra-coordinator]`. Renders triggered from the room (via the helpdesk-skill that lands in slice 6) are NOT routed to the room's host — they go through the mesh-render broker to 5090/Spark/cloud. The helpdesk sets `gpu: false` + `node_roles: [infra-coordinator, primary-gpu-tts, gpu-inference]` (session on z890; mesh-renders on demand). `creator-studio` sets `gpu: true` + `min_vram_mb: 24000` + `node_roles: [primary-gpu-tts, gpu-inference]` (P7 routes to 5090 first, escalates to Spark for >24GB jobs). Required fields + conditional validation enforced via the schema (see P1 of review-iter-2).

4. **`pinokio_app_refs`** — array of `{ slug, role: primary|optional|fallback, gpu_reservation_mb, gpu_reservation_mode: concurrent|exclusive, autostart: bool }`. Each ref resolves to `pmoves/config/pinokio-apps/curated/<slug>.yaml` (or `user/<slug>.yaml` for user-added apps) for endpoint, healthcheck, gpu_required, node_affinity, pinokio_skill_ref. P7 session-open calls `pinokio start <slug>` per app in dependency order, respecting the declared GPU reservations and the autostart + gpu_reservation_mode interaction described below. The `creator-studio` room references `comfyui-desktop` (primary, 16GB, concurrent, autostart), `ace-step` (optional, 8GB, concurrent, autostart), `wan` (optional, 24GB, **exclusive**, **autostart: false**), `lightonocr-2-1b` (fallback, 2GB, concurrent, autostart).

### `autostart` + `gpu_reservation_mode` interaction (added review-iter-2)

The two knobs combine into a 4-quadrant behavior matrix that P7's session-open enforces:

| `autostart` | `gpu_reservation_mode` | Behavior |
|---|---|---|
| `true` (default) | `concurrent` (default) | P7 starts this app on room launch; VRAM counts toward the concurrent sum. The host node must satisfy `sum(concurrent_refs.gpu_reservation_mb) <= node_vram_mb`. |
| `true` | `exclusive` | P7 starts this app on room launch; the app claims the whole host GPU. P7 rejects the room if any other `autostart: true` ref is in the same launch set (the scheduler can't satisfy exclusive + concurrent at session-open). Workaround: set the exclusive ref to `autostart: false` and let the skill that needs it launch it on demand. |
| `false` | `concurrent` | P7 does NOT start this app on room launch; VRAM is reserved against the host's available budget so the app can be started later. The skill that needs it triggers the launch. |
| `false` | `exclusive` | P7 does NOT start this app on room launch; the exclusive claim is deferred. The skill that needs it launches the app on a node with the full VRAM available (typically DGX Spark for big video / LoRA jobs). This is the recommended pattern for big models that shouldn't be in the room's initial launch set. |

**Why this is a 4-quadrant matrix, not just `autostart: false` alone:** WAN video gen claims 24 GB exclusive. On a 32 GB 5090, the other concurrent refs (comfyui-desktop 16 GB + ace-step 8 GB + lightonocr-2-1b 2 GB = 26 GB) fit just fine — but the moment P7 tries to ALSO start wan, the host can't satisfy 26 GB concurrent + 24 GB exclusive on a 32 GB GPU. Setting `autostart: false` on the wan ref moves it out of the launch set, so the room opens with the 3 concurrent apps and the comfy-mesh-skill's video-gen mode launches wan on demand when the user asks for video (typically routed to Spark for the 24 GB exclusive claim).

P7's session-open validates this constraint at admission: if any `autostart: true` ref has `gpu_reservation_mode: exclusive` AND any other `autostart: true` ref exists, P7 returns `409 conflict` with `room_id` + the offending ref slug(s). The fix is in the manifest, not the runtime.

## P8 surface mapping (added slice 2, 2026-07-27)

Slice 1's schema fields were designed to be the PMOVES-side declaration of the same surfaces Pinokio 8 manages natively. The `pinokio_bridge` service (slice 2) reads from Pinokio's on-disk state and the room manifest, and reconciles them at session-open. Here's the field-by-field mapping:

| Schema field (slice 1) | P8 surface | Bridge endpoint | What P7 does at session-open |
|---|---|---|---|
| `pinokio_app_refs[*].slug` | `~/pinokio/api/<slug>/` (app dir) | `GET /v1/apps/{slug}/status` | Resolves the slug to a Pinokio install; 404s the room if the app isn't installed |
| `pinokio_app_refs[*].role: primary\|optional\|fallback` | — (PMOVES-internal policy) | — | Decides whether the ref is required, nice-to-have, or last-resort; doesn't change Pinokio's view of the app |
| `pinokio_app_refs[*].gpu_reservation_mb` | — (PMOVES-internal budget) | — | Contributes to the concurrent VRAM sum; the bridge doesn't see this directly |
| `pinokio_app_refs[*].gpu_reservation_mode: concurrent\|exclusive` | P8 autolaunch + per-app GPU claim | `GET /v1/autolaunch` (post-write verification) | Verifies the P8 autolaunch state matches the manifest's `autostart` intent |
| `pinokio_app_refs[*].autostart: bool` | P8 `/autolaunch` page state | `GET/POST /v1/apps/{slug}/autolaunch` | Toggles the app's autolaunch; `false` means the app is on-demand only |
| `hardware_requirements.gpu: bool` | — (room-level decision) | — | Combined with `min_vram_mb` to require the bridge's `/v1/gpu/match` |
| `hardware_requirements.min_vram_mb` | `{{vram}}` template var | `GET /v1/gpu/match?min_vram=N` | Routes the room session to a host with at least N MB VRAM |
| `hardware_requirements.gpu_arch: [sm_XX]` | `{{gpu_target}}` template var | `GET /v1/gpu/match?gpu_arch=sm_120,sm_110` | Routes to a host with a matching compute capability (the bridge normalizes the raw `12.0` to `sm_120` internally) |
| `hardware_requirements.node_roles: [...]` | — (PMOVES fleet topology) | — | Coarse routing preference; the bridge's per-host detection is the final say |
| `hardware_requirements.cpu_arch: [x86_64\|arm64]` | — (PMOVES fleet topology) | — | Same as node_roles; coarse routing preference |
| (no direct slice-1 field) | P8 orchestration (recursive deps) | `GET /v1/apps/{slug}/dependencies` | P7 uses this to verify the room's launch order is feasible (e.g. creator-studio needs comfyui which needs shared-models) |
| (no direct slice-1 field) | P8 managed skills (sync state) | `GET /v1/skills`, `GET /v1/skills/conflicts` | `pmoves-living-docs-refresh` uses this to detect drift between the managed-skill library and the local PMOVES skill folder |
| (no direct slice-1 field) | P8 GPU templates (full set: `{{vram}}`, `{{gpu_model}}`, `{{gpu_driver}}`, `{{gpu_target}}`, `{{gpus}}`) | `GET /v1/gpu/detect` | P7's `/v1/gpu/detect` is the canonical source for the same data that Pinokio 8's launcher templates see; the bridge keeps the two in sync by reading Pinokio's own state file |

The bridge service is the single source of truth for the read-side. Pinokio's own state files are the source of truth for the write-side; the bridge forwards writes to Pinokio via structured `shell.run` argv (P8 surface, not raw shell).

## Why this and not a different shape

- **Not extending `room_type`** — `room_type` is the operating pattern (creator/scout/hybrid) and is referenced by `pmoves/configs/agent-teams.yaml`, the skill marketplace, and the OpenRoom adapter. Conflating "what the room does" with "who it serves" would tangle two real concerns. Two fields, two clean axes.
- **Not putting hardware in `meta.chit` / `meta`** — `meta` is signing-card metadata, not infra. `hardware_requirements` is a first-class schema field because P7 needs to read it during session-open without a metadata walk.
- **Not a `mcp_servers` array inside the room** — Pinokio apps are NOT MCP servers (only the official ComfyUI MCP is). Pinokio apps are HTTP/Gradio services that PMOVES drives via Pinokio's built-in `pinokio` skill. The `pinokio_app_refs` field is the cleanest semantic — it's "what Pinokio apps this room brings up", not "what MCP servers this room registers".

## Hardware mesh (fleet reality)

Per `pmoves/configs/pinokio-network-inventory.yaml` + `pmoves/config/profiles/`:

| Node | GPU | VRAM | Node role | Available apps |
|---|---|---|---|---|
| pmoves-z890 | RTX 3090ti | 24GB | infra-coordinator | NATS, Supabase, Flute, MinIO (KVM4-2) + 3090ti can host ComfyUI |
| POWERFULMOVES (5090) | RTX 5090 | 32GB | primary-gpu-tts | Ultimate-TTS-Studio, Qwen3-TTS, VibeVoice, VoxForge, Ollama, N8N, SillyTavern, ACE-Step, WAN, ComfyUI |
| pmoves-laptop (4090) | RTX 4090 Laptop | 16GB | mobile-relay (consumer) | consumer of mesh, light local |
| pmoves-dgx-spark | GB10 Blackwell unified | 128GB | gpu-inference | Ollama (Gemma 4 31B, Nemotron Super 49B), NIM, can host ComfyUI for huge jobs |
| pmoves-kvm4-1 | — | — | api-gateway | NATS relay, Discord-Bot |
| pmoves-kvm4-2 | — | — | data-storage | Supabase, MinIO, Qdrant, Meilisearch, Neo4j |
| pmoves-jetson-orin | Edge CUDA | — | edge-ai | Ollama |
| kvm2 | — | — | exit-proxy | Cloudflare-Tunnel, Tailscale-Funnel |

When slice 6 lands, Fordham on z890 (CPU SESSION) + `creator_surface: ambient` will let the helpdesk-skill trigger mesh-renders when an answer benefits from a visual. The mesh-render broker (slice 2) routes the render request to 5090 first (LAN, 32GB, fastest for the typical image-gen case), escalates to Spark for >24GB jobs (video, LoRA), falls back to cloud.comfy.org MCP if no fleet GPU is up. The Fordham session itself never moves to a GPU host — only the render does. (Updated in review-iter-2 per CodeRabbit thread 3657849863; the previous version conflated the room session's CPU posture with the mesh-render's GPU posture.)

## Cross-references

- `pmoves/docs/ROOM_MANIFEST_CONTRACT.md` — base contract
- `pmoves/contracts/schemas/room/room.manifest.v1.schema.json` — schema (this slice's diff)
- `pmoves/contracts/schemas/room/skill.binding.v1.schema.json` — skill binding shape (unchanged)
- `pmoves/config/rooms/creator-studio.room.collab.json` — slice 5 seed
- `pmoves/configs/pinokio-network-inventory.yaml` — fleet inventory
- `pmoves/config/profiles/{workstation_5090,laptop-4090,dgx-spark-grace-blackwell,z890-coordinator}.yaml` — node profiles
- `D:\pinokio\prototype\PINOKIO.md` — Pinokio v1 docs (legacy, pre-8.0); the bridge wraps P8's autolaunch + orchestration + managed skills + GPU surfaces
- `https://cocktailpeanutlabs.github.io/p8/` — Pinokio 8.0.0 release notes (the upstream this slice wraps)
- `pmoves/skills/pinokio-bridge-skill/SKILL.md` — PMOVES-side skill that uses the bridge (slice 2 P1 commit)
- `pmoves/services/pinokio_bridge/` — the Python adapter (slice 2 functional commit)
- `pmoves/configs/tac_trees/pinokio-p8.tac.yaml` — the P8 audit tree (slice 2 functional commit)
- `pmoves/docs/handoffs/creator-comfyui-selfhost-config-2026-06-24.md` — self-host config handoff
- AGNOTE4482PHI.t1.md — lane CLAIM + RELEASE entries

## Sibling extension: PMOVES-wide pinokio-apps registry (slice 5a)

The schema's `pinokio_app_refs` field is meaningless without the catalog. Slice 5a lands `pmoves/config/pinokio-apps/curated/<slug>.yaml` for the 12 known apps (comfyui-desktop, ace-step, wan, lightonocr-2-1b, ultimate-tts-studio, qwen3-tts, vibevoice-realtime, voxforge-pro, n8n, sillytavern, unsloth, customokio). Schema is `pmoves/config/pinokio-apps/schema/pinokio-app.v1.schema.json`. Discovery tool (`pmoves/tools/pinokio_apps/discover.py`) reads `D:\pinokio\api\` to populate the `user/` mirror.
