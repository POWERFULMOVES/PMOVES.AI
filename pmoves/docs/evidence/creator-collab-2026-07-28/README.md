# Creator Collab Lane — visual evidence (2026-07-28)

Visual evidence for the creator-collab lane as of 2026-07-28, after slices
1+2+3+4+6 SHIPPED (slice 5 = this page; slice 7 = Fordham E2E, last).

## What this is

`pmoves/docs/evidence/creator-collab-2026-07-28/` is a static, renderable
snapshot of the lane's contract-level deliverables. Everything in here
is generated from the actual JSON / YAML files in the repo — no
copy-paste, no mockups. Re-run `render_dashboard.py` to refresh.

This is the visual evidence required by the lane workflow for the
frontend / OpenRoom-surface slices (creator-collab slices 1, 5, 6, 7
all touch the OpenRoom surface; slice 5 is the visual-evidence slice
per operator signoff).

## Contents

| Path | What |
|---|---|
| `index.html` | The rendered dashboard. Dark theme, single-file, no JS deps. |
| `screenshots/01-overview.png` | Full-page screenshot (1440x5655 captured, 1440x900 viewport). Header + slice status + 4 sections. |
| `screenshots/02-rooms.png` | The room directory section (12 rooms) + the 2 new room cards. |
| `screenshots/03-creator-studio.png` | The `creator-studio.room.collab` card (slice 1's first consumer). |
| `screenshots/04-helpdesk.png` | The `pmoves.room.helpdesk` card (slice 6's first consumer). |
| `screenshots/05-pinokio-apps.png` | The 12 curated Pinokio apps (slice 4) with 4-layer reachability. |
| `screenshots/06-tac-trees.png` | The 43 layer-TAC trees in `pmoves/configs/tac_trees/` (slice 4 added 4). |
| `screenshots/07-topics.png` | The 99 NATS topics, with the 3 slice 6 helpdesk.* + 5 slice 3 comfy.collab.* + room.* topics highlighted. |

## What the dashboard shows

- **Header** — lane state at a glance (ship_count 5/7, slice 1+2+3+4+6 SHIPPED, slice 5 + 7 pending).
- **Section 1: Room directory** — the 12 rooms in `pmoves/config/rooms/catalog.json`, plus full detail cards for the 2 new rooms (creator-studio from slice 1, helpdesk from slice 6). Each card shows room_purpose, creator_surface, stage, agent_id, hardware_requirements, pinokio_app_refs, policies.publish, access.invite_list, apps (kind/route/status), and skill_bindings (skill_id/display_name/invocation_mode).
- **Section 2: Pinokio Apps Registry** — the 12 curated YAML entries, with hardware, gpu_arch, autostart, and the 4-layer network_exposure (L1 venv, L2 same-host container, L3 tailnet mesh, L4 public via kvm2 Cloudflare-Tunnel + Hostinger DNS). ComfyUI Desktop + Ultimate TTS Studio are the 2 L4-public apps.
- **Section 3: Layer-TAC trees** — 43 .tac.yaml files in `pmoves/configs/tac_trees/`; slice 4 added 4 (pinokio-venv / pmoves-container / tailnet-mesh / public-tunnel — one per reachability layer). Cascading gates surface which layer failed first.
- **Section 4: NATS topics** — 99 topics total (was 91 pre-slice-3, +5 slice 3, +3 slice 6). The 3 slice 6 helpdesk.* topics are highlighted; the 5 slice 3 comfy.collab.* + room.* topics are listed; the 91 pre-existing topics are collapsed in a `<details>`.

## How to re-render

```powershell
# From the worktree root (use the worktree's Python directly):
C:\Users\russe\AppData\Local\Programs\Python\Python312\python.exe `
    pmoves/tools/creator-collab-evidence/render_dashboard.py `
    --out pmoves/docs/evidence/creator-collab-2026-07-28/index.html

C:\Users\russe\AppData\Local\Programs\Python\Python312\python.exe `
    pmoves/tools/creator-collab-evidence/capture_screenshots.py `
    --html pmoves/docs/evidence/creator-collab-2026-07-28/index.html `
    --out pmoves/docs/evidence/creator-collab-2026-07-28/screenshots `
    --port 8848
```

The renderer is deterministic — running it twice produces byte-identical
HTML if the source files haven't changed. The capture script uses
Playwright + chromium headless, viewport 1440x900.

## Why a generator, not a hand-written page

- **No copy-paste drift.** The dashboard reads the actual catalog.json
  + the 2 new room manifests + the 12 curated YAMLs + topics.json.
  When a slice commit lands and changes one of those files, re-running
  the renderer picks it up.
- **Self-explanatory.** The HTML carries the data + a dark theme; a
  viewer can open the page in any browser without a build step.
- **Re-runnable in CI.** The dashboard + screenshots are part of the
  slice 5 commit. Future slices that touch the room directory /
  pinokio-apps registry can re-run the same scripts to refresh.

## What this is NOT

- **Not a real PMOVES UI render.** This is a contract-level snapshot
  generated from the actual JSON / YAML, not the Next.js
  `pmoves/ui` surface. The pmoves-ui dashboard would need env.shared
  + npm install + a real dev server boot, which is heavier and
  requires operator secrets. The contract-level evidence answers the
  question "did the new manifests parse + render correctly?" without
  the deploy machinery.
- **Not interactive.** It's a static HTML page with no JS. The
  collapsible topics section uses native `<details>`.
- **Not a substitute for the slice 7 Fordham E2E.** Slice 7 (the
  integrated Fordham ↔ PMOVES-helpdesk E2E) is the last slice; it
  exercises the actual surfaces in motion. This page is the
  contract-level snapshot that comes before the runtime integration.

## Cross-references

- `pmoves/docs/specs/creator-collab-room-extensions-2026-07-27.md` (slice 1)
- `pmoves/docs/specs/pinokio-apps-registry-2026-07-28.md` (slice 4)
- `pmoves/docs/specs/helpdesk-and-room-suggest-2026-07-28.md` (slice 6)
- `pmoves/tools/creator-collab-evidence/render_dashboard.py` (the renderer)
- `pmoves/tools/creator-collab-evidence/capture_screenshots.py` (the capturer)
- `pmoves/tools/creator-collab-state.json` (lane state; ship_count: 5/7)
- `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` (the lane's audit trail)
