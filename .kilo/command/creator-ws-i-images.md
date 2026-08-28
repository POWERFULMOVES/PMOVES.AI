# creator-ws-i-images

Field brief for **KiloCode (GLM-5.1 / 5090)** — implement WS-I (image generation)
of the creator pipeline. Three-Body: 4090-CLAUDE analyzed + scaffolded the
ComfyUI self-host config; KiloCode executes the GPU build + workflow wiring;
trail signed on completion (`chit:sign-trail`).

Source plan: `research/CREATOR_PIPELINE_HANDOFF_2026-06-08.md` (WS-I) +
`pmoves/docs/handoffs/creator-comfyui-selfhost-config-2026-06-24.md`.

## Arguments

- `model` (string, default `qwen-image`): `qwen-image` (Qwen/Qwen-Image, Apache-2.0,
  strong text + ControlNet-Inpainting regional control) or `flux-schnell`
  (black-forest-labs/FLUX.1-schnell, Apache-2.0, fast drafts). **Never Ideogram-4
  (non-commercial).**
- `comfyui_url` (string, default `${COMFYUI_URL:-http://comfyui:8188}`): endpoint —
  the 5090 container service or a host/Pinokio ComfyUI.
- `workflow` (string, optional): reuse an existing graph under
  `pmoves/creator/workflows/` (e.g. `251018_MICKMUMPITZ_QWEN-IMAGE-EDIT-360_1-0.json`)
  rather than authoring from scratch.

## Implementation

1. **Build/validate ComfyUI on-node (5090 amd64).** `make -C pmoves comfyui-up`
   builds `pmoves/services/comfyui/Dockerfile` (build-from-source, replaces the
   removed RunPod image). Confirm `/` responds on :8188 and `nvidia-smi` shows the
   container using the GPU. Fix the pinned `COMFYUI_REF` if the tag drifted.
2. **Install license-clean models** into the `comfyui-models` volume: Qwen-Image
   (Apache) + FLUX.1-schnell (Apache). Record `model id + license` (license gate).
3. **Wire the regional-control workflow** (Ideogram-video equivalent = area-prompt
   / ControlNet-Inpainting). Prefer adapting an existing `pmoves/creator/workflows/`
   graph. Export the POST `/prompt` API-format JSON to
   `pmoves/services/comfyui/prompt_examples/`.
4. **Emit CGP provenance** on each artifact: `point.meta` carries model id, license,
   prompt hash, and (when present) the WS-A cymatic glyph for compositing. Outputs
   land in `/opt/ComfyUI/output` → comfy-watcher ships them to MinIO `pmoves-comfyui`
   + NATS `artifact_uri: s3://…` (existing seam — do not rebuild).
5. **Smoke**: thumbnail/poster with rendered text via the n8n `pmoves_comfy_gen`
   flow (now `COMFYUI_URL`-driven); verify the artifact appears in MinIO + NATS.

Files:
- `pmoves/services/comfyui/Dockerfile` — build base (already scaffolded; validate).
- `pmoves/services/comfyui/prompt_examples/` — add the exported API-format graph.
- `pmoves/config/creator_models.yaml` — register model id + license (extend).

## Related

- `pmoves/docs/handoffs/creator-comfyui-selfhost-config-2026-06-24.md` — ComfyUI runtime decision
- `pmoves/creator/workflows/251018_MICKMUMPITZ_QWEN-IMAGE-EDIT-360_1-0.json` — Qwen workflow
- `pmoves/creator/tutorials/qwen_image_edit_plus_tutorial.md` — Qwen tutorial (ignore its RunPod section)
- `pmoves/services/comfy-watcher/watcher.py` — output → MinIO + NATS seam
- `.claude/skills/comfy-operate-image/` — drive ComfyUI UI + harvest API payload

## Notes

- **License gate is hard:** Apache/MIT/BSD/CC-BY or OpenRAIL-with-note only. Qwen-Image
  + FLUX.1-schnell are Apache-2.0. Record license in CGP `point.meta`.
- ComfyUI volume gotcha: models/output/etc. are SUBPATH mounts — never mount over
  `/opt/ComfyUI`.
- GPU build validates on-node only (CI doesn't build GPU images) — same gate as
  OmniVoice #1845. On Spark (arm64) validate separately.
- Close the loop with `chit:sign-trail` referencing this brief.
