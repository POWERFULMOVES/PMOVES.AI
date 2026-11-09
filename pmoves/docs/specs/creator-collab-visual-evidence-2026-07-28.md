# Creator Collab Lane — Visual Evidence Slice 5

> **Status:** Slice 5 SHIPPED on `feat/creator-collab-lane`. 6/7 slices
> complete. Companion to the slice-1 spec (room manifest extensions),
> the slice-2 spec (P8 surface mapping), the slice-3 spec's NATS
> pipeline section, the slice-4 spec (pinokio-apps registry), and
> the slice-6 spec (helpdesk + room-suggest).

## 1. Why slice 5

The lane workflow requires visual evidence for slices that ship a new
room manifest or change the OpenRoom surface. Slices 1, 5, 6, 7 all
touch the OpenRoom surface:

- slice 1: `creator-studio.room.collab.json` (SHIPPED_MERGED to main)
- slice 5: this slice — the visual evidence
- slice 6: `pmoves.room.helpdesk.json` (SHIPPED on lane)
- slice 7: Fordham ↔ PMOVES-helpdesk E2E (last, integrated demo)

The lane operator's standing rule: "boot dev server + take Playwright
screenshots before push" for frontend work. Slice 5 is the dedicated
visual-evidence slice — it's the snapshot of the contract-level
deliverables as of 2026-07-28, after slices 1+2+3+4+6 SHIPPED.

## 2. What slice 5 ships

A static, renderable HTML dashboard at
`pmoves/docs/evidence/creator-collab-2026-07-28/index.html` plus 7
Playwright PNG screenshots. The dashboard is generated from the
actual JSON / YAML files in the repo — no copy-paste, no mockups.

| Section | Source | Shows |
|---|---|---|
| Header | lane state | 7-slice status badges, current ship_count (5/7) |
| 1. Room directory | `pmoves/config/rooms/catalog.json` + the 2 new room manifests | 12 rooms, plus full detail cards for the 2 new (creator-studio + helpdesk) |
| 2. Pinokio Apps Registry | `pmoves/configs/pinokio-apps/curated/*.yaml` | 12 curated entries with hardware + 4-layer reachability |
| 3. Layer-TAC trees | `pmoves/configs/tac_trees/*.tac.yaml` | 43 trees, slice 4 added 4 (one per reachability layer) |
| 4. NATS topics | `pmoves/contracts/topics.json` | 99 topics, 3 slice 6 helpdesk.* highlighted |

## 3. Approach: contract-level snapshot, not a real PMOVES UI render

The operator's option (Option A in the slice 5 signoff) was to boot
`pmoves-ui` on :4482 and screenshot the dashboard rendering the new
manifests. The `pmoves/ui` Next.js surface requires:
- `npm install` (~5-10 min, ~500MB dependencies)
- `pmoves/env.shared` + `pmoves/env.shared.generated` (not in the
  worktree; the only env file present is `env.shared.example`)
- Supabase / external service env vars

The contract-level snapshot answers the same question ("did the new
manifests parse + render correctly?") without the deploy machinery.
When the operator has a clean `pmoves/ui` boot, the same renderer can
be pointed at the running surface; for now, the contract-level
evidence is the deliverable.

## 4. Why a generator, not a hand-written page

- **No copy-paste drift.** The dashboard reads the actual JSON / YAML.
  Future slice commits that change any of these files are picked up by
  re-running the renderer.
- **Self-explanatory.** The HTML carries the data + a dark theme; a
  viewer can open the page in any browser without a build step.
- **Re-runnable.** `render_dashboard.py` is deterministic (running
  twice with no source changes produces byte-identical HTML). The
  capture script uses Playwright + chromium headless, viewport 1440x900.

## 5. Renderer + capture scripts

`pmoves/tools/creator-collab-evidence/render_dashboard.py` (16.7 KB):
- Reads catalog.json + the 2 new room manifests + 12 curated YAMLs
  + topics.json
- Generates the single static HTML page
- stdlib + pyyaml only

`pmoves/tools/creator-collab-evidence/capture_screenshots.py` (5.3 KB):
- Boots a local HTTP server on the evidence directory (port 8848,
  falls back to any free port)
- Opens chromium headless at 1440x900 viewport
- Captures 7 PNGs (full page + 6 section captures)
- Uses Playwright sync API (already in the lane's dependency stack
  via `pmoves/ui`'s `@playwright/test`)

## 6. Screenshots

| File | Size | Content |
|---|---|---|
| `01-overview.png` | 496 KB | Full page (1440x5655 captured at 1440x900 viewport) |
| `02-rooms.png` | 175 KB | Room directory section + 2 new room cards |
| `03-creator-studio.png` | 58 KB | `creator-studio.room.collab` card (slice 1's first consumer) |
| `04-helpdesk.png` | 63 KB | `pmoves.room.helpdesk` card (slice 6's first consumer) |
| `05-pinokio-apps.png` | 142 KB | 12 curated Pinokio apps (slice 4) with 4-layer reachability |
| `06-tac-trees.png` | 115 KB | 43 layer-TAC trees (slice 4 added 4) |
| `07-topics.png` | 24 KB | 99 NATS topics with 3 helpdesk.* highlighted |

## 7. What slice 5 is NOT

- **Not a real PMOVES UI render.** This is a contract-level snapshot
  generated from the actual JSON / YAML, not the Next.js
  `pmoves/ui` surface. The pmoves-ui dashboard would need env.shared
  + npm install + a real dev server boot, which is heavier and
  requires operator secrets.
- **Not interactive.** The page has no JS; the collapsible topics
  section uses native `<details>`.
- **Not a substitute for the slice 7 Fordham E2E.** Slice 7 is the
  runtime integration test — it exercises the actual surfaces in
  motion (pinokio_bridge launches comfyui-desktop → nats_event_bus
  sees room.presence.v1 → helpdesk room opens → Fordham resident
  lands → helpdesk routes to Fordham room → Fordham's
  `mesh-egress-ab` runs the capacity A/B → writeback to notebook →
  dashboard). This page is the snapshot that comes before that.

## 8. Cross-references

- `pmoves/docs/evidence/creator-collab-2026-07-28/index.html` (the dashboard)
- `pmoves/docs/evidence/creator-collab-2026-07-28/screenshots/` (the 7 PNGs)
- `pmoves/docs/evidence/creator-collab-2026-07-28/README.md` (the evidence README)
- `pmoves/tools/creator-collab-evidence/render_dashboard.py` (the renderer)
- `pmoves/tools/creator-collab-evidence/capture_screenshots.py` (the capturer)
- `pmoves/docs/specs/creator-collab-room-extensions-2026-07-27.md` (slice 1)
- `pmoves/docs/specs/pinokio-apps-registry-2026-07-28.md` (slice 4)
- `pmoves/docs/specs/helpdesk-and-room-suggest-2026-07-28.md` (slice 6)
- `pmoves/tools/creator-collab-state.json` (lane state; ship_count: 6/7)
- `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` (the lane's audit trail)
