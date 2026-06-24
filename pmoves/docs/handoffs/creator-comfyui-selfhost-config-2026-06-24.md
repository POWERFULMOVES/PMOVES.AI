# Creator Pipeline — ComfyUI Self-Host Config (2026-06-24)

**Author:** 4090-CLAUDE. **Lane note:** the ComfyUI render engine + `comfyui-pipeline`
TAC tree are **codex's**; ComfyUI *workflows + LoRA training* are **5090/KiloCode**;
the MinIO→JuiceFS storage seam is **Z890's**. This doc is the design decision +
the **Known Road handoff** authorizing the `docker-compose.comfyui.yml` edit
(`KNOWN_ROAD=compose:handoff:creator-comfyui-selfhost-config-2026-06-24.md`).
It routes the dependent work to those owners — it does not claim their lanes.

## Trigger

Operator directive: **"I'm not using RunPod."** The render overlay pinned
`runpod/comfyui:latest` (also flagged "vendor-specific" in
`DHI_MIGRATION_MANIFEST.md:137`). PMOVES.AI runs its own fleet GPUs, so the
ComfyUI runtime must be self-host and license-clean.

## What was already true (so we don't rebuild)

- `render-webhook` (compose :8085, Supabase callback) and `publisher-discord`
  (:8094) are **already wired** in `pmoves/docker-compose.yml`.
- The real ComfyUI→object-store seam is **comfy-watcher** (`watcher.py` →
  MinIO `pmoves-comfyui` + NATS `artifact_uri: s3://…`), per
  `MEDIA_DATA_ARCHITECTURE_PLAN.md`. NOT render-webhook→MinIO.
- `comfyui` lives in the `docker-compose.comfyui.yml` overlay (profile `creator`),
  intentionally optional. Brought up via `make -C pmoves comfyui-up`
  (Makefile:1713).
- Real creator workflows already exist under `pmoves/creator/workflows/`
  (Qwen-Image-Edit-360, WAN-2.2 img/vid, VibeVoice-RVC, Z-Image Turbo) +
  tutorials under `pmoves/creator/tutorials/`.

So the `comfyui-pipeline` TAC's 4 fails are **not "missing services"** — they
reflect a TAC that encodes a different architecture (render-webhook→MinIO) than
what's built. Reconciling that tree is **codex's** call (see §Handoffs).

## Decision — ComfyUI is a configurable endpoint, not a vendor image

The best fit for the dynamic / impedance-matched fleet is to **decouple the
runtime from the pipeline**. Every consumer targets `${COMFYUI_URL:-http://comfyui:8188}`,
so a node runs ComfyUI whichever way fits, with no pipeline change:

| Node | How ComfyUI runs | Why |
|---|---|---|
| **5090** (32GB) | containerized `comfyui` service, `creator` profile, on-demand | image/video workhorse; no wasted electricity (dynamic-fleet principle) |
| **4090** workstation | host **Pinokio/desktop** ComfyUI; set `COMFYUI_URL=http://host.docker.internal:8188` | avoids GPU-in-Docker-Desktop pain; matches how the creator already works (P7/Pinokio) |
| **Spark** (arm64) | containerized, if/when a model fits | validate arm64 build separately |

**De-RunPod:** the container path now **builds from upstream source**
(`pmoves/services/comfyui/Dockerfile`) on a license-clean base instead of the
vendor image:
- ComfyUI = GPL-3.0 (self-host/internal is fine), PyTorch base = BSD-3, CUDA
  runtime = NVIDIA redistributable. **No CC-BY-NC** — honors the creator-pipeline
  license gate (`reference_creator_pipeline_models`).
- Pinned via `ARG COMFYUI_REF` (default `v0.3.40`) — never a moving branch.
- `${COMFYUI_IMAGE}` still overrides to a pre-built GHCR tag or a vetted image.
- **GPU image → validate the build ON-NODE** (5090 amd64 / Spark arm64); CI does
  not build GPU images (same gate as OmniVoice #1845).

ComfyUI gotcha handled: persist **subpaths** (`models/ output/ input/
custom_nodes/ user/`), never a volume over `/opt/ComfyUI` (would hide the baked
source).

## Changes in this PR (4090 lane)

1. `pmoves/services/comfyui/Dockerfile` — new, build-from-source self-host image.
2. `pmoves/docker-compose.comfyui.yml` — de-RunPod (build context + subpath
   volumes + host-Pinokio override docs). *(Known Road compose edit.)*
3. `pmoves/n8n/flows/pmoves_comfy_gen.json` + `pmoves/services/n8n/workflows/pmoves_comfy_gen.json`
   — standardize the hardcoded `http://comfyui:8188` to `${COMFYUI_URL || …}`
   (matches `pmoves_comfy_hub.json`).
4. `.kilo/command/creator-ws-i-images.md`, `.kilo/command/creator-ws-a2-anime.md`
   — field-briefs routing the image/anime workstreams to 5090/KiloCode.

## Handoffs

- **codex (`comfyui-pipeline` TAC):** reconcile the tree to reality — services
  exist; comfyui is overlay-by-design; the MinIO seam is comfy-watcher, not
  render-webhook; `render-webhook.*MINIO` / `comfyui.*nvidia` patterns also hit
  the `re.search`-no-DOTALL multiline bug fixed for cast-gateway in #1882.
- **5090 / KiloCode:** execute the two field-briefs — build/validate the ComfyUI
  image on-node, install license-clean models, wire CGP provenance.
- **Z890:** MinIO `pmoves-comfyui` → JuiceFS migration (storage lane) is
  unaffected by this change; comfy-watcher keeps the `s3://` seam.

Related: [[project_dynamic_fleet_principle]], [[reference_creator_pipeline_models]],
[[project_creator_operator_lattice]], `research/CREATOR_PIPELINE_HANDOFF_2026-06-08.md`.
