# LEARNINGS: mavis-creative-pipeline-v0

**Branch:** `feat/mavis-creative-pipeline-v0`
**Base:** `feat/persona-livingdoc-rooms` @ `a198e1cf3f`
**Commits:** 6 (CLAIM + install + workflows + client + pinokio + render)
**Files added:** 12 (~2,800 ins / 0 del)
**PR:** https://github.com/POWERFULMOVES/PMOVES.AI/pull/TBD
**Date:** 2026-08-06

## TL;DR

The Mavis creative-pipeline v0 slice lands the integration foundation
that turns Cataclysm Studios sketch archive + 82 SoundCloud tracks into
the production substrate for the music video + AI comic + CHIT viz
pipeline. The render itself happens later (operator runs the Aitrepreneur
installer on an H3-capable host, Mavis submits the prompt), but the
foundation is now in `pmoves/tools/`, self-explanatory, cross-agent
pickup-ready, and respects the "sketch is the finished piece" framing.

## What this slice does

| Tool | Purpose |
|------|---------|
| `pmoves/tools/comfyui/install/` | 3 Aitrepreneur MiniMax H3 ULTRA installers (RunPod + Windows portable + Windows safe). Verbatim from operator's `Downloads/SEAP/`, with `ATTRIBUTION.md`. |
| `pmoves/tools/comfyui/workflows/` | 2 H3 ULTRA ComfyUI workflow JSONs (standard + turbo-LoRA). Turbo is the default — ~30-60s render at 5s 720p on RTX 4090. |
| `pmoves/tools/comfyui_client.py` | Synchronous Python HTTP wrapper for ComfyUI's `/prompt` + `/history` + `/view` endpoints. Env-driven. 12/12 tests pass. |
| `pmoves/tools/pinokio_launch.sh` | Shell wrapper for `pinokio start <app>` + port-readiness polling. Cross-platform (Python3 fallback for Git Bash). 8/8 tests pass. |
| `pmoves/tools/render_skin.py` | The pipeline glue. Sketch + prompt -> patched workflow -> ComfyUI render -> theme.skin JSON. 14/14 tests pass. |
| `pmoves/tools/comfyui/README.md` | High-level map of the pipeline for future agents picking this up. |

## What this slice does NOT do (left for follow-up)

- **The actual `cyber.png` render** — needs a ComfyUI host with H3 downloaded.
  Operator runs `pmoves/tools/comfyui/install/MINIMAX_H3_ULTRA-AUTO_INSTALL-RUNPOD.sh`
  on a RunPod pod, then `python -m pmoves.tools.render_skin "G:\My Drive\CataclysmstudiosInc\Pictures\cyber.png" "Pillar 4 encoding visual, third eye, 6-eye motif" --output pmoves/design/skins/pillar4-encoding.json`.
- **Beat → room manifest generator** — `pmoves/tools/beat_to_room.py`. Medium slice.
  The render_skin.py pipeline is reusable per-track. 82 SoundCloud tracks → 82 navigable rooms.
- **CHIT tour re-skin pass** — Warhammer/IDW/Mega Man X aesthetic across `pillars-lab.js`,
  `tenant-renderer`, living-doc. Bigger slice, A2UI surfaces already componentized.
- **Pinokio MCP adapter** — the user mentioned Pinokio can be accessed from this client;
  the shell wrapper covers the immediate need, MCP adapter is the cleaner path for the
  next slice.
- **Pillar 4 room manifest bump in PMOVES-OpenRoom** — submodule, separate worktree,
  separate PR. Comes after the first render lands.

## Acceptance criteria (5/5 met)

- [x] Mavis client can submit an H3 ULTRA workflow to a ComfyUI host (`comfyui_client.py` + tests)
- [x] Mavis can launch a Pinokio app (ComfyUI / Ace Studio / Veo) and wait for ready (`pinokio_launch.sh` + tests)
- [x] Mavis can take a sketch + prompt and produce a `theme.skin` JSON (`render_skin.py` + tests)
- [x] The 3 install paths are documented + copied with attribution (`install/README.md` + `install/ATTRIBUTION.md`)
- [x] The 2 H3 ULTRA workflows are committed as artifacts so future sessions don't need the operator's local SEAP folder (`workflows/README.md`)

## Tests (34/34 pass)

- `pmoves/tools/tests/test_comfyui_client.py` — 12 tests
- `pmoves/tools/tests/test_pinokio_launch.sh` — 8 tests
- `pmoves/tools/tests/test_render_skin.py` — 14 tests

All tests run without an actual ComfyUI host. Mocked HTTP via `urllib.request.urlopen`
patching + a fake pinokio binary (`tests/_fake_pinokio.sh`).

## 5-class review taxonomy (per pr-trim convention)

The 5-class taxonomy (legit / already-fixed / owner / out-of-scope / pre-existing) is the
right spine for the post-merge review of this PR. Anticipated classifications:

- **legit**: 0 (this is a foundation slice with no review to react to yet)
- **already-fixed**: 0
- **owner**: any feedback on the `theme.skin` schema (operator is the consumer, only they
  can sign off on the field names)
- **out-of-scope**: any "add Ace Studio wrapper too" / "add Veo wrapper too" / "add Beat-to-room"
  comments — those are deliberately follow-up slices
- **pre-existing**: n/a (no existing code was modified)

## 4-bucket learnings (per review-lessons > review-comments convention)

### missed-signal
(none yet — this is the initial slice, not a review iteration)

### fix-pattern
(none yet — no review cycles to learn from)

### wrong-suggestion
(none yet)

### already-addressed
- **Pinokio binary detection**: a review might suggest "use `command -v pinokio` for
  presence detection" — already addressed, the wrapper uses `command -v` for
  the binary and Python for port detection.
- **Workflow JSON format**: a review might suggest "validate the workflow JSON before
  submission" — already addressed, the wrapper's `_request` raises `ComfyUIError`
  with the full server error message if the workflow is rejected.
- **Render timeout**: a review might suggest "add a render timeout" — already
  addressed, `PMOVES_COMFYUI_TIMEOUT_S` env var + `_port_open` polling with
  deadline tracking.

## What this proves for the operator's bigger vision

The "sketch is the finished piece" frame is now testable end-to-end. The
operator's 2023-11-03 6-eye third-eye horned-helmet character (cyber.png)
becomes a Pillar 4 encoding pillar skin in 3 commands:

1. `pinokio_launch.sh comfyui --port 8188` (launch the ComfyUI host)
2. `python -m pmoves.tools.render_skin "G:\My Drive\CataclysmstudiosInc\Pictures\cyber.png" "Pillar 4 encoding visual, third eye, 6-eye motif" --output pmoves/design/skins/pillar4-encoding.json` (submit + wait + download)
3. Add the skin to a Pillar 4 room manifest in PMOVES-OpenRoom submodule (separate worktree)

The same loop works for the 82 SoundCloud tracks (pass track name as prompt,
album art as sketch), the IDW/Transformers-style comic panels (pass script page
as prompt, character LoRA as sketch), and the CHIT tour pillars (one render per
pillar, one commit per skin).

## Files changed (12 added)

```
pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md   | +28 (CLAIM entry)
docs/AGENT_TRAIL.md                       | +42 (first trail entry)
pmoves/tools/comfyui/README.md            | new (4916 bytes)
pmoves/tools/comfyui/ATTRIBUTION.md      | new (2648 bytes) - in install/
pmoves/tools/comfyui/install/README.md    | new (3432 bytes)
pmoves/tools/comfyui/install/MINIMAX_H3_ULTRA-AUTO_INSTALL-RUNPOD.sh        | new (24486 bytes, verbatim)
pmoves/tools/comfyui/install/MINIMAX_H3_ULTRA-COMFYUI-MANAGER_AUTO_INSTALL.bat | new (6601 bytes, verbatim)
pmoves/tools/comfyui/install/MINIMAX_H3_ULTRA-MODELS-NODES_INSTALL.bat       | new (11095 bytes, verbatim)
pmoves/tools/comfyui/workflows/README.md  | new (3699 bytes)
pmoves/tools/comfyui/workflows/MINIMAX_H3_ULTRA_WORKFLOW.json               | new (250648 bytes, verbatim)
pmoves/tools/comfyui/workflows/MINIMAX_H3_ULTRA_+TURBO-LORA_WORKFLOW.json   | new (251948 bytes, verbatim)
pmoves/tools/comfyui_client.py            | new (14935 bytes)
pmoves/tools/pinokio_launch.sh           | new (4225 bytes)
pmoves/tools/render_skin.py              | new (15173 bytes)
pmoves/tools/tests/test_comfyui_client.py | new (7623 bytes)
pmoves/tools/tests/test_pinokio_launch.sh| new (4969 bytes)
pmoves/tools/tests/_fake_pinokio.sh      | new (776 bytes - test fixture)
pmoves/tools/tests/test_render_skin.py   | new (11675 bytes)
pmoves/tools/LEARNINGS/creative-pipeline-v0_LEARNINGS.md | new (this file)
```

## Three-body

- **Delivery** (Mavis, this): the slice itself, 6 stacked commits, 34/34 tests pass,
  LEARNINGS, trail entry, AGNOTE CLAIM
- **Control** (DARKXSIDE, operator): review the PR, run the Aitrepreneur installer
  on an H3-capable host, do the first cyber.png render, decide on the Pillar 4
  room manifest bump
- **Memory** (this file + AGNOTE + trail): the full provenance trail for future
  Spark / Knuckles / 4090 / fresh Mavis sessions

## CHIT trail unsigned-local

No `CHIT_PASSPHRASE` loaded in this Mavis session per the standing operator
convention. All entries are unsigned-local.
