# Mavis ComfyUI Integration

The Mavis end of the **sketch → render → skin** pipeline. Three pieces:

```
SEAP/SEAP  (operator's local Cataclysm Studios sketch archive + 82 SoundCloud tracks)
  └─ G:\My Drive\CataclysmstudiosInc\Pictures\cyber.png  (the 6-eye + third-eye horned-helmet)
        │
        ▼
pmoves/tools/comfyui_client.py     (HTTP wrapper for ComfyUI REST API)
pmoves/tools/render_skin.py        (the pipeline glue: sketch + prompt → theme.skin JSON)
        │
        ▼
ComfyUI host (MiniMax H3 ULTRA, installed via ../install/ scripts)
        │
        ▼
pmoves/design/skins/<skin>.json    (consumed by pmovesRoomAdapter.applyTheme in PMOVES-OpenRoom)
        │
        ▼
Live Pillar 4 room in /stage/?room=pillar4.encoding
```

## What's in this directory

| Path | What it is |
|------|------------|
| `README.md` | This file - the high-level map |
| `install/` | The three Aitrepreneur MiniMax H3 ULTRA installers (RunPod + Windows portable + Windows safe). Pick one based on host. Read `install/README.md` for the decision matrix. |
| `install/ATTRIBUTION.md` | Aitrepreneur credit + model provenance + pinned dep versions. Read this before running any of the install scripts. |
| `workflows/` | The two H3 ULTRA ComfyUI workflow JSONs (standard + turbo-LoRA). Read `workflows/README.md` for the iteration-vs-quality decision. |
| `comfyui_client.py` | Python HTTP wrapper. Submits workflows, polls history, fetches images. Env-driven. Lives in the parent `pmoves/tools/` dir, not here. |
| `pinokio_launch.sh` | Shell wrapper for `pinokio start <app>`. Used to launch ComfyUI + Ace Studio + Veo from the same launcher. Lives in the parent `pmoves/tools/` dir, not here. |
| `render_skin.py` | The pipeline glue. Takes a sketch + prompt, submits to ComfyUI, writes a `theme.skin` JSON. Lives in the parent `pmoves/tools/` dir, not here. |
| `tests/` | Smoke tests for the client + launcher. Mock-based, no actual ComfyUI host required. |

## The "sketch is the finished piece" loop

Per the operator's framing, the design is canonical and the runtime
fabricates around it. The loop is:

1. **Operator picks a sketch** from the Cataclysm Studios archive (e.g.
   `cyber.png` for Pillar 4, `darkxside.jpg` for the operator avatar,
   one of the 2011-07-15 Mega Man X pose studies for a taxonomy bit-state)
2. **Mavis runs** `pmoves/tools/render_skin.py cyber.png "Pillar 4 encoding visual, dark void, neon violet, third eye, 6-eye motif" --output pmoves/design/skins/pillar4-encoding.json`
3. **render_skin.py** loads the workflow, injects the prompt + the sketch
   (via a `LoadImage` node if present, or as a CLIPTextEncode fallback),
   submits to ComfyUI, polls until done, fetches the output PNGs
4. **render_skin.py writes** a `theme.skin` JSON with the rendered PNG
   path + the data-attrs that `pmovesRoomAdapter.applyTheme` (PR #2437 P6)
   consumes
5. **Operator adds** the skin to a room manifest (in PMOVES-OpenRoom, a
   separate submodule worktree), commits, opens PR
6. **Live room** at `http://localhost:5173/webuiapps/?room=pillar4.encoding`
   now has the rendered cyber.png as its wallpaper / icon

That's the loop. The same `render_skin.py` handles the 82 SoundCloud
beats (pass the track name as the prompt, pass an album art sketch as
the image), the IDW/Transformers-style comic panels (pass the script
page as the prompt, pass a character LoRA as the image), and the CHIT
tour pillars (one render per pillar, one commit per skin).

## When to use which tool

| Want to do | Use |
|------------|-----|
| Install ComfyUI + H3 on a fresh host | `install/MINIMAX_H3_ULTRA-AUTO_INSTALL-RUNPOD.sh` (RunPod) or the Windows .bat equivalents |
| Add H3 to an existing ComfyUI install | `install/MINIMAX_H3_ULTRA-MODELS-NODES_INSTALL.bat` |
| Launch ComfyUI / Ace Studio / Veo from this client | `pmoves/tools/pinokio_launch.sh <app>` |
| Render a sketch into a skin | `pmoves/tools/render_skin.py <sketch> "<prompt>" --output <skin.json>` |
| Run a workflow manually with custom inputs | `pmoves/tools/comfyui_client.py submit <workflow.json> --inputs key=value` |
| Verify the client + launcher work without a ComfyUI host | `pytest pmoves/tools/tests/test_comfyui_client.py` |

## Why this lives in `pmoves/tools/` (not a separate repo)

The Mavis creative pipeline is one of the three "agent home" surfaces
alongside the agent runtime (Agent Zero, Archon) and the room runtime
(PMOVES-OpenRoom). Keeping the integration here means:

- The workflow JSONs travel with the rest of the agent tools (no
  separate version to track)
- The render output lands in `pmoves/design/skins/` which is the same
  dir the openroom submodule consumes (PR #2437 P6 wires this)
- A future Spark or Knuckles session can pick up the work by reading
  the path: `pmoves/tools/comfyui/README.md` (this file) → install
  the host → run the client → produce the skin
