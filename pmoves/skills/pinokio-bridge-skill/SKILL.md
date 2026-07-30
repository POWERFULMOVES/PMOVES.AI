---
name: pinokio-bridge
description: >
  Pinokio 8 bridge for PMOVES — exposes the four P8 surfaces PMOVES agents
  need: autolaunch (which apps start when Pinokio starts), orchestration
  (the recursive dependency graph that decides launch order), managed skills
  (Pinokio 8's library of skills syncing into local agent skill folders), and
  GPU/VRAM template substitution (the {{vram}} / {{gpu_*}} / {{ready}} vars
  that launchers expose). Reads from the local Pinokio 8 install on the host
  via the pinokio_bridge Python service (HTTP) — does NOT shell out to
  Pinokio directly. Companion skill to the pmoves-room-orchestrator P7
  service (which uses these surfaces to schedule rooms). Works alongside the
  existing pterm skill (which still wraps the pterm CLI for direct Pinokio
  script execution).
---

# pinokio-bridge — Pinokio 8 surfaces for PMOVES

Wraps the four Pinokio 8 surfaces that PMOVES agents need but don't have a
direct API for. Reads from the local Pinokio 8 install via the
`pinokio_bridge` Python service (HTTP at `http://127.0.0.1:8130` by
default). Does **not** shell out to Pinokio directly — uses the
structured `shell.run` argv surface through the bridge service so large
prompts and multiline arguments are passed safely (no shell-escape bugs).

> **Requires**: Pinokio 8.x installed locally (`pterm --version` should
> report `8.x.x` or higher), the `pinokio_bridge` Python service running,
> and a PMOVES room manifest that uses the `pinokio_app_refs` schema
> fields (`autostart`, `gpu_reservation_mode`, `gpu_arch`,
> `gpu_reservation_mb`) — those were added in creator-collab slice 1
> (PR #2264, merged 2026-07-27).

## Surfaces exposed

| Surface | What it answers | Endpoint |
|---|---|---|
| **Autolaunch** | Which apps start when Pinokio starts, with which script, and the per-app ON/OFF state | `GET /v1/apps/{slug}/autolaunch`, `POST /v1/apps/{slug}/autolaunch` |
| **Orchestration** | The recursive dependency graph — which apps depend on which, and the resolved launch order with `{{ready('start.js')}}` checks at each level | `GET /v1/apps/{slug}/dependencies`, `GET /v1/orchestration/graph` |
| **Managed skills** | The Pinokio 8 skill library: source, sync targets, validity, conflicts, ON/OFF — same as Pinokio's `/skills` page | `GET /v1/skills`, `POST /v1/skills/{slug}/sync`, `GET /v1/skills/conflicts` |
| **GPU/VRAM templates** | The `{{vram}}`, `{{gpu_model}}`, `{{gpu_driver}}`, `{{gpu_target}}`, `{{gpus}}` template vars that P8 launchers expose — let PMOVES read the detected GPU and route rooms to the right node | `GET /v1/gpu/detect` |

Each surface is also exposed in `POST` form for write operations
(enabling autolaunch, syncing a skill, etc.). Writes require the
operator-level `X-PMOVES-Bridge-Token` header; reads are open.

## Why this is a separate skill (not just more pterm)

`pterm` is the Pinokio terminal CLI — good for `pterm start`, `pterm
clipboard`, `pterm push`, and direct script execution. `pinokio-bridge`
is the *managed* surface — autolaunch, orchestration, managed skills,
GPU templates — where Pinokio 8 has moved beyond "run this script" to
"run this graph of scripts with this GPU and these skills in scope".
Reading these state surfaces through pterm would require scraping Pinokio
state files directly; the bridge service does the parsing + caching so
PMOVES agents get structured JSON.

## Surface 1 — Autolaunch

Pinokio 8's `/autolaunch` page shows which apps launch on Pinokio start
with their selected script + the global "disable startup" toggle.
The bridge exposes that as JSON so P7 can decide whether a room
session needs to pre-warm a dependency.

```bash
# Read the autolaunch state for a specific app
curl -s http://127.0.0.1:8130/v1/apps/comfyui-desktop/autolaunch
# → {"slug": "comfyui-desktop", "enabled": true, "script": "start.js",
#    "global_disabled": false, "last_evaluated_at": "2026-07-27T15:30:00Z"}

# List autolaunch state for every installed app
curl -s http://127.0.0.1:8130/v1/autolaunch
# → [{"slug": "comfyui-desktop", "enabled": true, ...}, ...]

# Enable autolaunch for an app (operator-level token required)
curl -s -X POST http://127.0.0.1:8130/v1/apps/wan/autolaunch \
  -H "X-PMOVES-Bridge-Token: $PMOVES_BRIDGE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"enabled": true, "script": "start.js"}'
# → {"slug": "wan", "enabled": true, "script": "start.js", ...}
```

How PMOVES uses this: when P7 opens a room session, the room manifest
declares `pinokio_app_refs` with `autostart: true` for each app that
should be ready before the room is interactive. P7 calls
`GET /v1/autolaunch` once at session-open and verifies the manifest's
declared refs match Pinokio's autolaunch state. If a ref is missing,
P7 either calls `POST /v1/apps/{slug}/autolaunch` (with operator
approval) or surfaces the gap to the user.

## Surface 2 — Orchestration

Pinokio 8's recursive dependency-aware launch — A depends on B, B
depends on C and D, Pinokio waits for C and D to be ready before
launching B, and waits for B before launching A. The bridge exposes the
graph + the resolved launch order + the `{{ready('start.js')}}` check
result at each level.

```bash
# Get the dependency graph for an app
curl -s http://127.0.0.1:8130/v1/apps/ideogrammar/dependencies
# → {
#     "slug": "ideogrammar",
#     "depends_on": ["comfyui"],
#     "recursive": ["comfyui", "shared-models"],
#     "launch_order": [
#       {"level": 0, "apps": ["shared-models"]},
#       {"level": 1, "apps": ["comfyui"]},
#       {"level": 2, "apps": ["ideogrammar"]}
#     ],
#     "ready_checks": {
#       "shared-models": true,
#       "comfyui": false,
#       "ideogrammar": false
#     }
#   }

# Get the full orchestration graph (for the whole fleet)
curl -s http://127.0.0.1:8130/v1/orchestration/graph
# → {"nodes": [...], "edges": [...], "cycles": []}
```

How PMOVES uses this: when the `comfy-mesh-skill` (creator-collab slice 1
schema, `pinokio_app_refs[*].slug`) wants to launch `comfyui`, P7 first
checks the dependency graph. If `comfyui` depends on `shared-models`,
P7 waits for `shared-models` to be ready before calling
`POST /v1/apps/comfyui/launch` (which the bridge does via structured
`shell.run` argv, not via raw shell).

## Surface 3 — Managed skills

Pinokio 8 ships a managed skill library that syncs into local agent
skill folders (Claude Code, Codex, etc.). The library shows source
URL, sync target path, validity (does the target file match the
source), conflicts (if the target was modified locally), and ON/OFF
state. Built-in `pinokio` and `gepeto` skills are part of this set.

```bash
# List the managed skill library
curl -s http://127.0.0.1:8130/v1/skills
# → [
#     {"slug": "pinokio", "source": "builtin", "sync_target":
#      "C:\\Users\\...\\.claude\\skills\\pinokio\\SKILL.md",
#      "valid": true, "conflict": false, "enabled": true},
#     {"slug": "gepeto", ...},
#     {"slug": "custom-voice-bridge", "source":
#      "https://github.com/...", ...}
#   ]

# Sync a specific skill (operator-level token required)
curl -s -X POST http://127.0.0.1:8130/v1/skills/pinokio-bridge/sync \
  -H "X-PMOVES-Bridge-Token: $PMOVES_BRIDGE_TOKEN"
# → {"slug": "pinokio-bridge", "synced": true, "target":
#      "C:\\Users\\...\\.claude\\skills\\pinokio-bridge\\SKILL.md"}

# Check for skill conflicts (target modified, source moved, etc.)
curl -s http://127.0.0.1:8130/v1/skills/conflicts
# → [{"slug": "...", "conflict_kind": "local_modification", ...}]
```

How PMOVES uses this: the `pmoves-living-docs-refresh` skill (in
`.claude/skills/`) calls `GET /v1/skills` to detect when a managed
skill is out of date. When the operator upgrades Pinokio or installs
a new managed skill from the P8 UI, the refresh skill pulls the
update into PMOVES's own skill folder and re-symlinks the SKILL.md
files. The bridge service is what makes this scriptable — without it,
PMOVES agents would have to know the exact on-disk layout of Pinokio
8's managed skill library.

## Surface 4 — GPU/VRAM templates

Pinokio 8 exposes detected GPU + VRAM as template variables in
launcher scripts: `{{vram}}` (integer GB), `{{gpu_model}}`,
`{{gpu_driver}}`, `{{gpu_target}}`, `{{gpus}}` (JSON). The bridge
exposes the same data as a JSON endpoint so PMOVES's P7 service
can route room sessions to the right host without spawning a
launcher just to read the vars.

```bash
# Detect the GPU on the current host
curl -s http://127.0.0.1:8130/v1/gpu/detect
# → {
#     "host": "POWERFULMOVES",
#     "vram": 32,
#     "gpus": [
#       {"model": "NVIDIA GeForce RTX 5090", "driver": "570.86.16",
#        "compute_capability": "12.0", "vram_mb": 32768}
#     ],
#     "primary": {"model": "RTX 5090", "vram_gb": 32}
#   }

# Cross-reference with creator-collab slice 1's hardware_requirements
# (this is what P7's session-open does internally — exposed for debugging)
curl -s "http://127.0.0.1:8130/v1/gpu/match?min_vram=24&gpu_arch=sm_120,sm_110"
# → {
#     "matched": true,
#     "host": "POWERFULMOVES",
#     "reason": "vram 32 >= 24 AND gpu_arch sm_120 in [sm_120, sm_110]"
#   }
```

How PMOVES uses this: when P7 opens a `creator-studio` room session,
the room manifest declares `hardware_requirements: { gpu: true,
min_vram_mb: 24000, gpu_arch: [sm_120, sm_110] }`. P7 calls
`GET /v1/gpu/detect` on each candidate fleet node + `GET /v1/gpu/match`
to pick the host that satisfies the requirements, with the right
P8 `{{vram}}` / `{{gpu_arch}}` context. The bridge service is the
canonical source for this data — the same numbers appear in
Pinokio's launcher templates, so PMOVES + Pinokio agree.

## Pinokio App Management (passthrough)

The bridge also exposes the basic Pinokio app-management surface that
the `pterm` skill provides, but as structured JSON instead of shell
commands. Useful for agents that don't have shell access:

```bash
# List installed apps
curl -s http://127.0.0.1:8130/v1/apps
# → [{"slug": "comfyui-desktop", "version": "0.3.41", ...}]

# Get app status
curl -s http://127.0.0.1:8130/v1/apps/comfyui-desktop/status
# → {"slug": "comfyui-desktop", "state": "running", "pid": 12345,
#    "uptime_sec": 86400, "endpoints": [{"port": 8188, "url":
#    "http://127.0.0.1:8188"}]}

# Launch an app (with structured argv — no shell escape)
curl -s -X POST http://127.0.0.1:8130/v1/apps/wan/launch \
  -H "X-PMOVES-Bridge-Token: $PMOVES_BRIDGE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"script": "start.js", "env": {"HF_TOKEN": "..."}, "argv_extra": ["--yolo"]}'
# → {"slug": "wan", "state": "launching", "pid": null, "log_tail": "..."}
```

## Token + service health

```bash
# Health check
curl -s http://127.0.0.1:8130/healthz
# → {"status": "ok", "pinokio_version": "8.0.0", "uptime_sec": 3600}

# The X-PMOVES-Bridge-Token header is loaded from PMOVES_BRIDGE_TOKEN
# in the bridge service's environment. Rotate via:
#   - Regenerate the token in the bridge service config
#   - Update PMOVES_BRIDGE_TOKEN in the secret store
#   - Restart the bridge service (no client action needed)
```

## Companion to P7 + pterm

- `pterm` (`.claude/skills/pterm/SKILL.md`) — the Pinokio terminal CLI
  wrapper. Use for direct script execution + clipboard + notifications.
- `pmoves-room-orchestrator` (P7 service, `pmoves/services/p7-room-orchestrator/`)
  — uses the bridge to schedule rooms.
- `pinokio-bridge` (this skill) — the managed-surface read/write API
  that P7 and PMOVES agents use.

## Cross-references

- Pinokio 8 docs: https://cocktailpeanutlabs.github.io/p8/
- creator-collab slice 1 (PR #2264): `room_purpose` + `creator_surface` +
  `hardware_requirements` + `pinokio_app_refs` schema fields
- creator-collab slice 5 (TBD): full creator-studio E2E smoke that
  exercises this bridge end-to-end with a 5090/Spark render
- `pmoves/configs/tac_trees/pinokio-p8.tac.yaml` — the P8 audit tree
  that catches drift on the surfaces this bridge depends on
